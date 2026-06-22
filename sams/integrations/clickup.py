"""ClickUp integration — fetch the tasks assigned to the current user.

The SAMS backend reaches ClickUp over its REST API with a personal token
(``CLICKUP_API_TOKEN``), so the Source Control panel can pull "my tasks" and the
user can Accept / Edit / Decline them into SAMS cards.

Get a token at ClickUp → Settings → Apps → API Token (starts with ``pk_``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("sams.integrations.clickup")

API = "https://api.clickup.com/api/v2"

# Statuses that are effectively finished — hidden from "my tasks".
_DONE = {"closed", "done", "complete", "completed", "cancelled", "canceled",
         "partner declined", "waiting for deploy", "waiting for deployment"}


class ClickUpClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @property
    def token(self) -> str | None:
        # Read lazily so a token set after construction (e.g. from .env) is seen.
        return self._token or os.environ.get("CLICKUP_API_TOKEN")

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.token or ""}

    async def _get(self, client: httpx.AsyncClient, path: str, params: Any = None) -> dict[str, Any]:
        r = await client.get(f"{API}{path}", headers=self._headers(), params=params)
        r.raise_for_status()
        return r.json()

    async def assigned_tasks(self, *, include_closed: bool = False) -> dict[str, Any]:
        """Tasks assigned to the authenticated user, across all their workspaces."""
        if not self.configured:
            return {"configured": False, "tasks": []}
        async with httpx.AsyncClient(timeout=30) as client:
            user = (await self._get(client, "/user"))["user"]
            uid = str(user["id"])
            teams = (await self._get(client, "/team")).get("teams", [])
            tasks: list[dict[str, Any]] = []
            seen: set[str] = set()
            for team in teams:
                params = [
                    ("assignees[]", uid),
                    ("include_closed", "true" if include_closed else "false"),
                    ("subtasks", "true"),
                    ("include_markdown_description", "true"),
                ]
                try:
                    data = await self._get(client, f"/team/{team['id']}/task", params=params)
                except httpx.HTTPError as exc:  # one bad workspace shouldn't break the rest
                    log.warning("clickup team %s fetch failed: %s", team.get("id"), exc)
                    continue
                for task in data.get("tasks", []):
                    if task["id"] in seen:
                        continue
                    seen.add(task["id"])
                    norm = self._normalize(task, team)
                    if (norm["status"] or "").lower() in _DONE:
                        continue
                    tasks.append(norm)
            return {"configured": True, "user": user.get("username"), "tasks": tasks}

    @staticmethod
    def _normalize(task: dict[str, Any], team: dict[str, Any]) -> dict[str, Any]:
        status = task.get("status") or {}
        priority = task.get("priority") or {}
        return {
            "id": task["id"],
            "name": task.get("name", ""),
            "description": (task.get("markdown_description") or task.get("text_content")
                           or task.get("description") or ""),
            "status": status.get("status") if isinstance(status, dict) else status,
            "url": task.get("url"),
            "priority": priority.get("priority") if isinstance(priority, dict) else None,
            "list": (task.get("list") or {}).get("name"),
            "team": team.get("name"),
        }
