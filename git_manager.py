"""
Git Manager for Assaultron AI
Provides secure Git operations with Discord logging and guardrails
MULTI-REPOSITORY SUPPORT: Work on different projects in different sandbox folders
Phases 3-5: GitHub Identity, Repository Access, SSH Authentication
"""

import os
import subprocess
import re
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import logging
import requests
import threading
from pathlib import Path


class GitRepository:
    """Represents a single Git repository with its context"""

    def __init__(self, repo_path: str, repo_url: Optional[str] = None,
                 owner: Optional[str] = None, name: Optional[str] = None):
        """
        Initialize a Git repository context

        Args:
            repo_path: Local path to repository (e.g., "./sandbox/my-project")
            repo_url: Remote repository URL (optional, can be detected)
            owner: Repository owner (optional, can be detected)
            name: Repository name (optional, can be detected)
        """
        self.repo_path = str(Path(repo_path).resolve())
        self.repo_url = repo_url
        self.owner = owner
        self.name = name

        # Detect repo info if not provided
        if os.path.exists(os.path.join(self.repo_path, '.git')):
            self._detect_repo_info()

    def _detect_repo_info(self):
        """Detect repository information from git config"""
        try:
            # Get remote URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self.repo_url = result.stdout.strip()

                # Parse owner and name from URL
                # Supports: git@github.com:owner/repo.git or https://github.com/owner/repo.git
                match = re.search(r'[:/]([^/]+)/([^/]+?)(\.git)?$', self.repo_url)
                if match:
                    self.owner = match.group(1)
                    self.name = match.group(2)

        except Exception:
            pass

    def get_display_name(self) -> str:
        """Get a human-readable name for this repository"""
        if self.owner and self.name:
            return f"{self.owner}/{self.name}"
        elif self.name:
            return self.name
        else:
            return os.path.basename(self.repo_path)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "path": self.repo_path,
            "url": self.repo_url,
            "owner": self.owner,
            "name": self.name,
            "display_name": self.get_display_name()
        }


