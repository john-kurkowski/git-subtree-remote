'''Functions to diff a local subtree with its remote.'''


import click
import requests


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
