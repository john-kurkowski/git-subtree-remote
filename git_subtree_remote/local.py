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

    @property
    def exists(self):
        return bool(self.last_split_ref)


def validate_subtrees(local_repo, is_all, prefixes):
    '''Validates the --all flag or variadic subtree prefixes given to the
    program.'''
    if is_all:
        prefixes = all_subtree_prefixes(local_repo)
        if not prefixes:
            raise ValueError('No subtrees found in this repo')
    elif not prefixes:
        raise ValueError('At least 1 subtree prefix is required (or set --all)')

    def mk_subtree(prefix):
        ref = None
        if os.path.exists(prefix):
            ref = last_split_ref_for_prefix(local_repo, prefix)
        return Subtree(prefix, ref)

    return [mk_subtree(prefix) for prefix in prefixes]


def all_subtree_prefixes(local_repo):
    '''Finds all current subtree prefixes in the current branch of the current
    repository.'''
    subtree_splits = local_repo.git.log(grep='git-subtree-dir: ')
    prefixes = set(SUBTREE_DIR_RE.findall(subtree_splits))
    existing_prefixes = (prefix for prefix in prefixes if os.path.exists(prefix))
    return sorted(existing_prefixes)


def last_split_ref_for_prefix(local_repo, prefix):
    repo_dir = os.path.join(local_repo.git_dir, os.pardir)
    repo_relative_prefix = os.path.relpath(prefix, repo_dir).rstrip('/')
    subtree_splits = local_repo.git.log(grep='git-subtree-dir: {}'.format(repo_relative_prefix))
    return SUBTREE_SPLIT_RE.search(subtree_splits).group('git_subtree_split')
