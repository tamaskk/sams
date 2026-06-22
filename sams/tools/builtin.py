"""Implementations of the built-in tool namespace (spec 19.2).

Every function is decorated with ``@tool`` and therefore auto-registers. Each
receives the agent's :class:`~sams.sdk.agent.AgentContext` as ``ctx`` and may use
``ctx.vault``, ``ctx.kanban``, ``ctx.gate``, ``ctx.shell``, ``ctx.emit``.

For the runnable reference implementation, filesystem (``fs.*``) work is routed
through the Vault (the system of record), and integration tools (git/ci/deploy)
emit their events and return structured results rather than touching real
infrastructure — the contract is identical when a real adapter is connected.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..sdk.decorators import tool


# --------------------------------------------------------------------------- #
# Filesystem (routed through the Vault) + shell
# --------------------------------------------------------------------------- #
@tool(id="fs.read", description="Read a file from the workspace/Vault.")
async def fs_read(ctx, path: str) -> str:
    return await ctx.vault.read(path)


@tool(id="fs.write", description="Write a file to the workspace/Vault.")
async def fs_write(ctx, path: str, content: str) -> str:
    return await ctx.vault.write(path, content, actor=ctx.agent.id)


@tool(id="shell.run", description="Run a shell command.")
async def shell_run(ctx, command: str) -> dict[str, Any]:
    res = await ctx.shell.run(command)
    return {"stdout": res.stdout, "stderr": res.stderr, "code": res.code}


# --------------------------------------------------------------------------- #
# Git / version control (spec 9.2)
# --------------------------------------------------------------------------- #
async def _git_event(ctx, type: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ctx.emit(type, payload)
    return {"ok": True, **payload}


@tool(id="git.commit", description="Commit staged changes.")
async def git_commit(ctx, message: str, branch: str = "feature/work") -> dict[str, Any]:
    return await _git_event(ctx, "git.commit.created", {"message": message, "branch": branch})


@tool(id="git.push", description="Push a branch.")
async def git_push(ctx, branch: str = "feature/work") -> dict[str, Any]:
    return await _git_event(ctx, "git.branch.pushed", {"branch": branch})


@tool(id="git.diff", description="Get the diff for a branch/PR.")
async def git_diff(ctx, ref: str = "HEAD") -> dict[str, Any]:
    return {"ref": ref, "files_changed": 1, "diff": f"--- a\n+++ b\n@@ change for {ref} @@"}


@tool(id="git.pr.create", description="Open a pull request.")
async def git_pr_create(ctx, title: str, branch: str = "feature/work", number: int | None = None) -> dict[str, Any]:
    pr = number or 128
    await ctx.emit("git.pr.opened", {"pr": pr, "title": title, "branch": branch})
    return {"pr": pr, "title": title, "branch": branch}


@tool(id="git.pr.review", description="Post a review on a PR.")
async def git_pr_review(ctx, pr: int, verdict: str = "comment", body: str = "") -> dict[str, Any]:
    return await _git_event(ctx, "git.pr.reviewed", {"pr": pr, "verdict": verdict, "body": body})


@tool(id="git.pr.merge", description="Merge a PR (gate-protected).")
async def git_pr_merge(ctx, pr: int) -> dict[str, Any]:
    await ctx.emit("git.pr.merged", {"pr": pr})
    return {"pr": pr, "merged": True}


# --------------------------------------------------------------------------- #
# Web / research
# --------------------------------------------------------------------------- #
@tool(id="web.fetch", description="Fetch a URL and return its text.")
async def web_fetch(ctx, url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            return resp.text[:20000]
    except Exception as exc:  # noqa: BLE001 - offline-friendly
        return f"[web.fetch unavailable for {url}: {exc}]"


@tool(id="web.search", description="Search the web (returns result stubs offline).")
async def web_search(ctx, query: str, limit: int = 5) -> list[dict[str, Any]]:
    return [{"title": f"Result {i + 1} for {query}", "url": f"https://example.com/{i}"} for i in range(limit)]


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@tool(id="db.query", description="Run a database query.")
async def db_query(ctx, query: str) -> dict[str, Any]:
    return {"query": query, "rows": []}


@tool(id="etl.run", description="Run an ETL job.")
async def etl_run(ctx, pipeline: str) -> dict[str, Any]:
    return await _git_event(ctx, "data.etl.completed", {"pipeline": pipeline})


@tool(id="notebook.run", description="Execute a notebook.")
async def notebook_run(ctx, path: str) -> dict[str, Any]:
    return {"path": path, "status": "ok"}


# --------------------------------------------------------------------------- #
# Kanban
# --------------------------------------------------------------------------- #
@tool(id="kanban.read", description="Read the Kanban board.")
async def kanban_read(ctx, column: str | None = None) -> list[dict[str, Any]]:
    cards = ctx.kanban.all() if column is None else ctx.kanban.by_column().get(column, [])
    return [c.to_dict() for c in cards]


@tool(id="kanban.write", description="Create a Kanban card.")
async def kanban_write(ctx, title: str, column: str = "To Do", labels: list[str] | None = None,
                       assignee: str | None = None, priority: str = "Medium") -> dict[str, Any]:
    card = await ctx.kanban.create(
        title, column=column, labels=labels or [], assignee=assignee, priority=priority, actor=ctx.agent.id
    )
    return card.to_dict()


# --------------------------------------------------------------------------- #
# Vault
# --------------------------------------------------------------------------- #
@tool(id="vault.read", description="Read from the Vault.")
async def vault_read(ctx, uri: str) -> str:
    return await ctx.vault.read(uri)


@tool(id="vault.write", description="Write to the Vault.")
async def vault_write(ctx, uri: str, content: str) -> str:
    return await ctx.vault.write(uri, content, actor=ctx.agent.id)


@tool(id="vault.search", description="Search the Vault.")
async def vault_search(ctx, query: str) -> list[dict[str, Any]]:
    return await ctx.vault.search(query)


@tool(id="vault.gc", description="Garbage-collect old Vault versions.")
async def vault_gc(ctx) -> dict[str, Any]:
    return {"reclaimed": await ctx.vault.gc()}


@tool(id="vector.query", description="Semantic search of long-term memory.")
async def vector_query(ctx, query: str, k: int = 5) -> list[dict[str, Any]]:
    mems = await ctx.vault.memory.query(query, agent=ctx.agent.id, space=ctx.space, k=k)
    return [{"id": m.id, "text": m.text, "scope": m.scope} for m in mems]


@tool(id="memory.write", description="Write a long-term memory.")
async def memory_write(ctx, text: str, scope: str = "private") -> dict[str, Any]:
    mem = await ctx.vault.memory.write(text, agent=ctx.agent.id, scope=scope, space=ctx.space)
    await ctx.emit("vault.memory.written", {"memory_id": mem.id, "scope": scope})
    return {"id": mem.id}


# --------------------------------------------------------------------------- #
# Whiteboard / docs / media
# --------------------------------------------------------------------------- #
@tool(id="whiteboard.read", description="Read a whiteboard's content.")
async def whiteboard_read(ctx, board: str) -> str:
    uri = f"vault://boards/{ctx.slug(board)}.md"
    return await ctx.vault.read(uri) if await ctx.vault.exists(uri) else ""


@tool(id="whiteboard.write", description="Write whiteboard content.")
async def whiteboard_write(ctx, board: str, content: str) -> str:
    return await ctx.vault.write(f"vault://boards/{ctx.slug(board)}.md", content, actor=ctx.agent.id)


@tool(id="canvas.draw", description="Draw on the canvas (records a draw op).")
async def canvas_draw(ctx, board: str, shape: str) -> dict[str, Any]:
    return {"board": board, "shape": shape, "drawn": True}


@tool(id="image.generate", description="Generate an image (records intent).")
async def image_generate(ctx, prompt: str) -> dict[str, Any]:
    path = f"vault://artifacts/img-{ctx.slug(prompt)[:24]}.txt"
    await ctx.vault.write(path, f"[image placeholder]\nprompt: {prompt}", actor=ctx.agent.id)
    return {"artifact": path}


@tool(id="doc.write", description="Write a document to the Vault.")
async def doc_write(ctx, path: str, content: str) -> str:
    return await ctx.vault.write(path, content, actor=ctx.agent.id)


@tool(id="md.render", description="Render markdown (returns the markdown).")
async def md_render(ctx, content: str) -> str:
    return content


@tool(id="chart.render", description="Render a chart spec.")
async def chart_render(ctx, spec: dict[str, Any] | str) -> dict[str, Any]:
    return {"chart": spec, "rendered": True}


# --------------------------------------------------------------------------- #
# Security Gate
# --------------------------------------------------------------------------- #
@tool(id="gate.approve", description="Approve a gated change.")
async def gate_approve(ctx, gate_id: str) -> dict[str, Any]:
    req = await ctx.gate.approve(gate_id, ctx.agent.id)
    return req.to_dict()


@tool(id="gate.request_changes", description="Request changes / reject at the gate.")
async def gate_request_changes(ctx, gate_id: str, comment: str = "") -> dict[str, Any]:
    req = await ctx.gate.reject(gate_id, ctx.agent.id, comment)
    return req.to_dict()


@tool(id="gate.comment", description="Comment on a gated change.")
async def gate_comment(ctx, gate_id: str, comment: str) -> dict[str, Any]:
    await ctx.emit("security.gate.comment", {"gate_id": gate_id, "comment": comment})
    return {"gate_id": gate_id, "comment": comment}


# --------------------------------------------------------------------------- #
# QA / testing / security scanning
# --------------------------------------------------------------------------- #
@tool(id="test.generate", description="Generate a test suite.")
async def test_generate(ctx, target: str) -> dict[str, Any]:
    path = f"vault://tests/test_{ctx.slug(target)}.py"
    await ctx.vault.write(path, f"# auto-generated tests for {target}\n", actor=ctx.agent.id)
    return {"tests": path}


@tool(id="test.run", description="Run tests.")
async def test_run(ctx, path: str = "tests/") -> dict[str, Any]:
    return {"passed": 12, "failed": 0, "path": path}


@tool(id="fuzz.run", description="Run a fuzzing campaign.")
async def fuzz_run(ctx, target: str, iterations: int = 1000) -> dict[str, Any]:
    return {"target": target, "iterations": iterations, "crashes": 0}


@tool(id="sast.scan", description="Static application security testing.")
async def sast_scan(ctx, path: str = "vault://src") -> dict[str, Any]:
    return {"path": path, "findings": []}


@tool(id="secrets.scan", description="Scan for leaked secrets.")
async def secrets_scan(ctx, ref: str = "HEAD") -> dict[str, Any]:
    await ctx.emit("security.secrets.scanned", {"ref": ref, "leaks": 0})
    return {"ref": ref, "leaks": 0}


# --------------------------------------------------------------------------- #
# Ops / DevOps
# --------------------------------------------------------------------------- #
@tool(id="metrics.query", description="Query metrics.")
async def metrics_query(ctx, metric: str) -> dict[str, Any]:
    return {"metric": metric, "value": 0.0}


@tool(id="alert.raise", description="Raise an alert.")
async def alert_raise(ctx, message: str, severity: str = "warning") -> dict[str, Any]:
    await ctx.emit("ops.alert.raised", {"message": message, "severity": severity})
    return {"raised": True}


@tool(id="incident.open", description="Open an incident.")
async def incident_open(ctx, title: str) -> dict[str, Any]:
    await ctx.emit("ops.incident.opened", {"title": title})
    return {"incident": title}


@tool(id="ci.trigger", description="Trigger a CI run.")
async def ci_trigger(ctx, ref: str = "main") -> dict[str, Any]:
    await ctx.emit("ops.ci.triggered", {"ref": ref})
    return {"ref": ref, "status": "running"}


@tool(id="deploy.run", description="Run a deploy.")
async def deploy_run(ctx, env: str = "dev") -> dict[str, Any]:
    await ctx.emit("ops.deploy.completed", {"env": env})
    return {"env": env, "deployed": True}


@tool(id="infra.apply", description="Apply infrastructure changes.")
async def infra_apply(ctx, plan: str) -> dict[str, Any]:
    return {"plan": plan, "applied": True}


@tool(id="build.run", description="Run a build.")
async def build_run(ctx, target: str = "all") -> dict[str, Any]:
    return {"target": target, "ok": True}


@tool(id="package.publish", description="Publish a package.")
async def package_publish(ctx, name: str, version: str) -> dict[str, Any]:
    return {"name": name, "version": version, "published": True}


# --------------------------------------------------------------------------- #
# Comms (draft-only; sending requires human approval — spec 7.16)
# --------------------------------------------------------------------------- #
@tool(id="email.draft", description="Draft an email (never sends).")
async def email_draft(ctx, to: str, subject: str, body: str) -> dict[str, Any]:
    await ctx.emit("comms.email.drafted", {"to": to, "subject": subject})
    return {"draft": True, "to": to, "subject": subject}


@tool(id="chat.post", description="Post a chat message.")
async def chat_post(ctx, thread: str, body: str) -> dict[str, Any]:
    await ctx.emit("chat.message.posted", {"thread": thread, "body": body, "author": ctx.agent.id})
    return {"posted": True}


@tool(id="schedule.post", description="Schedule a social post (human-approved).")
async def schedule_post(ctx, channel: str, body: str, when: str) -> dict[str, Any]:
    await ctx.emit("comms.post.scheduled", {"channel": channel, "when": when})
    return {"scheduled": True}


# --------------------------------------------------------------------------- #
# Localization
# --------------------------------------------------------------------------- #
@tool(id="translate.run", description="Translate text.")
async def translate_run(ctx, text: str, to_lang: str = "en") -> dict[str, Any]:
    return {"to": to_lang, "text": f"[{to_lang}] {text}"}


@tool(id="i18n.extract", description="Extract i18n keys.")
async def i18n_extract(ctx, path: str) -> dict[str, Any]:
    return {"path": path, "keys": []}
