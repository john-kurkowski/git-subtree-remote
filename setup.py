'''Are your Git repository's subtrees up to date? Can't remember the remote you
pulled them from? This Git subcommand diffs, adds, and updates the given
subtrees (or all) in the current Git repository, finding their remote based on
their paths/prefixes/basenames.'''


from setuptools import find_packages
from setuptools import setup


setup(
    name='git-subtree-remote',
    version='0.0.1',
    url='https://github.com/john-kurkowski/git-subtree-remote',
    description=__doc__,
    packages=find_packages('.'),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Version Control',
    ],
    entry_points={
        'console_scripts': (
            'git-subtree-remote = git_subtree_remote.command:cli',
        ),
    },
    install_requires=[
        'click >= 6.2, < 7',
        'gitpython >= 1.0.1, < 2',
        'requests >= 2.9.1, < 3',
    ],
)
