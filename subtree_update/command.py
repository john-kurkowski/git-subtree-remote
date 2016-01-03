'''Commands to diff and update subtrees in the current Git repository.'''


import os

import click
import git

from .diff import print_subtree_diff
from .diff import print_up_to_date
from .local import validate_subtrees
from .remote import rate_limit_find_subtree_remote


def subtree_pull(local_repo, remote, squash):
    subtree_args = ['pull', remote.repo['git_url'], 'master']

    subtree_kwargs = {'prefix': remote.subtree.prefix}
    if squash:
        subtree_kwargs['squash'] = True

    return local_repo.git.subtree(*subtree_args, **subtree_kwargs)


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
    try:
        subtrees = validate_subtrees(local_repo, is_all, prefixes)
    except ValueError as verr:
        raise click.BadParameter(verr.message)

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
            if remote.is_ahead:
                subtree_pull(local_repo, remote, squash)
            else:
                click.echo('') # Newline after surrounding progress bar
                print_up_to_date(remote)

    click.echo(local_repo.git.status())
