"""The Kanban system — the human-and-agent-shared task board (spec 8.3).

Columns map to status (``To Do``, ``In Progress``, ``In Review``, ``Done``); each
card carries id, title, labels, assignee, progress, checklist, milestone, and
priority. Every move emits ``kanban.card.moved`` — which can trigger workflows —
and cards sync bidirectionally with GitHub Projects.
"""

from .board import Card, ChecklistItem, KanbanBoard, COLUMNS

__all__ = ["KanbanBoard", "Card", "ChecklistItem", "COLUMNS"]
