"""
This module contains functions for retrieving YARA rules from online repositories.
"""

import datetime
import logging
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
                logging.warning(
                    f"Contents of directory {path} are busy, retrying in {delay} seconds..."
                )
                time.sleep(delay)
            else:
                raise
    logging.error(
        f"Failed to remove contents of directory {path} after {retries} attempts"
    )
    raise e


def retrieve_yara_rule_sets(repo_staging_dir, yara_repos):
    # The list of YARA rule sets of all repositories
    yara_rule_repo_sets = []

    # Check if the directory exists
    if os.path.exists(repo_staging_dir):
        try:
            # Remove the existing repo directory and all its contents
            safe_rmtree_contents(repo_staging_dir)
        except Exception as e:
            logging.error(f"Error removing contents of directory: {e}")

    # Loop over the repositories
    for repo in yara_repos:

        # Output the repository information to the console in a single line
        logging.info("Retrieving YARA rules from repository: %s", repo["name"])

        # Extract the owner and the repository name from the URL
        repo_url_parts = repo["url"].split("/")
        repo["owner"] = repo_url_parts[3]
        repo["repo"] = repo_url_parts[4].split(".")[0]

        # If the repository hasn't not been cloned yet, clone it
        if not os.path.exists(
            os.path.join(repo_staging_dir, repo["owner"], repo["repo"])
        ):
            # Clone the repository
            repo_folder = os.path.join(repo_staging_dir, repo["owner"], repo["repo"])
            repo["commit_hash"] = Repo.clone_from(
                repo["url"], repo_folder, branch=repo["branch"]
            ).head.commit.hexsha
        else:
            # Get the latest commit hash
            repo_folder = os.path.join(repo_staging_dir, repo["owner"], repo["repo"])
            repo["commit_hash"] = Repo(repo_folder).head.commit.hexsha

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
        # Walk a sub folder if one is set in the config
        walk_folder = repo_folder
        if "path" in repo:
            walk_folder = os.path.join(repo_folder, repo["path"])
        # Walk the folder and find all YARA files
        for root, _, files in os.walk(walk_folder):
            for file in files:
                if file.endswith(".yar") or file.endswith(".yara"):
                    file_path = os.path.join(root, file)

                    # Debug output
                    logging.debug("Found YARA rule file: %s", file_path)

                    # Read the YARA file
                    with open(file_path, "r", encoding="utf-8") as f:
                        yara_file_content = f.read()
                        # Parse the rules in the file
                        try:
                            # Get the rule file path in the repository
                            relative_path = os.path.relpath(
                                file_path, start=repo_folder
                            )
                            # Parse the YARA rules in the file
                            yara_parser = plyara.Plyara()
                            yara_rules = yara_parser.parse_string(yara_file_content)
                            # Create a YARA rule set object
                            yara_rule_set = {
                                "rules": yara_rules,
                                "file_path": relative_path,
                            }
                            # Debug output
                            logging.debug(
                                "Found %d YARA rules in file: %s",
                                len(yara_rules),
                                file_path,
                            )
                            # Append to list of YARA rule sets
                            yara_rule_sets.append(yara_rule_set)

                        except Exception as e:
                            print(e)
                            logging.error(
                                "Skipping YARA rule in the following "
                                "file because of a syntax error: %s ",
                                file_path,
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
            "quality": repo["quality"],
            "license": repo["license"],
            "license_url": repo["license_url"],
            "commit_hash": repo["commit_hash"],
            "retrieval_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "repo_path": repo_folder,
        }
        yara_rule_repo_sets.append(yara_rule_repo)

        # Output the number of YARA rules retrieved from the repository
        logging.info(
            "Retrieved %d YARA rules from repository: %s",
            len(yara_rule_sets),
            repo["name"],
        )

    # Return the YARA rule sets
    return yara_rule_repo_sets
