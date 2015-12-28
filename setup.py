'''Git subcommand `git subtree-update <prefix>` to update the given subtrees in
the current Git repository.'''

from setuptools import find_packages
from setuptools import setup


setup(
    name='git-subtree-update',
    version='0.0.1',
    url='https://github.com/john-kurkowski/git-subtree-update',
    description=__doc__,
    packages=find_packages('.'),
    entry_points={
        'console_scripts': (
            'git-subtree-update = subtree_update:subtree_update',
        ),
    },
    install_requires=[
        'click >= 6.2, < 7',
        'gitpython >= 1.0.1, < 2',
        'requests >= 2.9.1, < 3',
    ],
)
