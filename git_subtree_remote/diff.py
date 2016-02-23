'''Functions to diff a local subtree with its remote.'''


import click
import requests


def repo_commits_since(repo, since_ref, headers):
    if since_ref:
        compare_url = repo['compare_url'].format(base=since_ref, head='master')
        compare_resp = requests.get(compare_url, headers=headers)
        compare_resp.raise_for_status()
        return compare_resp.json()
    else:
        commits = []
        all_commits_url = repo['commits_url'].format(**{'/sha': ''})
        next_commits_url = all_commits_url + '?per_page=100'
        while next_commits_url:
            commits_resp = requests.get(next_commits_url, headers=headers)
            commits_resp.raise_for_status()
            commits.extend(commits_resp.json())
            next_commits_url = (commits_resp.links.get('next') or {}).get('url')

        return {
            'status': 'ahead',
            'ahead_by': len(commits),
            'commits': commits,
        }


def tags_in_commits(repo, commits, headers):
    tags_resp = requests.get(repo['tags_url'], headers=headers)
    tags_resp.raise_for_status()
    commits_by_sha = {commit['sha']: commit for commit in commits}
    return [tag for tag in tags_resp.json() if tag['commit']['sha'] in commits_by_sha]


def print_diverged(remote):
    click.echo('{} is diverged from {}.'.format(
        remote.subtree.prefix,
        remote.repo['html_url'],
    ))


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
        if not remote.subtree.exists:
            ahead_by = '(new)'
        elif remote.is_diverged:
            ahead_by = '(diverged)'
        elif remote.commits_since['ahead_by']:
            ahead_by = remote.commits_since['ahead_by']
        else:
            ahead_by = '(up-to-date)'

        click.secho(row_format.format(
            remote.subtree.prefix,
            remote.repo['html_url'],
            ahead_by,
            ', '.join(sorted(tag['name'] for tag in remote.tags_since)) or '(none)',
        ))


def print_up_to_date(remote):
    click.echo('{} already up-to-date with {}.'.format(
        remote.subtree.prefix,
        remote.repo['html_url'],
    ))
