'''Functions to find upstream remotes for subtrees, based on their path/prefix/basename.'''


import collections
import os

import click
import requests

from .diff import repo_commits_since
from .diff import tags_in_commits
from .utilities import RatedSemaphore


API_BASE = 'https://api.github.com'


class SubtreeRemote(collections.namedtuple('SubtreeRemote', (
        'subtree',
        'repo',
        'commits_since',
        'tags_since',
    ))):

    @property
    def is_ahead(self):
        return bool(self.commits_since['ahead_by'])

    @property
    def is_diverged(self):
        return self.commits_since['status'] == 'diverged'


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
    '''Finds a local subtree's remote based on its prefix.

    1. Is the prefix's dirname + basename an exact GitHub repo id? E.g.
       path/to/tpope/vim-markdown
    2. Is the basename a kebab-cased GitHub repo id? E.g. GitHub
       tpope/vim-markdown -> local path/to/tpope-vim-markdown
    3. Assume the author is missing; search GitHub for the basename. Prompt the
       user to disambiguate multiple hits.

    If the subtree's remote isn't somehow, even partially encoded in the
    prefix, you're looking at the wrong library.
    '''
    remote_repo = None

    prefix = subtree.prefix.rstrip('/')
    split = prefix.rsplit(os.sep, 2)
    if len(split) >= 2:
        repo_exact_name = os.path.join(*split[-2:])
        try:
            remote_repo = repo_for_exact_name(repo_exact_name, headers)
        except KeyError:
            pass

    repo_partial_name = os.path.basename(prefix)
    if not remote_repo and '-' in repo_partial_name:
        try:
            remote_repo = repo_for_kebab_name(repo_partial_name, headers)
        except KeyError:
            pass

    if not remote_repo:
        remote_repo = repo_for_partial_name(repo_partial_name, headers)

    commits_since = repo_commits_since(remote_repo, subtree.last_split_ref, headers)
    tags_since = tags_in_commits(remote_repo, commits_since['commits'], headers)
    return SubtreeRemote(subtree, remote_repo, commits_since, tags_since)


def repo_for_exact_name(repo_exact_name, headers):
    '''Returns the GitHub repo with the given owner/name string id. Raises
    KeyError if no repo found.'''
    repo_url = '{}/repos/{}'.format(API_BASE, repo_exact_name)
    repo_resp = requests.get(repo_url, headers=headers)
    try:
        repo_resp.raise_for_status()
    except requests.exceptions.HTTPError as http_ex:
        if http_ex.response.status_code == 404:
            raise KeyError('Not found: {}'.format(repo_exact_name))
        else:
            raise
    return repo_resp.json()


def repo_for_kebab_name(repo_partial_name, headers):
    '''Returns the first, existing GitHub repo name contained in the
    kebab-cased version. Raises KeyError if no repo found.'''
    kebabs = repo_partial_name.split('-')
    for i, _ in enumerate(kebabs):
        repo_exact_name = '{}/{}'.format('-'.join(kebabs[0:i+1]), '-'.join(kebabs[i+1:]))
        try:
            return repo_for_exact_name(repo_exact_name, headers)
        except KeyError as key_err:
            pass
    raise key_err


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
    same query. Returns the 0-based index picked.'''
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

    repo_i = click.prompt(number_prompt, type=click.IntRange(1, len(repos))) - 1
    return repo_i
