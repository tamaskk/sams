"""Shared fixtures: a booted SAMS platform per test."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest_asyncio

from sams.platform import build_platform


@pytest_asyncio.fixture
async def platform():
    # Start each test with a clean (non-persisted) board.
    Path(".sams/state/kanban.json").unlink(missing_ok=True)
    p = build_platform(".", environment="dev")
    await p.boot()
    try:
        yield p
    finally:
        await p.shutdown()


async def wait_for(predicate, *, timeout: float = 5.0, interval: float = 0.03):
    """Poll until predicate() is truthy or timeout."""
    waited = 0.0
    while waited < timeout:
        if predicate():
            return True
        await asyncio.sleep(interval)
        waited += interval
    return False
