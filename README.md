# README.md

---

## Changelog Generator Tool

This Python script is a changelog generator that creates a detailed changelog for a project based on git commit history.
It identifies version changes, associates commits with issues from an issue tracker (currently supports Redmine), and
generates a markdown file summarizing these changes.

### Features

- Supports different version containers like Maven (`pom.xml`), NPM (`package.json`), and environment files.
- Identifies commits associated with version changes.
- Extracts issue information from commit messages for Redmine.
- Generates a changelog in markdown format.

### Prerequisites

- Python 3
- packaging (It's temporary)
- Git repository
- Redmine issue tracker (for advanced commit information)

### Setup

- Ensure Python 3 is installed on your system.
- Install packaging:
```shell
pip install packaging
```

### Usage

1. Clone your git repository locally, if you haven't already.
2. Navigate to the root directory of this script.
3. Run the script via the command line, adjusting the arguments as needed.

#### Sample Command

```shell
python easy_changelog.py --issue-tracker-url YOUR_ISSUE_TRACKER_URL --issue-tracker-token YOUR_API_KEY --version-control-system-commit-url YOUR_VCS_COMMIT_BASE_URL -C PATH_TO_YOUR_GIT_REPO
```

Replace placeholders (`YOUR_ISSUE_TRACKER_URL`, `YOUR_API_KEY`, `YOUR_VCS_COMMIT_BASE_URL`, `PATH_TO_YOUR_GIT_REPO`)
with applicable values.

### Command Line Arguments

- `--issue-tracker-type`: Optional. Issue tracker type. Currently, only `redmine` is supported.
- `--issue-tracker-url`: Required. Base URL of your issue tracker.
- `--issue-tracker-token`: Required. API key or token for the issue tracker.
- `--version-control-system-commit-url`: Required. Base URL used in the changelog to link commits.
- `-C` / `--repository-path`: Optional. Path to the git directory. If not provided, the current working directory is
  used by default.
- `--version-container-type`: Optional. The type of version container (`maven`, `npm`, `env`). Default is `maven`.
- `--version-container-path`: Optional. Path to the version file relative to the repository root. Default is `pom.xml`
  for Maven projects.
- `-o` / `--output-file`: Optional. Path to the output changelog file. Default is `CHANGELOG.md`.
- `--version-compare-mode`: Optional. Version comparison mode (`full`,`major`,`minor`,`patch`,`labels`). Perform the
  comparison up to specified version component and ignore others. It's useful for example if dev-branch contains patches
  or labels like `-alpha` or `-rc.0` and you want to include these changes to changelog file but do not separate it by
  different versions. Default is `full` which means compare all components.

### Output

The script generates a `CHANGELOG.md` file (or another specified file) in the root directory of this script, documenting
all notable changes in the format recommended by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
