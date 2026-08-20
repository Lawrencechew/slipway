from typing import Dict, Any
import uuid


class GitAdapterInterface:
    def create_branch(self, repo: str, base: str, branch: str) -> Dict[str, Any]:
        raise NotImplementedError()

    def commit(self, repo: str, branch: str, files: Dict[str, str], message: str) -> Dict[str, Any]:
        raise NotImplementedError()

    def create_pr(self, repo: str, head: str, base: str, title: str, body: str) -> Dict[str, Any]:
        raise NotImplementedError()


class MockGitAdapter(GitAdapterInterface):
    def __init__(self):
        self.ops = []

    def create_branch(self, repo: str, base: str, branch: str) -> Dict[str, Any]:
        op = {"op": "create_branch", "repo": repo, "base": base, "branch": branch}
        self.ops.append(op)
        return {"ok": True, "branch": branch}

    def commit(self, repo: str, branch: str, files: Dict[str, str], message: str) -> Dict[str, Any]:
        commit_id = uuid.uuid4().hex
        op = {"op": "commit", "repo": repo, "branch": branch, "files": list(files.keys()), "message": message, "commit": commit_id}
        self.ops.append(op)
        return {"ok": True, "commit": commit_id}

    def create_pr(self, repo: str, head: str, base: str, title: str, body: str) -> Dict[str, Any]:
        pr_id = uuid.uuid4().hex
        op = {"op": "create_pr", "repo": repo, "head": head, "base": base, "title": title, "body": body, "pr": pr_id}
        self.ops.append(op)
        return {"ok": True, "pr": pr_id}
