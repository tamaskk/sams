"""GitHub REST integration — list the repositories on the user's profile.

The SAMS backend reaches GitHub over its REST API with a personal access token
(``GITHUB_TOKEN``) so the GitHub panel can show "my repos" (public + private).
Without a token it falls back to the *public* repos of ``GITHUB_USERNAME`` if set.

Create a token at GitHub → Settings → Developer settings → Personal access tokens
(a fine-grained or classic token with read access to repositories).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any

import httpx

log = logging.getLogger("sams.integrations.github_api")

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @property
    def token(self) -> str | None:
        # Read lazily so a token set after construction (e.g. from .env) is seen.
        return self._token or os.environ.get("GITHUB_TOKEN")

    @property
    def username(self) -> str | None:
        return os.environ.get("GITHUB_USERNAME")

    @property
    def configured(self) -> bool:
        return bool(self.token or self.username)

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def repos(self) -> dict[str, Any]:
        """Repositories for the authenticated user, or public repos of GITHUB_USERNAME."""
        if not self.configured:
            return {"configured": False, "repos": []}
        async with httpx.AsyncClient(timeout=30) as client:
            user: dict[str, Any] = {}
            if self.token:
                ru = await client.get(f"{API}/user", headers=self._headers())
                ru.raise_for_status()
                user = ru.json()
                params: dict[str, Any] = {
                    "per_page": 100, "sort": "pushed",
                    "affiliation": "owner,collaborator,organization_member",
                }
                rr = await client.get(f"{API}/user/repos", headers=self._headers(), params=params)
            else:
                params = {"per_page": 100, "sort": "pushed", "type": "owner"}
                rr = await client.get(f"{API}/users/{self.username}/repos", headers=self._headers(), params=params)
            rr.raise_for_status()
            repos = [self._normalize(r) for r in rr.json()]
            return {
                "configured": True,
                "user": user.get("login") or self.username,
                "avatar": user.get("avatar_url"),
                "repos": repos,
            }

    async def tree(self, repo: str, ref: str | None = None) -> dict[str, Any]:
        """The full file tree (recursive) of a repo at a branch/ref."""
        async with httpx.AsyncClient(timeout=30) as client:
            if not ref:
                r = await client.get(f"{API}/repos/{repo}", headers=self._headers())
                r.raise_for_status()
                ref = r.json().get("default_branch", "main")
            rr = await client.get(f"{API}/repos/{repo}/git/trees/{ref}",
                                  headers=self._headers(), params={"recursive": "1"})
            rr.raise_for_status()
            data = rr.json()
            entries = [
                {"path": t["path"], "type": "dir" if t["type"] == "tree" else "file", "size": t.get("size")}
                for t in data.get("tree", []) if t.get("type") in ("tree", "blob")
            ]
            return {"repo": repo, "ref": ref, "truncated": data.get("truncated", False), "entries": entries}

    async def file_content(self, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
        """The (decoded) text content of a single file."""
        async with httpx.AsyncClient(timeout=30) as client:
            params = {"ref": ref} if ref else None
            r = await client.get(f"{API}/repos/{repo}/contents/{path}", headers=self._headers(), params=params)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, list):
                return {"path": path, "content": "", "directory": True}
            size = int(j.get("size") or 0)
            if size > 800_000:
                return {"path": path, "content": f"(file too large to preview — {size:,} bytes)", "truncated": True}
            raw = j.get("content", "")
            if j.get("encoding") == "base64":
                data = base64.b64decode(raw)
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    return {"path": path, "content": "(binary file)", "binary": True}
                return {"path": path, "content": text, "truncated": False}
            return {"path": path, "content": raw, "truncated": False}

    async def default_branch(self, repo: str) -> str | None:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}/repos/{repo}", headers=self._headers())
            r.raise_for_status()
            return r.json().get("default_branch")

    async def my_pulls(self, state: str = "open") -> dict[str, Any]:
        """Pull requests across the user's repos, aggregated per-repo.

        This is more reliable than the search API (which is flaky with
        fine-grained tokens) and uses the same /pulls endpoint that opens PRs.
        """
        st = state if state in ("open", "closed", "all") else "open"
        async with httpx.AsyncClient(timeout=30) as client:
            login = self.username
            if self.token and not login:
                ru = await client.get(f"{API}/user", headers=self._headers())
                ru.raise_for_status()
                login = ru.json().get("login")
            if self.token:
                params: dict[str, Any] = {"per_page": 100, "sort": "pushed",
                                          "affiliation": "owner,collaborator,organization_member"}
                rr = await client.get(f"{API}/user/repos", headers=self._headers(), params=params)
            else:
                rr = await client.get(f"{API}/users/{login}/repos", headers=self._headers(),
                                      params={"per_page": 100, "sort": "pushed", "type": "owner"})
            rr.raise_for_status()
            repos = [r["full_name"] for r in rr.json() if not r.get("archived")]

            async def repo_pulls(full: str) -> list[dict[str, Any]]:
                try:
                    r = await client.get(f"{API}/repos/{full}/pulls", headers=self._headers(),
                                         params={"state": st, "per_page": 50, "sort": "updated", "direction": "desc"})
                    r.raise_for_status()
                    return [self._normalize_pull(p, full) for p in r.json()]
                except httpx.HTTPError:
                    return []

            results = await asyncio.gather(*(repo_pulls(f) for f in repos))
            pulls = [p for sub in results for p in sub]
            pulls.sort(key=lambda p: p.get("updated_at") or "", reverse=True)
            return {"configured": True, "user": login, "pulls": pulls}

    @staticmethod
    def _normalize_pull(p: dict[str, Any], repo: str) -> dict[str, Any]:
        user = p.get("user") or {}
        return {
            "id": p.get("id"),
            "number": p.get("number"),
            "title": p.get("title", ""),
            "url": p.get("html_url"),
            "repo": repo,
            "author": user.get("login"),
            "state": "merged" if p.get("merged_at") else p.get("state", "open"),
            "draft": bool(p.get("draft")),
            "updated_at": p.get("updated_at"),
            "comments": 0,
        }

    async def pull_detail(self, repo: str, number: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}/repos/{repo}/pulls/{number}", headers=self._headers())
            r.raise_for_status()
            p = r.json()
            head = p.get("head") or {}
            base = p.get("base") or {}
            user = p.get("user") or {}
            return {
                "repo": repo, "number": p.get("number"), "title": p.get("title", ""),
                "body": p.get("body") or "",
                "state": "merged" if p.get("merged") else p.get("state", "open"),
                "draft": bool(p.get("draft")), "merged": bool(p.get("merged")),
                "mergeable": p.get("mergeable"), "mergeable_state": p.get("mergeable_state"),
                "head": head.get("ref"), "base": base.get("ref"),
                "additions": p.get("additions", 0), "deletions": p.get("deletions", 0),
                "changed_files": p.get("changed_files", 0), "commits": p.get("commits", 0),
                "url": p.get("html_url"), "author": user.get("login"),
            }

    async def pull_files(self, repo: str, number: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}/repos/{repo}/pulls/{number}/files",
                                 headers=self._headers(), params={"per_page": 100})
            r.raise_for_status()
            return {"files": [
                {"filename": f.get("filename"), "status": f.get("status"),
                 "additions": f.get("additions", 0), "deletions": f.get("deletions", 0),
                 "patch": f.get("patch")}
                for f in r.json()
            ]}

    async def merge_pull(self, repo: str, number: int, method: str = "merge") -> dict[str, Any]:
        if method not in ("merge", "squash", "rebase"):
            method = "merge"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.put(f"{API}/repos/{repo}/pulls/{number}/merge",
                                 headers=self._headers(), json={"merge_method": method})
            if r.status_code >= 400:  # 405 not mergeable, 409 conflict, etc.
                try:
                    msg = r.json().get("message", r.text)
                except Exception:  # noqa: BLE001
                    msg = r.text
                return {"merged": False, "message": msg, "status": r.status_code}
            j = r.json()
            return {"merged": bool(j.get("merged", True)), "message": j.get("message", ""), "sha": j.get("sha")}

    async def close_pull(self, repo: str, number: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(f"{API}/repos/{repo}/pulls/{number}",
                                   headers=self._headers(), json={"state": "closed"})
            if r.status_code >= 400:
                try:
                    msg = r.json().get("message", r.text)
                except Exception:  # noqa: BLE001
                    msg = r.text
                return {"closed": False, "message": msg, "status": r.status_code}
            return {"closed": True}

    async def ready_pull(self, repo: str, number: int) -> dict[str, Any]:
        """Mark a draft PR ready for review (GraphQL — REST can't un-draft)."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}/repos/{repo}/pulls/{number}", headers=self._headers())
            r.raise_for_status()
            node_id = r.json().get("node_id")
            if not node_id:
                return {"ok": False, "message": "could not resolve the PR id"}
            gr = await client.post(
                "https://api.github.com/graphql", headers=self._headers(),
                json={"query": "mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{isDraft}}}",
                      "variables": {"id": node_id}},
            )
            if gr.status_code >= 400:
                return {"ok": False, "message": gr.text[:200]}
            data = gr.json()
            if data.get("errors"):
                return {"ok": False, "message": data["errors"][0].get("message", "GraphQL error")}
            return {"ok": True}

    async def open_pr(self, repo: str, head: str, base: str, title: str, body: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{API}/repos/{repo}/pulls", headers=self._headers(),
                                  json={"title": title, "head": head, "base": base, "body": body})
            r.raise_for_status()
            return r.json()

    @staticmethod
    def _normalize(r: dict[str, Any]) -> dict[str, Any]:
        owner = r.get("owner") or {}
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "description": r.get("description") or "",
            "url": r.get("html_url"),
            "clone_url": r.get("clone_url"),
            "ssh_url": r.get("ssh_url"),
            "private": bool(r.get("private")),
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "updated_at": r.get("pushed_at") or r.get("updated_at"),
            "default_branch": r.get("default_branch"),
            "owner": owner.get("login"),
            "fork": bool(r.get("fork")),
            "archived": bool(r.get("archived")),
        }
