"""
Agent Tools - Email and Git tool wrappers for autonomous agent
Provides email and git functionality with proper error handling and logging
"""

import logging
from typing import Dict, Any, Optional, List
from .email_manager import get_email_manager
from .git_manager import get_git_manager

logger = logging.getLogger('assaultron.agent_tools')


# ============================================================================
# EMAIL TOOLS
# ============================================================================

def send_email(
    to: str,
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    add_signature: bool = True
) -> Dict[str, Any]:
    """
    Send an email via the AI's email account.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text email body
        body_html: Optional HTML email body
        cc: Optional list of CC recipients
        bcc: Optional list of BCC recipients
        add_signature: Whether to add automatic signature (default: True)

    Returns:
        Dict with success status and error message if failed
    """
    try:
        email_manager = get_email_manager()
        success, error = email_manager.send_email(
            to, subject, body, body_html, cc, bcc, add_signature
        )

        if success:
            logger.info(f"Email sent successfully to {to}")
            result = {
                "success": True,
                "to": to,
                "subject": subject,
                "message": "Email sent successfully"
            }
            if cc:
                result["cc"] = cc
            if bcc:
                result["bcc"] = f"{len(bcc)} recipient(s)"
            return result
        else:
            logger.error(f"Failed to send email: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Email tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def read_emails(folder: str = "INBOX", limit: int = 5, unread_only: bool = True) -> Dict[str, Any]:
    """
    Read emails from the AI's email account.

    Args:
        folder: Email folder to read from (default: INBOX)
        limit: Maximum number of emails to fetch (default: 5, max: 20)
        unread_only: Only fetch unread emails (default: True)

    Returns:
        Dict with success status, list of emails, or error message
    """
    try:
        # Limit to prevent overwhelming the agent
        limit = min(limit, 20)

        email_manager = get_email_manager()
        emails, error = email_manager.read_emails(folder, limit, unread_only)

        if error:
            logger.error(f"Failed to read emails: {error}")
            return {
                "success": False,
                "error": error
            }

        logger.info(f"Read {len(emails)} emails from {folder}")
        return {
            "success": True,
            "count": len(emails),
            "emails": emails,
            "folder": folder
        }

    except Exception as e:
        logger.exception(f"Email read tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_email_status() -> Dict[str, Any]:
    """
    Get the status of the email manager.

    Returns:
        Dict with email configuration and status
    """
    try:
        email_manager = get_email_manager()
        status = email_manager.get_status()
        return {
            "success": True,
            **status
        }
    except Exception as e:
        logger.exception(f"Email status tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def reply_to_email(
    email_id: str,
    reply_body: str,
    reply_body_html: Optional[str] = None,
    cc: Optional[List[str]] = None,
    folder: str = "INBOX"
) -> Dict[str, Any]:
    """
    Reply to an existing email.

    Args:
        email_id: ID of the email to reply to
        reply_body: Plain text reply body
        reply_body_html: Optional HTML reply body
        cc: Optional list of CC recipients
        folder: Email folder containing the original email

    Returns:
        Dict with success status and error message if failed
    """
    try:
        email_manager = get_email_manager()
        success, error = email_manager.reply_to_email(
            email_id, reply_body, reply_body_html, cc, folder
        )

        if success:
            logger.info(f"Reply sent successfully for email {email_id}")
            return {
                "success": True,
                "email_id": email_id,
                "message": "Reply sent successfully"
            }
        else:
            logger.error(f"Failed to reply to email: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Reply email tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def forward_email(
    email_id: str,
    to: str,
    forward_message: Optional[str] = None,
    cc: Optional[List[str]] = None,
    folder: str = "INBOX"
) -> Dict[str, Any]:
    """
    Forward an existing email to another recipient.

    Args:
        email_id: ID of the email to forward
        to: Recipient email address
        forward_message: Optional message to add before forwarded content
        cc: Optional list of CC recipients
        folder: Email folder containing the original email

    Returns:
        Dict with success status and error message if failed
    """
    try:
        email_manager = get_email_manager()
        success, error = email_manager.forward_email(
            email_id, to, forward_message, cc, folder
        )

        if success:
            logger.info(f"Email {email_id} forwarded successfully to {to}")
            return {
                "success": True,
                "email_id": email_id,
                "to": to,
                "message": "Email forwarded successfully"
            }
        else:
            logger.error(f"Failed to forward email: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Forward email tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# GIT TOOLS (MULTI-REPOSITORY SUPPORT)
# ============================================================================

def list_git_repositories() -> Dict[str, Any]:
    """
    List all Git repositories in the sandbox.

    Returns:
        Dict with success status and list of repositories
    """
    try:
        git_manager = get_git_manager()
        repos = git_manager.list_repositories()

        logger.info(f"Found {len(repos)} git repositories")
        return {
            "success": True,
            "count": len(repos),
            "repositories": repos
        }

    except Exception as e:
        logger.exception(f"List repositories tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def git_clone(repo_url: str, repo_path: str, use_ssh: bool = True) -> Dict[str, Any]:
    """
    Clone a repository into a specific sandbox folder.

    Args:
        repo_url: Repository URL (git@github.com:owner/repo.git or https://...)
        repo_path: Local path within sandbox (e.g., "my-project" or "projects/my-app")
        use_ssh: Use SSH authentication (default: True, requires SSH key setup)

    Returns:
        Dict with success status and error message if failed

    Example:
        git_clone("git@github.com:user/repo.git", "my-project")
        git_clone("https://github.com/user/repo.git", "projects/my-app", use_ssh=False)
    """
    try:
        git_manager = get_git_manager()

        # Ensure path is within sandbox
        from pathlib import Path
        sandbox_base = git_manager.sandbox_base
        full_path = str(Path(sandbox_base) / repo_path)

        success, error = git_manager.clone_repo(repo_url, full_path, use_ssh)

        if success:
            logger.info(f"Repository cloned to {repo_path}")
            return {
                "success": True,
                "repo_url": repo_url,
                "repo_path": full_path,
                "message": "Repository cloned successfully"
            }
        else:
            logger.error(f"Failed to clone repository: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Git clone tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def git_commit(repo_path: str, message: str, files: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Create a git commit in a specific repository.

    Args:
        repo_path: Path to repository (e.g., "my-project" or "projects/my-app")
        message: Commit message (must follow conventional commits format)
        files: Optional list of specific files to commit (None = commit all changes)

    Returns:
        Dict with success status and error message if failed

    Example commit messages:
        - feat(email): add email sending capability
        - fix(git): resolve SSH authentication issue
        - docs(readme): update setup instructions
        - refactor(agent): simplify tool registration

    Example:
        git_commit("my-project", "feat(api): add new endpoint")
        git_commit("my-project", "fix(bug): resolve issue", ["file1.py", "file2.py"])
    """
    try:
        git_manager = get_git_manager()

        # Ensure path is within sandbox
        from pathlib import Path
        sandbox_base = git_manager.sandbox_base
        full_path = str(Path(sandbox_base) / repo_path)

        success, error = git_manager.commit(full_path, message, files)

        if success:
            logger.info(f"Git commit created in {repo_path}: {message}")
            return {
                "success": True,
                "repo_path": repo_path,
                "message": message,
                "files": files or "all changes",
                "result": error if error else "Commit created successfully"
            }
        else:
            logger.error(f"Failed to create commit: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Git commit tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def git_push(repo_path: str, branch: str = "main") -> Dict[str, Any]:
    """
    Push commits to remote repository.

    Args:
        repo_path: Path to repository (e.g., "my-project" or "projects/my-app")
        branch: Branch name to push to (default: main)

    Returns:
        Dict with success status and error message if failed

    Example:
        git_push("my-project")
        git_push("my-project", "develop")
    """
    try:
        git_manager = get_git_manager()

        # Ensure path is within sandbox
        from pathlib import Path
        sandbox_base = git_manager.sandbox_base
        full_path = str(Path(sandbox_base) / repo_path)

        success, error = git_manager.push(full_path, branch)

        if success:
            logger.info(f"Pushed {repo_path} to {branch}")
            return {
                "success": True,
                "repo_path": repo_path,
                "branch": branch,
                "message": f"Successfully pushed to {branch}"
            }
        else:
            logger.error(f"Failed to push: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Git push tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def git_pull(repo_path: str, branch: str = "main") -> Dict[str, Any]:
    """
    Pull latest changes from remote repository.

    Args:
        repo_path: Path to repository (e.g., "my-project" or "projects/my-app")
        branch: Branch name to pull from (default: main)

    Returns:
        Dict with success status and error message if failed

    Example:
        git_pull("my-project")
        git_pull("my-project", "develop")
    """
    try:
        git_manager = get_git_manager()

        # Ensure path is within sandbox
        from pathlib import Path
        sandbox_base = git_manager.sandbox_base
        full_path = str(Path(sandbox_base) / repo_path)

        success, error = git_manager.pull(full_path, branch)

        if success:
            logger.info(f"Pulled {repo_path} from {branch}")
            return {
                "success": True,
                "repo_path": repo_path,
                "branch": branch,
                "message": f"Successfully pulled from {branch}"
            }
        else:
            logger.error(f"Failed to pull: {error}")
            return {
                "success": False,
                "error": error or "Unknown error"
            }

    except Exception as e:
        logger.exception(f"Git pull tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def git_status(repo_path: str) -> Dict[str, Any]:
    """
    Get git repository status.

    Args:
        repo_path: Path to repository (e.g., "my-project" or "projects/my-app")

    Returns:
        Dict with repository status including:
        - current branch
        - latest commit
        - modified files
        - untracked files
        - staged files

    Example:
        git_status("my-project")
    """
    try:
        git_manager = get_git_manager()

        # Ensure path is within sandbox
        from pathlib import Path
        sandbox_base = git_manager.sandbox_base
        full_path = str(Path(sandbox_base) / repo_path)

        status, error = git_manager.get_status(full_path)

        if error:
            logger.error(f"Failed to get git status: {error}")
            return {
                "success": False,
                "error": error
            }

        return {
            "success": True,
            **status
        }

    except Exception as e:
        logger.exception(f"Git status tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_git_config() -> Dict[str, Any]:
    """
    Get git manager configuration status.

    Returns:
        Dict with git configuration details
    """
    try:
        git_manager = get_git_manager()
        config = git_manager.get_config_status()
        return {
            "success": True,
            **config
        }
    except Exception as e:
        logger.exception(f"Git config tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# TOOL REGISTRY
# ============================================================================

# Dictionary of all agent tools with descriptions
AGENT_TOOLS = {
    # Email tools
    "send_email": {
        "function": send_email,
        "description": "Send an email to a recipient. Args: to (str), subject (str), body (str), body_html (optional str), cc (optional list), bcc (optional list), add_signature (bool, default True)",
        "category": "email"
    },
    "read_emails": {
        "function": read_emails,
        "description": "Read emails from inbox. Args: folder (str, default 'INBOX'), limit (int, default 5), unread_only (bool, default True)",
        "category": "email"
    },
    "get_email_status": {
        "function": get_email_status,
        "description": "Get email manager status and configuration. No arguments required.",
        "category": "email"
    },
    "reply_to_email": {
        "function": reply_to_email,
        "description": "Reply to an existing email. Args: email_id (str), reply_body (str), reply_body_html (optional str), cc (optional list), folder (str, default 'INBOX')",
        "category": "email"
    },
    "forward_email": {
        "function": forward_email,
        "description": "Forward an email to another recipient. Args: email_id (str), to (str), forward_message (optional str), cc (optional list), folder (str, default 'INBOX')",
        "category": "email"
    },

    # Git tools (multi-repository support)
    "list_git_repositories": {
        "function": list_git_repositories,
        "description": "List all git repositories in the sandbox. No arguments required. Returns list of repos with their paths and info.",
        "category": "git"
    },
    "git_clone": {
        "function": git_clone,
        "description": "Clone a repository into sandbox. Args: repo_url (str), repo_path (str, e.g. 'my-project'), use_ssh (bool, default True)",
        "category": "git"
    },
    "git_commit": {
        "function": git_commit,
        "description": "Create a git commit in a repo. Args: repo_path (str, e.g. 'my-project'), message (str, conventional format), files (optional list)",
        "category": "git"
    },
    "git_push": {
        "function": git_push,
        "description": "Push commits to remote. Args: repo_path (str, e.g. 'my-project'), branch (str, default 'main')",
        "category": "git"
    },
    "git_pull": {
        "function": git_pull,
        "description": "Pull latest changes from remote. Args: repo_path (str, e.g. 'my-project'), branch (str, default 'main')",
        "category": "git"
    },
    "git_status": {
        "function": git_status,
        "description": "Get git repository status. Args: repo_path (str, e.g. 'my-project'). Returns branch, commits, changed files.",
        "category": "git"
    },
    "get_git_config": {
        "function": get_git_config,
        "description": "Get git configuration status. No arguments required.",
        "category": "git"
    }
}


def get_tool_functions() -> Dict[str, Any]:
    """
    Get a dictionary of tool names to functions for agent registration.

    Returns:
        Dict mapping tool names to their functions
    """
    return {name: tool["function"] for name, tool in AGENT_TOOLS.items()}


def get_tool_descriptions() -> Dict[str, str]:
    """
    Get a dictionary of tool names to descriptions for agent prompts.

    Returns:
        Dict mapping tool names to their descriptions
    """
    return {name: tool["description"] for name, tool in AGENT_TOOLS.items()}
