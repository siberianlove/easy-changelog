#!/usr/bin/env python3

from http.client import HTTPResponse, HTTPSConnection
from packaging import version  # TODO: remove this dependency in final executable
import json
import re
import sys
import subprocess
import shlex
from typing import Any, Union, Tuple, Optional, Callable
import xml.etree.ElementTree as ET
from collections import defaultdict
import argparse
from enum import Enum


class VersionContainer(Enum):
    """`VersionContainer`

    An Enum representing different types of version containers.
    - Attributes: `maven`, `npm`, `env` which are the types of version containers.
    """

    maven = "maven"
    npm = "npm"
    env = "env"

    def __str__(self):
        return self.value


class VersionCompareMode(Enum):
    """`VersionCompareMode`

    An Enum representing different types of version comparison modes.

    """

    full = "full"
    major = "major"
    minor = "minor"
    patch = "patch"
    labels = "labels"

    def __str__(self):
        return self.value


class Commit:
    """`Commit`

    A class representing a single git commit.
    - Properties: `sha`, `title`, `date`, `version`, `issue`, `issue_title`, `tracker`.
    - Parameters:
        - `sha`: A string representing the commit hash.
        - `title`: Commit title.
        - `date`: Commit date.
        - `version`: Version related to the commit.
        - `issue` (Optional): The issue ID related to this commit if any.
        - `issue_title` (Optional): The title of the issue linked to this commit.
        - `tracker` (Optional): The tracker system used for the linked issue.
    """

    sha: str
    title: str
    date: str
    version: str
    issue: str
    issue_title: str
    tracker: str

    def __init__(
            self,
            sha: str,
            title: str,
            date: str,
            version: str,
            issue: str = None,
            issue_title: str = None,
            tracker: str = None,
    ):
        self.sha = sha
        self.title = title
        self.date = date
        self.version = version
        self.issue = issue
        self.issue_title = issue_title
        self.tracker = tracker


def git_log_array(
        git_dir: str, file: str = None, from_sha: str = None, to_sha: str = None
) -> list[str]:
    """`git_log_array`

    Returns an array of strings obtained from git log command.
    - Parameters:
        - `git_dir`: Directory of the git repository.
        - `file` (Optional): Specific file to track history.
        - `from_sha` (Optional): Starting commit hash.
        - `to_sha` (Optional): Ending commit hash.
    - Returns: A list of strings, each representing a git commit log entry.
    """
    cmd = [
        "git",
        "-C",
        git_dir,
        "log",
        "--pretty=format:%h%n%s%n%d%ci",
        "-s",
        "-z",
        "--reverse",
        "--no-merges",
    ]
    if from_sha and to_sha:
        cmd.extend([f"{from_sha}..{to_sha}"])
    elif from_sha:
        cmd.extend([f"{from_sha}"])
    if file:
        cmd.extend(["--", file])
    print(f"[CMD]: {shlex.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR]: {result.stderr}")
        exit(result.returncode)
    git_log_history = result.stdout.split("\0")
    return git_log_history


