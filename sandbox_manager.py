"""
Sandbox Manager - Secure file and command execution for autonomous agent

This module provides a safe environment for the AI agent to:
- Create and edit files
- Run system commands
- Perform file operations

All operations are restricted to SANDBOX_PATH defined in .env
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger('assaultron.sandbox')


class SandboxManager:
    """
    Manages secure file and command operations within a sandboxed directory.
    
    All operations are restricted to SANDBOX_PATH to prevent destructive actions
    outside the designated area.
    """
    
    def __init__(self, sandbox_path: str):
        """
        Initialize sandbox manager.
        
        Args:
            sandbox_path: Absolute path to sandbox directory
        """
        self.sandbox_path = Path(sandbox_path).resolve()
        
        # Create sandbox if it doesn't exist
        if not self.sandbox_path.exists():
            self.sandbox_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created sandbox directory: {self.sandbox_path}")
        
        logger.info(f"Sandbox initialized at: {self.sandbox_path}")
    
    def _validate_path(self, path: str) -> Path:
        """
        Validate that a path is within the sandbox.
        
        Args:
            path: Path to validate (relative or absolute)
            
        Returns:
            Resolved absolute path within sandbox
            
        Raises:
            ValueError: If path escapes sandbox
        """
        # Convert to Path and resolve
        if os.path.isabs(path):
            resolved = Path(path).resolve()
        else:
            resolved = (self.sandbox_path / path).resolve()
        
        # Check if path is within sandbox
        try:
            resolved.relative_to(self.sandbox_path)
        except ValueError:
            raise ValueError(f"Path '{path}' is outside sandbox: {self.sandbox_path}")
        
        return resolved
    
    def create_folder(self, name: str) -> Dict[str, Any]:
        """
        Create a folder in the sandbox.
        
        Args:
            name: Folder name or relative path
            
        Returns:
            Result dictionary with success status and message
        """
        try:
            folder_path = self._validate_path(name)
            folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created folder: {folder_path}")
            return {
                "success": True,
                "message": f"Folder created: {folder_path.relative_to(self.sandbox_path)}",
                "path": str(folder_path)
            }
        except Exception as e:
            logger.error(f"Failed to create folder '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_file(self, name: str, content: str = "") -> Dict[str, Any]:
        """
        Create a file in the sandbox.
        
        Args:
            name: File name or relative path
            content: File content
            
        Returns:
            Result dictionary with success status and message
        """
        try:
            file_path = self._validate_path(name)
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"Created file: {file_path} ({len(content)} bytes)")
            return {
                "success": True,
                "message": f"File created: {file_path.relative_to(self.sandbox_path)}",
                "path": str(file_path),
                "size": len(content)
            }
        except Exception as e:
            logger.error(f"Failed to create file '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def edit_file(self, name: str, edits: str) -> Dict[str, Any]:
        """
        Edit an existing file in the sandbox.
        
        Args:
            name: File name or relative path
            edits: New content to write (replaces entire file)
            
        Returns:
            Result dictionary with success status and message
        """
        try:
            file_path = self._validate_path(name)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path.relative_to(self.sandbox_path)}"
                }
            
            # Write new content
            file_path.write_text(edits, encoding='utf-8')
            logger.info(f"Edited file: {file_path} ({len(edits)} bytes)")
            return {
                "success": True,
                "message": f"File edited: {file_path.relative_to(self.sandbox_path)}",
                "path": str(file_path),
                "size": len(edits)
            }
        except Exception as e:
            logger.error(f"Failed to edit file '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def read_file(self, name: str) -> Dict[str, Any]:
        """
        Read a file from the sandbox.
        
        Args:
            name: File name or relative path
            
        Returns:
            Result dictionary with file content
        """
        try:
            file_path = self._validate_path(name)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path.relative_to(self.sandbox_path)}"
                }
            
            content = file_path.read_text(encoding='utf-8')
            logger.info(f"Read file: {file_path} ({len(content)} bytes)")
            return {
                "success": True,
                "content": content,
                "path": str(file_path),
                "size": len(content)
            }
        except Exception as e:
            logger.error(f"Failed to read file '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_file(self, name: str) -> Dict[str, Any]:
        """
        Delete a file from the sandbox.
        
        Args:
            name: File name or relative path
            
        Returns:
            Result dictionary with success status
        """
        try:
            file_path = self._validate_path(name)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path.relative_to(self.sandbox_path)}"
                }
            
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
            return {
                "success": True,
                "message": f"File deleted: {file_path.relative_to(self.sandbox_path)}"
            }
        except Exception as e:
            logger.error(f"Failed to delete file '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_file_exists(self, name: str) -> Dict[str, Any]:
        """
        Check if a file or folder exists in the sandbox.
        
        Args:
            name: File/folder name or relative path
            
        Returns:
            Result dictionary with existence status
        """
        try:
            path = self._validate_path(name)
            exists = path.exists()
            is_file = path.is_file() if exists else False
            is_dir = path.is_dir() if exists else False
            
            return {
                "success": True,
                "exists": exists,
                "is_file": is_file,
                "is_directory": is_dir,
                "path": str(path.relative_to(self.sandbox_path))
            }
        except Exception as e:
            logger.error(f"Failed to check existence of '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_files(self, directory: str = ".") -> Dict[str, Any]:
        """
        List files and folders in a directory.
        
        Args:
            directory: Directory path (relative to sandbox)
            
        Returns:
            Result dictionary with file list
        """
        try:
            dir_path = self._validate_path(directory)
            
            if not dir_path.exists():
                return {
                    "success": False,
                    "error": f"Directory does not exist: {dir_path.relative_to(self.sandbox_path)}"
                }
            
            if not dir_path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {dir_path.relative_to(self.sandbox_path)}"
                }
            
            items = []
            for item in dir_path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            return {
                "success": True,
                "directory": str(dir_path.relative_to(self.sandbox_path)),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            logger.error(f"Failed to list directory '{directory}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def run_command(self, cmd: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run a system command in the sandbox directory.
        
        Args:
            cmd: Command to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Result dictionary with stdout, stderr, and return code
        """
        try:
            logger.info(f"Executing command in sandbox: {cmd}")
            
            # Run command in sandbox directory
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.sandbox_path),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            logger.info(f"Command completed with return code: {result.returncode}")
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": cmd
            }
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s: {cmd}")
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "command": cmd
            }
        except Exception as e:
            logger.error(f"Failed to execute command '{cmd}': {e}")
            return {
                "success": False,
                "error": str(e),
                "command": cmd
            }


# Example usage and testing
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize sandbox
    sandbox = SandboxManager("./sandbox")
    
    # Test operations
    print("=== Testing Sandbox Manager ===\n")
    
    # Create folder
    result = sandbox.create_folder("test_project")
    print(f"Create folder: {result}\n")
    
    # Create file
    result = sandbox.create_file("test_project/hello.txt", "Hello from sandbox!")
    print(f"Create file: {result}\n")
    
    # Read file
    result = sandbox.read_file("test_project/hello.txt")
    print(f"Read file: {result}\n")
    
    # Check existence
    result = sandbox.check_file_exists("test_project/hello.txt")
    print(f"File exists: {result}\n")
    
    # List files
    result = sandbox.list_files("test_project")
    print(f"List files: {result}\n")
    
    # Run command
    result = sandbox.run_command("dir" if os.name == 'nt' else "ls -la")
    print(f"Run command: {result}\n")
