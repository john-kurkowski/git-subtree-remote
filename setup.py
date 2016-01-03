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
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Version Control',
    ],
    entry_points={
        'console_scripts': (
            'git-subtree-update = subtree_update.command:cli',
        ),
    },
    install_requires=[
        'click >= 6.2, < 7',
        'gitpython >= 1.0.1, < 2',
        'requests >= 2.9.1, < 3',
    ],
)
