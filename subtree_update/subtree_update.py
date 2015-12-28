'''Functions to diff and update subtrees in the current Git repository.'''

import collections
import os
import re

import click
import git
import requests

from .utilities import RatedSemaphore


API_BASE = 'https://api.github.com'
SUBTREE_DIR_RE = re.compile(r'git-subtree-dir: (?P<git_subtree_dir>\S.*)')
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


def validate_subtrees(local_repo, is_all, prefixes):
    if is_all:
        prefixes = all_subtree_prefixes(local_repo)
        if not prefixes:
            raise click.BadParameter('No subtrees found in this repo')
    elif not prefixes:
        raise click.BadParameter('At least 1 subtree prefix is required (or set --all)')

    return [
        Subtree(prefix, last_split_ref_for_prefix(local_repo, prefix))
        for prefix in prefixes
    ]


def all_subtree_prefixes(local_repo):
    '''Finds all current subtree prefixes in the current branch of the current
    repository.'''
    subtree_splits = local_repo.git.log(grep='git-subtree-dir: ')
    prefixes = set(SUBTREE_DIR_RE.findall(subtree_splits))
    existing_prefixes = (prefix for prefix in prefixes if os.path.exists(prefix))
    return sorted(existing_prefixes)


def last_split_ref_for_prefix(local_repo, prefix):
    subtree_splits = local_repo.git.log(grep='git-subtree-dir: {}'.format(prefix.rstrip('/')))
    return SUBTREE_SPLIT_RE.search(subtree_splits).group('git_subtree_split')


def rate_limit_find_subtree_remote():
    headers = remote_headers()
    search_max_per_minute = 30 if 'Authorization' in headers else 10
    search_buffer_s = 30
    search_rate_limit = RatedSemaphore(search_max_per_minute, 60 + search_buffer_s)
    def rate_limited_find(subtree):
        with search_rate_limit:
            return find_subtree_remote(subtree, headers)
    return rate_limited_find


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
    repo_partial_name = os.path.basename(subtree.prefix.rstrip('/'))

    remote_repo = repo_for_partial_name(repo_partial_name, headers)
    commits_since = repo_commits_since(remote_repo, subtree.last_split_ref, headers)
    tags_since = tags_in_commits(remote_repo, commits_since['commits'], headers)
    return SubtreeRemote(subtree, remote_repo, commits_since, tags_since)


def repo_for_partial_name(repo_partial_name, headers):
    '''Finds remote repositories matching the given name. If multiple match,
    picks the top ranked according to the search API. If their ranks are close,
    prompts user to choose one manually.'''
    search_url = '{}/search/repositories'.format(API_BASE)
    search_params = {
        'q': repo_partial_name,
        'in': 'name',
    }
    search_resp = requests.get(search_url, search_params, headers=headers)
    search_resp.raise_for_status()
    search_json = search_resp.json()

    repos_with_name = [repo for repo in search_json['items'] if repo['name'] == repo_partial_name]
    scores = [repo['score'] for repo in repos_with_name]
    if not repos_with_name:
        raise ValueError('No remotes found for {}'.format(repo_partial_name))
    elif len(repos_with_name) == 1 or is_confident_match(scores)[0]:
        repo_i = 0
    else:
        click.echo('') # Newline after surrounding progress bar
        repo_i = prompt_to_disambiguate_repos(repo_partial_name, repos_with_name)

    return repos_with_name[repo_i]


def is_confident_match(scores):
    '''Return an array of bools whether the corresponding score is a confident
    match, according to the search API ranking.

    Interface inspired by http://stackoverflow.com/a/22357811/62269. However,
    that function won't work here, because there aren't enough input points
    (usually less than 5). Instead, we tailor the definition of "outlier" to
    scores typically encountered from GitHub's search API.'''
    high_score = 50
    high_difference = 30
    result = [False] * len(scores)
    if scores[0] > high_score and scores[0] - scores[1] > high_difference:
        result[0] = True
    return result


def prompt_to_disambiguate_repos(query, repos):
    '''Prompt the user to pick from the given repositories that all matched the
    same query.'''
    max_repo_len = max(len(repo['html_url']) for repo in repos) + 3
    number_choice_format = '{:<4} {:<' + str(max_repo_len) + '} {:>}'

    number_prompt = 'Multiple remote repos found for {}.\n{}\n{}\n\nEnter a number 1-{}'.format(
        query,
        number_choice_format.format('', 'Remote', 'Score'),
        '\n'.join(
            number_choice_format.format('[{}]'.format(i + 1), repo['html_url'], repo['score'])
            for i, repo in enumerate(repos)
        ),
        len(repos),
    )

    repo_i = -1
    while repo_i < 0 or len(repos) <= repo_i:
        repo_i = click.prompt(number_prompt, type=int) - 1
    return repo_i


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
    max_repo_len = max(len(remote.repo['html_url']) for remote in subtree_remotes) + 3
    row_format = '{:<' + str(max_prefix_len) + '}{:<' + str(max_repo_len) + '}{:<15}{:<30}'

    click.secho(row_format.format('Prefix', 'Remote', 'Ahead By', 'Tags Since', underline=True))

    for remote in subtree_remotes:
        click.secho(row_format.format(
            remote.subtree.prefix,
            remote.repo['html_url'],
            remote.commits_since['ahead_by'] or '(up-to-date)',
            ', '.join(sorted(tag['name'] for tag in remote.tags_since)) or '(none)',
        ))


def print_up_to_date(remote):
    click.echo('{} already up-to-date with {}.'.format(
        remote.subtree.prefix,
        remote.repo['html_url'],
    ))


@click.command()
@click.option(
    'is_all', '--all',
    is_flag=True,
    help='''Update all subtrees in the repo.''',
)
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
def subtree_update(is_all, is_dry_run, squash, prefixes):
    '''Update the given subtrees in this repository. Divines their remote from
    the basename of the given prefix. Prompts the user when there are multiple
    possibilities.'''
    local_repo = git.Repo(os.getcwd())
    subtrees = validate_subtrees(local_repo, is_all, prefixes)

    rate_limited_find = rate_limit_find_subtree_remote()
    with click.progressbar(subtrees, label='Finding subtree remotes') as progressbar:
        subtree_remotes = [
            rate_limited_find(subtree)
            for subtree in progressbar
        ]

    if is_dry_run:
        print_subtree_diff(subtree_remotes)
        return

    updating_label = 'Updating {} subtrees'.format(len(subtree_remotes))
    with click.progressbar(subtree_remotes, label=updating_label) as progressbar:
        for remote in progressbar:
            if not remote.is_ahead:
                click.echo('') # Newline after surrounding progress bar
                print_up_to_date(remote)
                continue

            subtree_args = ['pull', remote.repo['git_url'], 'master']

            subtree_kwargs = {'prefix': remote.subtree.prefix}
            if squash:
                subtree_kwargs['squash'] = True

            local_repo.git.subtree(*subtree_args, **subtree_kwargs)

    click.echo(local_repo.git.status())
