'''Functions to find subtrees in a local Git repo.'''


import collections
import os
import re


SUBTREE_DIR_RE = re.compile(r'git-subtree-dir: (?P<git_subtree_dir>\S.*)')
SUBTREE_SPLIT_RE = re.compile(r'git-subtree-split: (?P<git_subtree_split>[a-z0-9]+)')


class Subtree(collections.namedtuple('Subtree', (
        'prefix',
        'last_split_ref',
    ))):
    pass


def validate_subtrees(local_repo, is_all, prefixes):
    if is_all:
        prefixes = all_subtree_prefixes(local_repo)
        if not prefixes:
            raise ValueError('No subtrees found in this repo')
    elif not prefixes:
        raise ValueError('At least 1 subtree prefix is required (or set --all)')

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
