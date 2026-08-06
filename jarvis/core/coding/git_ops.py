"""
Git Operations — version control integration.
=============================================
Provides git commands for the coding agent: commit, branch, diff, log, etc.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GitOps:
    """Git integration for the coding agent.

    Wraps git CLI commands for repository management, commit operations,
    branching, and history analysis.
    """

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command and return the result."""
        cmd = ["git", "-C", str(self.repo_path)] + list(args)
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=check,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git command timed out: {' '.join(cmd)}")
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not in PATH")

    def is_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        result = self._run("rev-parse", "--is-inside-work-tree", check=False)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def init(self) -> dict[str, Any]:
        """Initialize a new git repository."""
        result = self._run("init")
        return {"success": True, "output": result.stdout.strip()}

    def status(self) -> dict[str, Any]:
        """Get repository status."""
        result = self._run("status", "--porcelain")
        lines = [l for l in result.stdout.strip().split("\n") if l]

        staged, modified, untracked = [], [], []
        for line in lines:
            status_code = line[:2]
            file_path = line[3:]
            if status_code[0] in "MADRC":
                staged.append(file_path)
            elif status_code[1] == "M":
                modified.append(file_path)
            elif status_code == "??":
                untracked.append(file_path)

        branch_result = self._run("branch", "--show-current", check=False)
        branch = branch_result.stdout.strip() or "main"

        ahead_behind = self._run(
            "rev-list", "--left-right", "--count", f"{branch}...@{{u}}",
            check=False,
        )
        ahead, behind = 0, 0
        if ahead_behind.returncode == 0:
            parts = ahead_behind.stdout.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])

        return {
            "branch": branch,
            "ahead": ahead,
            "behind": behind,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "clean": len(staged) == 0 and len(modified) == 0 and len(untracked) == 0,
        }

    def add(self, files: list[str] | str = ".") -> dict[str, Any]:
        """Stage files for commit."""
        if isinstance(files, str):
            files = [files]
        self._run("add", *files)
        return {"success": True, "staged": files}

    def commit(self, message: str, files: list[str] | None = None) -> dict[str, Any]:
        """Create a commit with the given message."""
        if files:
            self.add(files)
        result = self._run("commit", "-m", message)
        commit_hash = self._run("rev-parse", "HEAD").stdout.strip()[:8]
        return {"success": True, "hash": commit_hash, "message": message}

    def diff(self, file_path: str | None = None, staged: bool = False) -> str:
        """Get diff of changes."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            args.append("--")
            args.append(file_path)
        result = self._run(*args)
        return result.stdout

    def log(self, count: int = 10, oneline: bool = True) -> list[dict[str, Any]]:
        """Get commit history."""
        args = ["log", f"--max-count={count}"]
        if oneline:
            args.append("--oneline")
        else:
            args.append("--format=%H|%s|%an|%ai")
        result = self._run(*args)
        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            if oneline:
                parts = line.split(" ", 1)
                entries.append({
                    "hash": parts[0] if len(parts) > 0 else "",
                    "message": parts[1] if len(parts) > 1 else "",
                })
            else:
                parts = line.split("|")
                entries.append({
                    "hash": parts[0] if len(parts) > 0 else "",
                    "message": parts[1] if len(parts) > 1 else "",
                    "author": parts[2] if len(parts) > 2 else "",
                    "date": parts[3] if len(parts) > 3 else "",
                })
        return entries

    def branch(self, name: str | None = None) -> dict[str, Any]:
        """List branches or create a new one."""
        if name:
            self._run("checkout", "-b", name)
            return {"success": True, "created": name}
        result = self._run("branch")
        branches = [l.strip().lstrip("* ") for l in result.stdout.split("\n") if l.strip()]
        return {"branches": branches}

    def switch(self, branch: str) -> dict[str, Any]:
        """Switch to a branch."""
        self._run("checkout", branch)
        return {"success": True, "branch": branch}

    def merge(self, branch: str) -> dict[str, Any]:
        """Merge a branch into the current branch."""
        result = self._run("merge", branch, check=False)
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else "",
        }

    def stash(self, message: str = "") -> dict[str, Any]:
        """Stash current changes."""
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        result = self._run(*args)
        return {"success": True, "output": result.stdout.strip()}

    def stash_pop(self) -> dict[str, Any]:
        """Pop the most recent stash."""
        result = self._run("stash", "pop", check=False)
        return {"success": result.returncode == 0, "output": result.stdout.strip()}

    def blame(self, file_path: str) -> list[dict[str, str]]:
        """Show who last modified each line of a file."""
        result = self._run("blame", "--line-porcelain", file_path, check=False)
        entries = []
        current: dict[str, str] = {}
        for line in result.stdout.split("\n"):
            if line.startswith("author "):
                current["author"] = line[7:]
            elif line.startswith("author-time "):
                ts = int(line[12:])
                current["date"] = datetime.fromtimestamp(ts).isoformat()
            elif not line.startswith(" ") and not line.startswith("\t") and current:
                entries.append(current)
                current = {}
        if current:
            entries.append(current)
        return entries

    def remote(self, url: str | None = None, name: str = "origin") -> dict[str, Any]:
        """Get or set remote URL."""
        if url:
            self._run("remote", "add", name, url, check=False)
            self._run("remote", "set-url", name, url, check=False)
            return {"success": True, "remote": name, "url": url}
        result = self._run("remote", "-v", check=False)
        remotes = {}
        for line in result.stdout.strip().split("\n"):
            if line and "\t" in line:
                parts = line.split("\t")
                remotes[parts[0]] = parts[1].split(" ")[0]
        return {"remotes": remotes}

    def push(self, branch: str = "", remote: str = "origin") -> dict[str, Any]:
        """Push commits to remote."""
        args = ["push", remote]
        if branch:
            args.append(branch)
        result = self._run(*args, check=False)
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else "",
        }

    def pull(self, remote: str = "origin", branch: str = "") -> dict[str, Any]:
        """Pull from remote."""
        args = ["pull", remote]
        if branch:
            args.append(branch)
        result = self._run(*args, check=False)
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
        }

    def create_tag(self, name: str, message: str = "") -> dict[str, Any]:
        """Create an annotated tag."""
        args = ["tag", "-a", name]
        if message:
            args.extend(["-m", message])
        self._run(*args)
        return {"success": True, "tag": name}

    def generate_commit_message(self, diff_text: str) -> str:
        """Generate a commit message from diff content."""
        lines = diff_text.strip().split("\n")
        files_changed = set()
        added, removed = 0, 0
        for line in lines:
            if line.startswith("diff --git"):
                parts = line.split(" b/")
                if len(parts) > 1:
                    files_changed.add(parts[1])
            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        if len(files_changed) == 1:
            file = list(files_changed)[0]
            action = "Update" if removed > 0 else "Add"
            return f"{action} {file}"
        elif len(files_changed) <= 3:
            files = ", ".join(sorted(files_changed))
            return f"Update {files}"
        else:
            return f"Update {len(files_changed)} files ({added} additions, {removed} deletions)"
