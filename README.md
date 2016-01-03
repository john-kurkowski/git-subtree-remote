# git-subtree-update

Are your Git repository's **subtrees** up to date? **Can't remember the remote** you pulled them from? This Git subcommand `git subtree-update <prefix>` **diffs** and **updates** the given subtrees (or `--all` of them) in the current Git repository, based on their basenames.

For example, if your subtree has a prefix of `path/to/vim-fireplace`, there's a good chance the remote was https://github.com/tpope/vim-fireplace.git. This subcommand looks that up and runs the appropriate `git subtree pull ...` for you.

## Motivation

[The power of Git subtree] notes that subtrees do not track the remote they came from. This makes them difficult to diff or keep up to date automatically. You have to remember where they came from, and/or write down the command you used to acquire the subtree in the first place.

I have a _particular use case_ where my subtree prefixes' _basenames_ share their name with a repo on GitHub. Therefore, I can find them via GitHub's search API with confidence. For low confidence matches, I can prompt the user for a manual selection.

Automatic diff and update of my subtrees got a lot easier.

## Limitations

If your subtree prefixes don't follow this basename convention or aren't on GitHub, `git subtree-update` won't help you. But I'm interested in PRs to make this more general!

Also, keep an eye on the author of [the above article][The power of Git subtree]. The author is getting Git to record `git-subtree-repo: <repo-url-here>` in subtree commits. That would make this project vastly simpler. Or outright foldable into Git's own subtree command.

## Installation

1. `git clone` this repository
2. `python setup.py install`

## Usage

In a Git repository with subtrees:

```zsh
git subtree-update path/to/some/subtree/prefix
```

Or update all subtrees:

```zsh
git subtree-update --all
```

Use `--dry-run` to see what subtrees are outdated:

```zsh
git subtree-update --dry-run --all
```

This uses GitHub's search API, which is rate limited. The script can take a while if you're updating dozens of subtrees. Set your `GITHUB_TOKEN` env var to a GitHub API token to get a faster rate.

[The power of Git subtree]: https://developer.atlassian.com/blog/2015/05/the-power-of-git-subtree/#hacking-on-git-subtree
