'''Functions to diff and update subtrees in the current Git repository.'''

import os
import re

import click
import git
import requests


SUBTREE_SPLIT_RE = re.compile(r'git-subtree-split: (?P<git_subtree_split>[a-z0-9]+)')


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
    number_prompt = 'Multiple remotes repos found.\n{}\n{}\n\nEnter a number 1-{}'.format(
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


def print_subtree_diff(prefix, repo, commits_since, tags):
    max_prefix_len = len(prefix) + 3
    max_repo_len = len(repo['full_name']) + 3
    row_format = '{:<' + str(max_prefix_len) + '}{:<' + str(max_repo_len) + '}{:<15}{:<30}'
    click.secho(row_format.format('Prefix', 'Remote', 'Ahead By', 'Tags Since', underline=True))
    click.secho(row_format.format(
        prefix,
        repo['full_name'],
        commits_since['ahead_by'],
        ', '.join(sorted(tag['name'] for tag in tags)) or '(none)',
    ))


@click.command()
@click.option(
    'is_dry_run', '-n', '--dry-run',
    is_flag=True,
    help='''Don't actually update anything, just show what would be done.'''
)
@click.option(
    'squash', '--squash',
    is_flag=True,
    help='Pass through `git subtree --squash ...',
)
@click.argument('prefix')
def subtree_update(is_dry_run, squash, prefix):
    '''Update the given subtrees in this repo. Divines their remote from the
    basename of the given prefix. Prompts the user when there are multiple
    possibilities.'''
    # TODO: this isn't a universal assumption
    repo_partial_name = os.path.basename(prefix)

    local_repo = git.Repo(os.getcwd())
    last_split_ref = last_split_ref_for_prefix(local_repo, prefix)

    headers = remote_headers()
    remote_repo = repo_for_partial_name(repo_partial_name, headers)
    commits_since = repo_commits_since(remote_repo, last_split_ref, headers)
    tags = tags_in_commits(remote_repo, commits_since['commits'], headers)

    if not commits_since['ahead_by']:
        click.echo('{} already up-to-date with {}.'.format(prefix, remote_repo['full_name']))
    elif is_dry_run:
        print_subtree_diff(prefix, remote_repo, commits_since, tags)
    else:
        subtree_args = ['pull', remote_repo['git_url'], 'master']

        subtree_kwargs = {'prefix': prefix}
        if squash:
            subtree_kwargs['squash'] = True

        local_repo.git.subtree(*subtree_args, **subtree_kwargs)

        click.echo(local_repo.git.status())