class GitManager:
    """Manages AI Git operations with multi-repository support"""

    def __init__(self):
        # Git configuration from environment
        self.github_username = os.getenv("GITHUB_USERNAME", "")
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.ssh_key_path = os.getenv("SSH_KEY_PATH", "./ssh/ai_github_key")
        self.git_user_name = os.getenv("GIT_USER_NAME", "AI Bot")
        self.git_user_email = os.getenv("GIT_USER_EMAIL", "")
        self.enabled = os.getenv("GIT_ENABLED", "false").lower() == "true"
        self.require_commit_format = os.getenv("REQUIRE_COMMIT_MESSAGE_FORMAT", "true").lower() == "true"

        # Discord logging
        self.log_webhook_url = os.getenv("DISCORD_LOG_URL", "")

        # Sandbox base directory
        self.sandbox_base = os.getenv("SANDBOX_PATH", "./sandbox")

        # Logging
        self.logger = logging.getLogger('assaultron.git')
        self._git_lock = threading.Lock()

        # Commit message format pattern
        self.commit_message_pattern = re.compile(
            r'^(feat|fix|docs|style|refactor|test|chore|perf)(\(.+\))?: .{1,100}$',
            re.MULTILINE
        )

        # Repository cache (path -> GitRepository)
        self._repo_cache: Dict[str, GitRepository] = {}

        # Validation
        if self.enabled and not self._validate_config():
            self.logger.error("Git configuration incomplete - git functionality disabled")
            self.enabled = False

    def _validate_config(self) -> bool:
        """Validate Git configuration"""
        if not self.github_username:
            self.logger.error("GitHub username not configured")
            return False
        if not self.git_user_email:
            self.logger.error("Git user email not configured")
            return False
        if not self.log_webhook_url:
            self.logger.warning("Discord log webhook not configured - logging disabled")
        return True

    def _validate_repo_path(self, repo_path: str) -> Tuple[bool, str]:
        """
        Validate that repository path is within sandbox

        Args:
            repo_path: Path to validate

        Returns:
            (is_valid: bool, normalized_path: str)
        """
        try:
            # Resolve to absolute path
            abs_path = Path(repo_path).resolve()
            sandbox_abs = Path(self.sandbox_base).resolve()

            # Check if within sandbox
            try:
                abs_path.relative_to(sandbox_abs)
                return True, str(abs_path)
            except ValueError:
                self.logger.error(f"Repository path outside sandbox: {repo_path}")
                return False, ""

        except Exception as e:
            self.logger.error(f"Invalid repository path: {e}")
            return False, ""

    def _get_or_create_repo(self, repo_path: str) -> Optional[GitRepository]:
        """
        Get or create GitRepository object for a path

        Args:
            repo_path: Path to repository

        Returns:
            GitRepository object or None if invalid
        """
        # Validate path
        is_valid, normalized_path = self._validate_repo_path(repo_path)
        if not is_valid:
            return None

        # Check cache
        if normalized_path in self._repo_cache:
            return self._repo_cache[normalized_path]

        # Create new repository object
        repo = GitRepository(normalized_path)
        self._repo_cache[normalized_path] = repo
        return repo

    def _log_to_discord(self, action: str, details: Dict, success: bool = True, error: Optional[str] = None):
        """
        Log Git activity to Discord #logs channel

        Args:
            action: Action performed (e.g., "commit", "push", "clone")
            details: Details dict (repo, branch, message, etc.)
            success: Whether action succeeded
            error: Error message if failed
        """
        if not self.log_webhook_url:
            return

        try:
            # Create embed
            color = 0x00ff00 if success else 0xff0000  # Green for success, red for error

            # Build description
            description_parts = []
            for key, value in details.items():
                # Truncate long values
                if isinstance(value, str) and len(value) > 200:
                    value = value[:200] + "..."
                description_parts.append(f"**{key.title()}:** {value}")

            if error:
                description_parts.append(f"\n**Error:** {error}")

            description = "\n".join(description_parts)

            embed = {
                "title": f"🔧 Git {action.replace('_', ' ').title()}",
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": f"Assaultron AI - Git Manager"
                }
            }

            payload = {
                "username": "Assaultron AI - Git Log",
                "embeds": [embed]
            }

            response = requests.post(
                self.log_webhook_url,
                json=payload,
                timeout=5
            )

            if response.status_code not in [200, 204]:
                self.logger.error(f"Discord log webhook failed: {response.status_code}")

        except Exception as e:
            self.logger.exception(f"Failed to log to Discord: {e}")

    def _run_git_command(self, args: List[str], cwd: str) -> Tuple[bool, str, str]:
        """
        Run a git command safely

        Args:
            args: Git command arguments (e.g., ["status", "-s"])
            cwd: Working directory

        Returns:
            (success: bool, stdout: str, stderr: str)
        """
        try:
            # Ensure work directory exists
            os.makedirs(cwd, exist_ok=True)

            # Configure git if needed
            self._configure_git_user(cwd)

            # Run command
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_SSH_COMMAND": f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=no"}
            )

            success = result.returncode == 0
            return success, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return False, "", "Command timed out after 30 seconds"
        except Exception as e:
            return False, "", str(e)

    def _configure_git_user(self, cwd: str):
        """Configure git user name and email for the repository"""
        try:
            subprocess.run(
                ["git", "config", "user.name", self.git_user_name],
                cwd=cwd,
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["git", "config", "user.email", self.git_user_email],
                cwd=cwd,
                capture_output=True,
                timeout=5
            )
        except Exception as e:
            self.logger.warning(f"Failed to configure git user: {e}")

    def _validate_commit_message(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate commit message format

        Args:
            message: Commit message to validate

        Returns:
            (is_valid: bool, error_message: Optional[str])
        """
        if not self.require_commit_format:
            return True, None

        # Extract first line of commit message
        first_line = message.split('\n')[0].strip()

        if not self.commit_message_pattern.match(first_line):
            return False, (
                "Commit message must follow conventional commits format:\n"
                "type(scope?): description\n"
                "Types: feat, fix, docs, style, refactor, test, chore, perf\n"
                f"Example: feat(email): add email sending capability\n"
                f"Your message: {first_line}"
            )

        return True, None

    def list_repositories(self) -> List[Dict]:
        """
        List all Git repositories in the sandbox

        Returns:
            List of repository information dicts
        """
        repos = []

        try:
            # Walk through sandbox directory
            for root, dirs, files in os.walk(self.sandbox_base):
                # Check if this directory is a git repo
                if '.git' in dirs:
                    repo = self._get_or_create_repo(root)
                    if repo:
                        repos.append(repo.to_dict())

                    # Don't recurse into .git directories
                    dirs.remove('.git')

        except Exception as e:
            self.logger.exception(f"Failed to list repositories: {e}")

        return repos

    def clone_repo(self, repo_url: str, repo_path: str, use_ssh: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Clone a repository into a specific sandbox folder

        Args:
            repo_url: Repository URL (git@github.com:owner/repo.git or https://...)
            repo_path: Local path within sandbox (e.g., "./sandbox/my-project")
            use_ssh: Use SSH authentication (default: True)

        Returns:
            (success: bool, error_message: Optional[str])
        """
        if not self.enabled:
            return False, "Git functionality is disabled"

        # Validate and normalize path
        is_valid, normalized_path = self._validate_repo_path(repo_path)
        if not is_valid:
            return False, f"Invalid repository path: {repo_path}"

        with self._git_lock:
            try:
                # Create parent directory
                parent_dir = os.path.dirname(normalized_path)
                os.makedirs(parent_dir, exist_ok=True)

                # Convert URL if needed
                if use_ssh and repo_url.startswith("https://github.com/"):
                    # Convert HTTPS to SSH
                    match = re.search(r'https://github\.com/([^/]+)/(.+?)(?:\.git)?$', repo_url)
                    if match:
                        repo_url = f"git@github.com:{match.group(1)}/{match.group(2)}.git"
                elif not use_ssh and repo_url.startswith("git@github.com:"):
                    # Convert SSH to HTTPS
                    match = re.search(r'git@github\.com:([^/]+)/(.+?)(?:\.git)?$', repo_url)
                    if match:
                        repo_url = f"https://github.com/{match.group(1)}/{match.group(2)}.git"

                # Clone
                success, stdout, stderr = self._run_git_command(
                    ["clone", repo_url, normalized_path],
                    cwd=parent_dir
                )

                if success:
                    # Create repository object
                    repo = self._get_or_create_repo(normalized_path)

                    self._log_to_discord("clone", {
                        "repo": repo.get_display_name() if repo else "unknown",
                        "url": repo_url,
                        "path": normalized_path,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, success=True)

                    self.logger.info(f"Repository cloned successfully: {repo_url} -> {normalized_path}")
                    return True, None
                else:
                    error = stderr or stdout
                    self._log_to_discord("clone", {
                        "url": repo_url,
                        "path": normalized_path
                    }, success=False, error=error)
                    return False, error

            except Exception as e:
                error = str(e)
                self.logger.exception(f"Failed to clone repository: {e}")
                self._log_to_discord("clone", {
                    "url": repo_url,
                    "path": repo_path
                }, success=False, error=error)
                return False, error

    def commit(self, repo_path: str, message: str, files: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """
        Create a git commit in a specific repository

        Args:
            repo_path: Path to repository (e.g., "./sandbox/my-project")
            message: Commit message
            files: List of files to stage (None = stage all changes)

        Returns:
            (success: bool, error_message: Optional[str])
        """
        if not self.enabled:
            return False, "Git functionality is disabled"

        # Get repository
        repo = self._get_or_create_repo(repo_path)
        if not repo:
            return False, f"Invalid repository path: {repo_path}"

        # Validate commit message
        is_valid, error = self._validate_commit_message(message)
        if not is_valid:
            self._log_to_discord("commit", {
                "repo": repo.get_display_name(),
                "path": repo_path,
                "message": message,
                "status": "blocked"
            }, success=False, error=error)
            return False, error

        with self._git_lock:
            try:
                # Stage files
                if files:
                    for file in files:
                        success, stdout, stderr = self._run_git_command(["add", file], repo.repo_path)
                        if not success:
                            error = f"Failed to stage {file}: {stderr}"
                            self._log_to_discord("commit", {
                                "repo": repo.get_display_name(),
                                "message": message,
                                "files": str(files)
                            }, success=False, error=error)
                            return False, error
                else:
                    # Stage all changes
                    success, stdout, stderr = self._run_git_command(["add", "-A"], repo.repo_path)
                    if not success:
                        error = f"Failed to stage changes: {stderr}"
                        self._log_to_discord("commit", {
                            "repo": repo.get_display_name(),
                            "message": message
                        }, success=False, error=error)
                        return False, error

                # Commit
                success, stdout, stderr = self._run_git_command(["commit", "-m", message], repo.repo_path)

                if success:
                    # Get commit hash
                    _, commit_hash, _ = self._run_git_command(["rev-parse", "HEAD"], repo.repo_path)
                    commit_hash = commit_hash.strip()[:7]

                    self._log_to_discord("commit", {
                        "repo": repo.get_display_name(),
                        "path": repo_path,
                        "message": message,
                        "files": str(files) if files else "all changes",
                        "commit": commit_hash,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, success=True)

                    self.logger.info(f"Commit created in {repo.get_display_name()}: {commit_hash}")
                    return True, None
                else:
                    error = stderr or stdout
                    # Check if "nothing to commit" error
                    if "nothing to commit" in error.lower():
                        return True, "No changes to commit"

                    self._log_to_discord("commit", {
                        "repo": repo.get_display_name(),
                        "message": message
                    }, success=False, error=error)
                    return False, error

            except Exception as e:
                error = str(e)
                self.logger.exception(f"Failed to create commit: {e}")
                self._log_to_discord("commit", {
                    "repo": repo.get_display_name(),
                    "message": message
                }, success=False, error=error)
                return False, error

    def push(self, repo_path: str, branch: str = "main") -> Tuple[bool, Optional[str]]:
        """
        Push commits to remote repository

        Args:
            repo_path: Path to repository
            branch: Branch to push (default: main)

        Returns:
            (success: bool, error_message: Optional[str])
        """
        if not self.enabled:
            return False, "Git functionality is disabled"

        repo = self._get_or_create_repo(repo_path)
        if not repo:
            return False, f"Invalid repository path: {repo_path}"

        with self._git_lock:
            try:
                # Push
                success, stdout, stderr = self._run_git_command(["push", "origin", branch], repo.repo_path)

                if success:
                    self._log_to_discord("push", {
                        "repo": repo.get_display_name(),
                        "path": repo_path,
                        "branch": branch,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, success=True)

                    self.logger.info(f"Pushed {repo.get_display_name()} to {branch}")
                    return True, None
                else:
                    error = stderr or stdout
                    self._log_to_discord("push", {
                        "repo": repo.get_display_name(),
                        "branch": branch
                    }, success=False, error=error)
                    return False, error

            except Exception as e:
                error = str(e)
                self.logger.exception(f"Failed to push: {e}")
                self._log_to_discord("push", {
                    "repo": repo.get_display_name(),
                    "branch": branch
                }, success=False, error=error)
                return False, error

    def pull(self, repo_path: str, branch: str = "main") -> Tuple[bool, Optional[str]]:
        """
        Pull latest changes from remote repository

        Args:
            repo_path: Path to repository
            branch: Branch to pull (default: main)

        Returns:
            (success: bool, error_message: Optional[str])
        """
        if not self.enabled:
            return False, "Git functionality is disabled"

        repo = self._get_or_create_repo(repo_path)
        if not repo:
            return False, f"Invalid repository path: {repo_path}"

        with self._git_lock:
            try:
                success, stdout, stderr = self._run_git_command(["pull", "origin", branch], repo.repo_path)

                if success:
                    self._log_to_discord("pull", {
                        "repo": repo.get_display_name(),
                        "path": repo_path,
                        "branch": branch,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, success=True)

                    self.logger.info(f"Pulled {repo.get_display_name()} from {branch}")
                    return True, None
                else:
                    error = stderr or stdout
                    self._log_to_discord("pull", {
                        "repo": repo.get_display_name(),
                        "branch": branch
                    }, success=False, error=error)
                    return False, error

            except Exception as e:
                error = str(e)
                self.logger.exception(f"Failed to pull: {e}")
                self._log_to_discord("pull", {
                    "repo": repo.get_display_name(),
                    "branch": branch
                }, success=False, error=error)
                return False, error

    def get_status(self, repo_path: str) -> Tuple[Dict, Optional[str]]:
        """
        Get git repository status

        Args:
            repo_path: Path to repository

        Returns:
            (status_dict: Dict, error_message: Optional[str])
        """
        if not self.enabled:
            return {"enabled": False}, None

        repo = self._get_or_create_repo(repo_path)
        if not repo:
            return {}, f"Invalid repository path: {repo_path}"

        try:
            # Get status
            success, stdout, stderr = self._run_git_command(["status", "--porcelain"], repo.repo_path)
            if not success:
                return {}, stderr

            # Get current branch
            success_branch, branch, _ = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo.repo_path)
            current_branch = branch.strip() if success_branch else "unknown"

            # Get latest commit
            success_commit, commit, _ = self._run_git_command(["log", "-1", "--pretty=format:%h - %s"], repo.repo_path)
            latest_commit = commit.strip() if success_commit else "No commits"

            # Parse status
            lines = stdout.strip().split('\n') if stdout.strip() else []
            modified = [line[3:] for line in lines if line.startswith(' M')]
            untracked = [line[3:] for line in lines if line.startswith('??')]
            staged = [line[3:] for line in lines if line[0] in ['A', 'M', 'D']]

            status = {
                "enabled": True,
                "repo": repo.get_display_name(),
                "path": repo_path,
                "branch": current_branch,
                "latest_commit": latest_commit,
                "modified_files": modified,
                "untracked_files": untracked,
                "staged_files": staged,
                "has_changes": bool(lines)
            }

            return status, None

        except Exception as e:
            self.logger.exception(f"Failed to get status: {e}")
            return {}, str(e)

    def get_config_status(self) -> Dict:
        """Get Git manager configuration status"""
        return {
            "enabled": self.enabled,
            "github_username": self.github_username if self.enabled else "Not configured",
            "git_user_name": self.git_user_name,
            "git_user_email": self.git_user_email if self.enabled else "Not configured",
            "ssh_key_path": self.ssh_key_path,
            "sandbox_base": self.sandbox_base,
            "commit_format_required": self.require_commit_format,
            "logging_enabled": bool(self.log_webhook_url),
            "repositories_count": len(self._repo_cache)
        }


# Global instance
git_manager = None


def get_git_manager() -> GitManager:
    """Get or create global git manager instance"""
    global git_manager
    if git_manager is None:
        git_manager = GitManager()
    return git_manager
