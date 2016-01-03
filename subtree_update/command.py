'''Commands to diff and update subtrees in the current Git repository.'''


import os

import click
import git

from .diff import print_subtree_diff
from .diff import print_up_to_date
from .local import validate_subtrees
from .remote import rate_limit_find_subtree_remote


def validate_subtree_remotes(local_repo, is_all, prefixes):
    try:
        subtrees = validate_subtrees(local_repo, is_all, prefixes)
    except ValueError as verr:
        raise click.BadParameter(verr.message)

    rate_limited_find = rate_limit_find_subtree_remote()
    with click.progressbar(subtrees, label='Finding subtree remotes') as progressbar:
        return [
            rate_limited_find(subtree)
            for subtree in progressbar
        ]


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    'is_all', '--all',
    is_flag=True,
    help='''Update all subtrees in the repo.''',
)
@click.argument('prefixes', 'prefix', nargs=-1)
def diff(is_all, prefixes):
    '''Diff the given subtrees. Divines their remote from the given prefix.
    Prompts the user when there are multiple possibilities.'''
    local_repo = git.Repo(os.getcwd())
    subtree_remotes = validate_subtree_remotes(local_repo, is_all, prefixes)
    print_subtree_diff(subtree_remotes)


@cli.command()
@click.option(
    'is_all', '--all',
    is_flag=True,
    help='''Update all subtrees in the repo.''',
)
@click.option(
    'squash', '--squash',
    is_flag=True,
    help='Pass through `git subtree --squash ...`',
)
@click.argument('prefixes', 'prefix', nargs=-1)
def pull(is_all, squash, prefixes):
    '''Add or update the given subtrees. Divines their remote from the given
    prefix. Prompts the user when there are multiple possibilities.'''
    local_repo = git.Repo(os.getcwd())
    subtree_remotes = validate_subtree_remotes(local_repo, is_all, prefixes)
    updating_label = 'Updating {} subtree(s)'.format(len(subtree_remotes))
    with click.progressbar(subtree_remotes, label=updating_label) as progressbar:
        for remote in progressbar:
            subtree_args = [remote.repo['git_url'], 'master']
            subtree_kwargs = {'prefix': remote.subtree.prefix}
            if squash:
                subtree_kwargs['squash'] = True

            if not remote.subtree.exists:
                subtree_args.insert(0, 'add')
                local_repo.git.subtree(*subtree_args, **subtree_kwargs)
            elif remote.is_ahead:
                subtree_args.insert(0, 'pull')
                local_repo.git.subtree(*subtree_args, **subtree_kwargs)
            else:
                click.echo('') # Newline after surrounding progress bar
                print_up_to_date(remote)

    click.echo(local_repo.git.status())
