'''Functions to diff and update subtrees in the current Git repository.'''

import collections
import os
import re

import click
import git
import requests


SUBTREE_SPLIT_RE = re.compile(r'git-subtree-split: (?P<git_subtree_split>[a-z0-9]+)')


class Subtree(collections.namedtuple('Subtree', (
        'prefix',
        'last_split_ref',
    ))):
    pass


class SubtreeRemote(collections.namedtuple('SubtreeRemote', (
        'subtree',
        'repo',
        'commits_since',
        'tags_since',
    ))):

    @property
    def is_ahead(self):
        return bool(self.commits_since['ahead_by'])


def last_split_ref_for_prefix(local_repo, prefix):
    subtree_splits = local_repo.git.log(grep='git-subtree-dir: {}'.format(prefix))
    return SUBTREE_SPLIT_RE.search(subtree_splits).group('git_subtree_split')


def remote_headers():
    headers = {
        'Accept': 'application/vnd.github.v3+json',
    }

    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'token {}'.format(token)

    return headers


def find_subtree_remote(subtree, headers):
    # TODO: this isn't a universal assumption
    repo_partial_name = os.path.basename(subtree.prefix)

    remote_repo = repo_for_partial_name(repo_partial_name, headers)
    commits_since = repo_commits_since(remote_repo, subtree.last_split_ref, headers)
    tags_since = tags_in_commits(remote_repo, commits_since['commits'], headers)
    return SubtreeRemote(subtree, remote_repo, commits_since, tags_since)


def repo_for_partial_name(repo_partial_name, headers):
    '''Finds remote repositories matching the given name. Prompts user to
    choose one if multiple match.'''
    search_url = 'https://api.github.com/search/repositories'
    search_params = {
        'q': repo_partial_name,
        'in': 'name',
    }
    search_resp = requests.get(search_url, search_params, headers=headers)
    search_resp.raise_for_status()
    search_json = search_resp.json()

    repos_with_name = [repo for repo in search_json['items'] if repo['name'] == repo_partial_name]
    repo_i = 0 if len(repos_with_name) < 2 else -1

    max_repo_len = max(len(repo['full_name']) for repo in repos_with_name) + 3
    number_choice_format = '{:<4} {:<' + str(max_repo_len) + '} {:>}'
    number_prompt = 'Multiple remote repos found for {}.\n{}\n{}\n\nEnter a number 1-{}'.format(
        repo_partial_name,
        number_choice_format.format('', 'Remote', 'Score'),
        '\n'.join(
            number_choice_format.format('[{}]'.format(i + 1), repo['full_name'], repo['score'])
            for i, repo in enumerate(repos_with_name)
        ),
        len(repos_with_name),
    )

    while repo_i < 0 or len(repos_with_name) <= repo_i:
        repo_i = click.prompt(number_prompt, type=int) - 1

    return repos_with_name[repo_i]


def repo_commits_since(repo, since_ref, headers):
    compare_url = repo['compare_url'].format(base=since_ref, head='master')
    compare_resp = requests.get(compare_url, headers=headers)
    compare_resp.raise_for_status()
    return compare_resp.json()


def tags_in_commits(repo, commits, headers):
    tags_resp = requests.get(repo['tags_url'], headers=headers)
    tags_resp.raise_for_status()
    commits_by_sha = {commit['sha']: commit for commit in commits}
    return [tag for tag in tags_resp.json() if tag['commit']['sha'] in commits_by_sha]


def print_subtree_diff(subtree_remotes):
    '''Prints a summary diff of subtree remotes that are ahead.'''
    if len(subtree_remotes) == 1 and not subtree_remotes[0].is_ahead:
        print_up_to_date(subtree_remotes[0])
        return

    max_prefix_len = max(len(remote.subtree.prefix) for remote in subtree_remotes) + 3
    max_repo_len = max(len(remote.repo['full_name']) for remote in subtree_remotes) + 3
    row_format = '{:<' + str(max_prefix_len) + '}{:<' + str(max_repo_len) + '}{:<15}{:<30}'
    click.secho(row_format.format('Prefix', 'Remote', 'Ahead By', 'Tags Since', underline=True))
    for remote in subtree_remotes:
        click.secho(row_format.format(
            remote.subtree.prefix,
            remote.repo['full_name'],
            remote.commits_since['ahead_by'] or '(up-to-date)',
            ', '.join(sorted(tag['name'] for tag in remote.tags_since)) or '(none)',
        ))


def print_up_to_date(remote):
    click.echo('{} already up-to-date with {}.'.format(
        remote.subtree.prefix,
        remote.repo['full_name'],
    ))


@click.command()
@click.option(
    'is_dry_run', '-n', '--dry-run',
    is_flag=True,
    help='''Don't actually update anything, just show what's outdated.'''
)
@click.option(
    'squash', '--squash',
    is_flag=True,
    help='Pass through `git subtree --squash ...`',
)
@click.argument('prefixes', 'prefix', nargs=-1)
def subtree_update(is_dry_run, squash, prefixes):
    '''Update the given subtrees in this repo. Divines their remote from the
    basename of the given prefix. Prompts the user when there are multiple
    possibilities.'''
    local_repo = git.Repo(os.getcwd())
    subtrees = [
        Subtree(prefix, last_split_ref_for_prefix(local_repo, prefix))
        for prefix in prefixes
    ]

    headers = remote_headers()
    subtree_remotes = [
        find_subtree_remote(subtree, headers)
        for subtree in subtrees
    ]

    if is_dry_run:
        print_subtree_diff(subtree_remotes)
        return

    for remote in subtree_remotes:
        if not remote.is_ahead:
            print_up_to_date(remote)
            continue

        subtree_args = ['pull', remote.repo['git_url'], 'master']

        subtree_kwargs = {'prefix': remote.subtree.prefix}
        if squash:
            subtree_kwargs['squash'] = True

        local_repo.git.subtree(*subtree_args, **subtree_kwargs)

    click.echo(local_repo.git.status())
