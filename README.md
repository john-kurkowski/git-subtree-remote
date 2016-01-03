# git-subtree-remote

Are your Git repository's **subtrees** up to date? **Can't remember the remote** you pulled them from? This Git subcommand **diffs**, **adds**, and **updates** the given subtrees (or all) in the current Git repository, finding their remote based on their paths/prefixes/basenames.

## Example

If your subtree has a prefix of `path/to/vim-fireplace`, there's a good chance the remote was https://github.com/tpope/vim-fireplace.git. This subcommand looks that up and runs the appropriate `git subtree pull` for you.

## Motivation

[The power of Git subtree] notes that subtrees do not track the remote they came from. This makes them difficult to diff or keep up to date automatically. You have to remember where they came from, and/or write down the command you used to acquire the subtree in the first place.

I have a _particular use case_ where my subtree prefixes partially encode the remote name, a repo on GitHub. Therefore, I can find the remote via GitHub's search API with confidence. For low confidence matches, I can prompt the user for a manual selection.

Automatic diff and update of my subtrees got a lot easier.

## Limitations

Your subtree remote must be on GitHub. The subtree prefix must match one of the following rules. The examples all resolve to the GitHub repo "tpope/vim-fireplace".

| Rule | Example Prefix |
| ---- | -------------- |
| The dirname + basename is a full, exact GitHub repo name. | path/to/tpope/vim-fireplace |
| The basename is a camelized, full GitHub repo name. | path/to/tpope-vim-fireplace |
| The basename is a short (no author), exact GitHub repo name. | path/to/vim-fireplace |

If your subtree's remote isn't on GitHub or the subtree's prefix doesn't follow these conventions, `git subtree-remote` won't help you. But I'm interested in PRs to make this more general!

Also, keep an eye on the author of [the above article][The power of Git subtree]. The author is getting Git to record `git-subtree-repo: <repo-url-here>` in subtree commits. That would make this project vastly simpler. Or outright foldable into Git's own subtree command.

## Installation

1. `git clone` this repository
2. `python setup.py install`

## Usage

Run the following in a Git repository with subtrees.

### Diff

See what subtrees are outdated.

```zsh
git subtree-remote diff (path/to/some/subtree/prefix...|--all)
```

### Pull

Add or update the given subtrees.

```zsh
git subtree-remote pull (path/to/some/subtree/prefix...|--all)
```

If the subtree doesn't exist, this is the same as `git subtree add`, but it looks up the GitHub remote for you.

If the subtree exists, same as `git subtree pull`, but you don't have to remember the remote. Or it can find and update _all_ your subtrees.

### Advanced

This subcommand uses GitHub's search API, which is rate limited. The script can take a while if you're updating dozens of subtrees. Set your `GITHUB_TOKEN` env var to a GitHub API token to get a faster rate.

[The power of Git subtree]: https://developer.atlassian.com/blog/2015/05/the-power-of-git-subtree/#hacking-on-git-subtree
