"""Manual end-to-end smoke test: boot SAMS and run a task through an agent."""

import asyncio

from sams.platform import build_platform


async def main() -> None:
    platform = build_platform(".", environment="dev")
    await platform.boot()

    print("=== STATUS ===")
    print(platform.status())

    print("\n=== AGENTS ONLINE ===")
    for a in platform.list_agents():
        print(f"  {a['name']:8} ({a['agent_id']:8}) {a['state']:12} home={a['home']['primitive']}")

    # 1) Submit a task and let the Orchestrator route it.
    print("\n=== SUBMIT TASK ===")
    task = await platform.submit_task(
        "Build real-time agent activity engine", capability="code.write"
    )
    print("submitted", task.id, "->", task.title)

    # Give the scheduler a moment to assign + run.
    for _ in range(50):
        await asyncio.sleep(0.05)
        if task.status in ("complete", "error"):
            break
    print("task status:", task.status)
    print("task result:", task.result)

    # 2) Run the code-review workflow (gate auto-approves in dev mode).
    print("\n=== RUN code-review WORKFLOW ===")
    run = await platform.run_workflow("code-review", {"pr": 128})
    print("run", run.run_id, "status:", run.status)
    for s in run.steps:
        print(f"  step {s.id:16} {s.status}")

    # 3) Show recent events + vault stats.
    print("\n=== RECENT EVENTS ===")
    hist = await platform.event_bus.history(limit=12)
    for e in hist[-12:]:
        print(f"  {e.type:28} actor={e.actor}")

    print("\n=== VAULT ===")
    print(await platform.vault.stats())

    await platform.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