def git_head_sha(git_dir: str) -> tuple[Optional[str], Optional[str]]:
    cmd = ["git", "-C", git_dir, "rev-parse", "--short", "HEAD"]
    print(f"[CMD]: {shlex.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr, None
    return None, re.sub("\\n", "", result.stdout)


def git_show(git_dir: str, sha: str, version_file: str = "pom.xml") -> tuple[Optional[str], Optional[str]]:
    """`git_show`

    Shows the content of a version file at a specific commit.
    - Parameters:
        - `git_dir`: Directory of the git repository.
        - `sha`: Commit hash.
        - `version_file` (Optional): File containing the version, default is `pom.xml`.
    - Returns: A tuple `(error, result)` where `error` is any error message, `result` is the file content at the given commit.
    """
    cmd = ["git", "-C", git_dir, "show", f"{sha}:{version_file}"]
    print(f"[CMD]: {shlex.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr, None
    return None, result.stdout


def git_is_shallow(git_dir: str) -> tuple[Optional[str], Optional[bool]]:
    """`git_is_shallow`

    Checks if the git repository is shallow. Requires `git` of version >= 2.15 to be installed.
    - Parameters:
        - `git_dir`: Directory of the git repository.
    - Returns: `True` if the git repository is shallow-repository, `False` otherwise.
    """
    cmd = ["git", "-C", git_dir, "rev-parse", "--is-shallow-repository"]
    print(f"[CMD]: {shlex.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr, None
    return None, "true" in result.stdout.lower()


def check_system_requirements():
    """`check_system_requirements`

    Checks that the system requirements are installed and available on your system. If not, it will raise an exception
    """
    git_required_version = "2.15"
    cmd = ["git", "--version"]
    print(f"[CMD]: {shlex.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] git is probably not installed on your system: {result.stderr}")
        exit(1)
    git_version: str = re.sub("[^\\d\\.]", "", result.stdout)
    if version.parse(git_version) < version.parse(git_required_version):
        print(f"[ERROR] git is older than {git_required_version}. Please update your git version: {git_version}")
        exit(1)


def parse_version_maven(file_content: str) -> str:
    """`parse_version_maven`

    Parses the version from a Maven pom.xml file content.
    - Parameters:
        - `file_content`: Content of the pom.xml file.
    - Returns: The version string if found, otherwise empty string.
    """
    pre = "{http://maven.apache.org/POM/4.0.0}"
    root = ET.ElementTree(ET.fromstring(file_content))
    result = ""
    xpath = f"./{pre}version"
    result = root.findtext(xpath)
    return result


def parse_version_npm(file_content: str) -> str:
    """`parse_version_npm`

    Parses the version from a npm package.json file content.
    - Parameters:
        - `file_content`: Content of the package.json file.
    - Returns: The version string.
    """
    file_json = json.loads(file_content)
    return file_json["version"]


def parse_version_env(file_content: str, version_key: str = "VERSION") -> Optional[str]:
    """`parse_version_env`

    Parses the version from an environment file content.
    - Parameters:
        - `file_content`: Content of the env file.
        - `version_key` (Optional): The key for the version variable, default is `VERSION`.
    - Returns: The version string if found, otherwise `None`.
    """
    env_vars = []  # or dict {}
    for line in file_content.split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        key, value = line.replace("export ", "", 1).strip().split("=", 1)
        if key == version_key:
            return value
        env_vars.append(key)
    print(
        f"[WARN] cannot parse version. Found keys: {env_vars}. Expected: {version_key}"
    )
    return None


def parse_issue_redmine(title: str) -> Optional[str]:
    """`parse_issue_redmine`

    Extracts an issue ID from a commit title assuming it mentions a Redmine issue.
    - Parameters:
        - `title`: The commit title.
    - Returns: The issue ID as a string, or `None` if not found.
    """
    result = re.search("#\\d+", title)
    if result:
        return result.group()[1:]
    return None


def fill_commits_info_stub(
        commits: list[Commit], issue_tool_url: str, issue_tool_api_key: str
) -> None:
    """`fill_commits_info_stub`

    A stub function to set tracker and issue title to "STUB" for demonstration.
    - Parameters:
        - `commits`: A list of `Commit` objects.
        - `issue_tool_url`: The base URL of the issue tracking tool.
        - `issue_tool_api_key`: API key for the issue tracking tool."""
    for c in commits:
        if c.issue:
            c.tracker = "STUB"
            c.issue_title = "STUB"


def fill_commits_info_redmine(
        commits: list[Commit],
        issue_tool_url: str,
        issue_tool_api_key: str,
        chunk_size: int = 100,
) -> None:
    """`fill_commits_info_redmine`

    Extracts detailed information about Redmine issues and updates the commits list.
    - Parameters:
        - `commits`: A list of `Commit` objects.
        - `issue_tool_url`: The base URL of the Redmine instance.
        - `issue_tool_api_key`: API key for Redmine.
        - `chunk_size` (Optional): The batch size for fetching issues in bulk.
    """
    batch: list[Commit] = []
    unique_issues: set[str] = set()
    for i in range(len(commits)):
        if unique_issues and (len(unique_issues) >= chunk_size or i == len(commits) - 1):
            fill_commits_info_redmine_batch(batch, issue_tool_url, issue_tool_api_key)
            batch = []
            unique_issues = set()
        elif commits[i].issue:
            batch.append(commits[i])
            unique_issues.add(commits[i].issue)


def fill_commits_info_redmine_batch(
        commits: list[Commit], issue_tool_url: str, issue_tool_api_key: str
) -> None:
    """`fill_commits_info_redmine_batch`

    Helper function that processes information for a batch of commits with known issues from Redmine.
    - Parameters:
        - `commits`: A list of `Commit` objects for a specific batch.
        - `issue_tool_url`: The base URL of the Redmine instance.
        - `issue_tool_api_key`: API key for Redmine.
    """
    commits_with_known_issues = list(filter(lambda c: c.issue, commits))
    commit_groups_by_issues = defaultdict(list)
    for c in commits_with_known_issues:
        commit_groups_by_issues[c.issue].append(c)

    if not commits_with_known_issues:
        return None

    request_url: str = f"/issues.json?issue_id={','.join(set(map(lambda i: i.issue, commits_with_known_issues)))}&limit={len(commit_groups_by_issues.keys())}&status_id=*"
    conn: HTTPSConnection = HTTPSConnection(issue_tool_url)
    print(f"[REQUEST]: curl https://{issue_tool_url}{request_url}")
    conn.request(
        "GET",
        request_url,
        headers={"X-Redmine-API-Key": issue_tool_api_key},
    )
    response: HTTPResponse = conn.getresponse()
    result: bytes = response.read()
    conn.close()
    if response.status != 200:
        print(
            f"[WARN]: Error while getting issue info from redmine: STATUS: {response.status} REASON: {response.reason} BODY: {response.read()}"
        )
    result_json = json.loads(result)
    for issue in result_json["issues"]:
        for commit in commit_groups_by_issues[str(issue["id"])]:
            commit.tracker = issue["tracker"]["name"]
            commit.issue_title = issue["subject"]


def version_cmp(v1: str, v2: str, mode: VersionCompareMode) -> int:
    if not v1 and not v2:
        return 0
    if not v1:
        return -1
    if not v2:
        return 1
    if mode == VersionCompareMode.full or mode == VersionCompareMode.labels:
        lv1 = version.parse(v1)
        lv2 = version.parse(v2)
        return 0 if lv1 == lv2 else -1 if lv1 < lv2 else 1

    component_re = re.compile(r'(\d+ | [a-z]+ | \.)', re.VERBOSE)
    c1 = [x for x in component_re.split(v1) if x and x != '.']
    c2 = [x for x in component_re.split(v2) if x and x != '.']

    version_numbers: int = 1 if mode == VersionCompareMode.major else 2 if mode == VersionCompareMode.minor else 3
    for i in range(version_numbers):
        if len(c1) < i + 1 or len(c2) < i + 1:
            return 0 if len(c1) == len(c2) else -1 if len(c1) < len(c2) else 1
        if c1[i] < c2[i]:
            return -1
        if c1[i] > c2[i]:
            return 1
    return 0


def version_trim(version: str, mode: VersionCompareMode) -> str:
    if mode == VersionCompareMode.full or mode == VersionCompareMode.labels:
        return version
    if mode == VersionCompareMode.major:
        return version.split(".", maxsplit=1)[0]
    if mode == VersionCompareMode.minor:
        return ".".join(version.split(".", maxsplit=2)[0:2])
    if mode == VersionCompareMode.patch:
        return ".".join(version.split(".", maxsplit=3)[0:3])


def sort_inside_versions(commits: list[Commit], version_cmp_mode: VersionCompareMode) -> None:
    """`sort_inside_versions`

    Sorts commits within each version group primarily by tracker, issue, and date.
    - Parameters:
        - `commits`: A list of `Commit` objects.
    """
    if len(commits) == 0:
        return
    version: str = commits[0].version
    version_begin_idx: int = 0
    for i in range(len(commits)):
        if version_cmp(commits[i].version, version, version_cmp_mode) != 0 or i == len(commits) - 1:
            version_end_idx: int = i if i == len(commits) - 1 else i - 1
            commits[version_begin_idx:version_end_idx] = sorted(
                commits[version_begin_idx:version_end_idx],
                key=lambda c: (
                    c.tracker + "." + c.issue + "." + c.date
                    if c.tracker
                    else chr(sys.maxunicode)
                ),
            )
            version_begin_idx = i
            version = commits[i].version


def filterout_none_issue(commits: list[Commit]) -> list[Commit]:
    """`filterout_none_issue`

    Filters out commits without issue information.
    - Parameters:
        - `commits`: A list of `Commit` objects.
    - Returns: A list of `Commit` objects that have issue information."""
    return filter(lambda c: c.tracker and c.issue, commits)


def build_changelog(
        commits: list[Commit],
        issue_tool_url: str,
        version_control_commit_url: str,
        version_cmp_mode: VersionCompareMode
) -> str:
    """`build_changelog`

    Builds a comprehensive changelog from a list of detailed commit objects.
    - Parameters:
        - `commits`: A list of `Commit` objects, ideally with detailed issue information.
        - `issue_tool_url`: Base URL for the issue tracker to link issues.
        - `version_control_commit_url`: Base URL for linking to specific commits.
    - Returns: A string containing the formatted changelog.
    """
    commits_reversed = list(reversed(commits))
    changelog: str = """
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
"""
    version, tracker, issue = ["", "", ""]
    mod_count: int = 0
    version_date = ""
    for i in range(len(commits_reversed)):
        version_date = max(commits_reversed[i].date[:10], version_date)
        print(
            f"[INFO] building changelog: {int((i / len(commits_reversed)) * 100)}%",
            end="\r",
        )
        expected_mod_count = mod_count
        if version_cmp(version, commits_reversed[i].version, version_cmp_mode) != 0 or mod_count != expected_mod_count:
            changelog = changelog.replace("%version_date%", version_date)
            version_date = ""
            changelog += "\n\n"
            version = commits_reversed[i].version
            mod_count += 1
            changelog += f"""## [{version_trim(version, version_cmp_mode)}] - %version_date%"""
        if tracker != commits_reversed[i].tracker or mod_count != expected_mod_count:
            changelog += "\n\n"
            tracker = commits_reversed[i].tracker
            mod_count += 1
            changelog += f"### {tracker}"
        if issue != commits_reversed[i].issue or mod_count != expected_mod_count:
            changelog += "\n\n"
            issue = commits_reversed[i].issue
            mod_count += 1
            changelog += f"- [#{issue}](https://{issue_tool_url}/issues/{issue})  {commits_reversed[i].issue_title} commits: "

        changelog += f" [{commits_reversed[i].sha}]({version_control_commit_url}{commits_reversed[i].sha})"
    changelog = changelog.replace("%version_date%", version_date)
    return changelog


def find_version_container_changes(
        git_directory: str,
        version_container: str,
        version_parser: Callable[[str], str],
        version_cmp_mode: VersionCompareMode
) -> list[Commit]:
    """`find_version_container_changes`
    
    Identifies commits where a version change occurs based on a version file.
    - Parameters:
        - `git_directory`: Path to the git repository.
        - `version_container`: Name/type of the version file.
        - `version_parser`: A function to parse the version from the file content.
    - Returns: A list of `Commit` objects representing version changes.
    """
    previous_version: str = ""
    version_container_changes: list[Commit] = []
    for commit_record in git_log_array(git_directory, version_container):
        sha, title, date = commit_record.split("\n", 2)
        error, result = git_show(git_directory, sha, version_container)
        version: str = ""
        if not error:
            version = version_parser(result)
        # TODO: make error message condition independent from system locale
        elif "exists on disk, but not in" in error:
            version = "0.0"
        else:
            print(f"[ERROR]: {error}")
            exit(1)
        if version_cmp(version, previous_version, version_cmp_mode) != 0:
            version_container_changes.append(Commit(sha, title, date, version))
            previous_version = version
    print(
        f"[INFO]: found versions {list(map(lambda v: v.version, version_container_changes))}"
    )
    return version_container_changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.add_argument("--issue-parser", required=True,)
    parser.add_argument(
        "--issue-tracker-type",
        required=False,
        help="Issue tracker type. Only redmine is supported now",
    )
    parser.add_argument(
        "--issue-tracker-url", required=True, help="Issue tracker base address"
    )
    parser.add_argument(
        "--issue-tracker-token", required=True, help="Issue tracker token or api key"
    )
    parser.add_argument(
        "--version-control-system-commit-url",
        required=True,
        help="Commit url used in changelog",
    )
    parser.add_argument(
        "-C",
        "--repository-path",
        required=False,
        help="Path to git directory. Current workong directory used by default.",
        default="",
    )
    parser.add_argument(
        "--version-container-type",
        required=False,
        help="Version container. Some bill of materials or properties file that contains application version. "
             "Name of this file and it's structure should stay same along all git log history.",
        type=VersionContainer,
        choices=list(VersionContainer),
        default=VersionContainer.maven,
    )
    parser.add_argument(
        "-o",
        "--output-file",
        required=False,
        help="Target file",
        default="CHANGELOG.md",
    )
    parser.add_argument("--version-container-path", required=False, default="pom.xml")
    parser.add_argument(
        "--version-compare-mode",
        help="Version comparison mode. Perform the comparison up to specified version component and ignore others. "
             "It's useful for example if dev-branch contains patches or labels like `-alpha` or `-rc.0` and you want "
             "to include these changes to changelog file but do not separate it by different versions.",
        required=False,
        type=VersionCompareMode,
        choices=list(VersionCompareMode),
        default=VersionCompareMode.full,
    )
    # parser.add_argument("--log-level", required=False,) ## DEBUG -> CMD -> INFO -> WARN -> ERROR
    # parser.add_argument("--version-include", required=False, default=".*")
    # parser.add_argument("--version-exclude", required=False, default=".*")
    # parser.add_argument("--yanked-filter", required=False,)
    args = parser.parse_args()

    check_system_requirements()

    version_container_parser: dict[VersionContainer, Callable[[str], str]] = {
        VersionContainer.maven: parse_version_maven,
        VersionContainer.npm: parse_version_npm,
        VersionContainer.env: parse_version_env,
    }

    error, is_shallow = git_is_shallow(args.repository_path)
    if not error and is_shallow:
        print(f"[WARN] The repository {args.repository_path} is shallow clone. It's important to not use shallow "
              f"clones to build changelog.")
    elif error:
        print(f"[ERROR]: {error}")
        exit(1)

    version_container_changes = find_version_container_changes(
        args.repository_path,
        args.version_container_path,
        version_container_parser.get(args.version_container_type),
        args.version_compare_mode
    )

    error, head_sha = git_head_sha(args.repository_path)
    if error:
        print(f"[ERROR]: {error}")
        exit(1)

    detailed_commits: list[Commit] = []
    for i in range(len(version_container_changes)):
        for commit_record in git_log_array(
                args.repository_path,
                from_sha=version_container_changes[i].sha,
                to_sha=version_container_changes[i + 1].sha if i + 1 < len(version_container_changes) else head_sha,
        )[:-1]:
            sha, title, date = commit_record.split("\n", 2)
            issue: str = parse_issue_redmine(title)
            detailed_commits.append(
                Commit(sha, title, date, version_container_changes[i].version, issue)
            )

    fill_commits_info_redmine(
        detailed_commits, args.issue_tracker_url, args.issue_tracker_token
    )

    sort_inside_versions(detailed_commits, args.version_compare_mode)

    filtered_commits = list(filterout_none_issue(detailed_commits))

    changelog = build_changelog(
        filtered_commits, args.issue_tracker_url, args.version_control_system_commit_url, args.version_compare_mode
    )

    with open(args.output_file, "w") as f:
        f.write(changelog)