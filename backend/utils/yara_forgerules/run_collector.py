"""
This module contains functions for retrieving YARA rules from online repositories.
"""

import datetime
import os
import shutil
import time

import plyara
from git import Repo


def safe_rmtree_contents(path, retries=5, delay=1):
    """Attempt to remove the contents of a directory, retrying if it is busy."""
    for i in range(retries):
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            return
        except OSError as e:
            if e.errno == 16:  # Device or resource busy
                time.sleep(delay)
            else:
                raise
    raise e


def retrieve_yara_rule_sets(repo_staging_dir, yara_repos, logs):
    # The list of YARA rule sets of all repositories
    yara_rule_repo_sets = []

    # Check if the directory exists
    if os.path.exists(repo_staging_dir):
        try:
            # Remove the existing repo directory and all its contents
            logs("Info", f"Removing existing repo directory: {repo_staging_dir}")
            safe_rmtree_contents(repo_staging_dir)
        except Exception as e:
            logs(
                "Error",
                f"Failed to remove existing repo directory: {repo_staging_dir}. Error: {e}",
            )
            pass

    # Loop over the repositories
    for repo in yara_repos:
        logs("Info", f"Processing repository: {repo['name']}")

        # Extract the owner and the repository name from the URL
        repo_url_parts = repo["url"].split("/")
        repo["owner"] = repo_url_parts[3]
        repo["repo"] = repo_url_parts[4].split(".")[0]

        # If the repository hasn't not been cloned yet, clone it
        if not os.path.exists(
            os.path.join(repo_staging_dir, repo["owner"], repo["repo"])
        ):
            logs("Info", f"Cloning repository: {repo['url']}")

            # Clone the repository
            repo_folder = os.path.join(repo_staging_dir, repo["owner"], repo["repo"])
            try:
                repo["commit_hash"] = Repo.clone_from(
                    repo["url"], repo_folder, branch=repo["branch"]
                ).head.commit.hexsha
                logs("Info", f"Repository cloned successfully to: {repo_folder}")
            except Exception as e:
                logs("Error", f"Failed to clone repository: {repo['url']}. Error: {e}")
                continue  # Skip to the next repository if cloning fails
        else:
            # Get the latest commit hash
            repo_folder = os.path.join(repo_staging_dir, repo["owner"], repo["repo"])
            try:
                repo["commit_hash"] = Repo(repo_folder).head.commit.hexsha
                logs(
                    "Info",
                    f"Repository already exists at: {repo_folder}. Using latest commit.",
                )
            except Exception as e:
                logs(
                    "Error",
                    f"Failed to retrieve latest commit for repository: {repo['url']}. Error: {e}",
                )
                continue  # Skip to the next repository if getting commit fails

        # Walk through the extracted folders and find a LICENSE file
        # and save it into the repository object
        repo["license"] = "NO LICENSE SET"
        repo["license_url"] = "N/A"
        for root, dir, files in os.walk(repo_folder):
            for file in files:
                if file == "LICENSE" or file == "LICENSE.txt" or file == "LICENSE.md":
                    file_path = os.path.join(root, file)
                    url_path = os.path.relpath(file_path, start=repo_folder)
                    if (
                        root == repo_folder
                    ):  # Check if the file is in the root directory
                        repo["license_url"] = (
                            f'{repo["url"]}/blob/{repo["commit_hash"]}/{url_path}'
                        )
                        with open(file_path, "r", encoding="utf-8") as f:
                            repo["license"] = f.read()
                        break  # if we found the license in the root directory, we don't need to look further
                    elif (
                        "license_url" not in repo
                    ):  # If the file is not in the root directory and no license has been found yet
                        repo["license_url"] = (
                            f'{repo["url"]}/blob/{repo["commit_hash"]}/{url_path}'
                        )
                        with open(file_path, "r", encoding="utf-8") as f:
                            repo["license"] = f.read()

        # Walk through the extracted folders and find all YARA files
        yara_rule_sets = []
        walk_folder = repo_folder
        if "path" in repo:
            walk_folder = os.path.join(repo_folder, repo["path"])
        for root, _, files in os.walk(walk_folder):
            for file in files:
                if file.endswith(".yar") or file.endswith(".yara"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        yara_file_content = f.read()
                        try:
                            # Get the rule file path in the repository
                            relative_path = os.path.relpath(
                                file_path, start=repo_folder
                            )
                            # Parse the YARA rules in the file
                            yara_parser = plyara.Plyara()
                            yara_rules = yara_parser.parse_string(yara_file_content)
                            yara_rule_set = {
                                "rules": yara_rules,
                                "file_path": relative_path,
                            }
                            yara_rule_sets.append(yara_rule_set)
                        except Exception as e:
                            logs(
                                "Error",
                                f"Failed to parse YARA rules from file: {file_path}. Error: {e}",
                            )

        # Append the YARA rule repository
        yara_rule_repo = {
            "name": repo["name"],
            "url": repo["url"],
            "author": repo["author"],
            "owner": repo["owner"],
            "repo": repo["repo"],
            "branch": repo["branch"],
            "rules_sets": yara_rule_sets,
            "license": repo["license"],
            "license_url": repo["license_url"],
            "commit_hash": repo["commit_hash"],
            "retrieval_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "repo_path": repo_folder,
        }
        yara_rule_repo_sets.append(yara_rule_repo)

    # Return the YARA rule sets
    return yara_rule_repo_sets