"""Manual verification for Phase 23 (Tasks & Follow-ups): confirms new
tasks get a sensible auto-assigned due date by priority, complete_task
correctly transitions status, and Overdue/Due Today/Upcoming grouping
computes correctly from real due_date values. Not a pytest suite (that's
tests/test_task_tools.py)."""

import sys
from datetime import date, timedelta

from database import crud
from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.task_tools import complete_task, create_followup_task  # noqa: E402


def main() -> None:
    seed_main()
    today = date.today()

    print("=== Auto-assigned due dates by priority ===")
    high = create_followup_task(description="High priority test task", priority="High")
    medium = create_followup_task(description="Medium priority test task", priority="Medium")
    low = create_followup_task(description="Low priority test task", priority="Low")
    none_priority = create_followup_task(description="No priority test task")

    assert high.due_date == today + timedelta(days=1), high.due_date
    assert medium.due_date == today + timedelta(days=3), medium.due_date
    assert low.due_date == today + timedelta(days=7), low.due_date
    assert none_priority.due_date == today + timedelta(days=5), none_priority.due_date
    print(f"High -> {high.due_date} (+1d), Medium -> {medium.due_date} (+3d), "
          f"Low -> {low.due_date} (+7d), none -> {none_priority.due_date} (+5d)")
    print("OK\n")

    print("=== Explicit due_date is respected, not overridden ===")
    explicit = create_followup_task(description="Explicit due date task", due_date=today + timedelta(days=30))
    assert explicit.due_date == today + timedelta(days=30)
    print("OK\n")

    print("=== complete_task transitions status ===")
    open_before = crud.list_tasks(status="Open")
    assert any(t.id == high.task_id for t in open_before)

    result = complete_task(high.task_id)
    assert result.success
    completed = crud.list_tasks(status="Completed")
    assert any(t.id == high.task_id for t in completed)
    open_after = crud.list_tasks(status="Open")
    assert not any(t.id == high.task_id for t in open_after)
    print("OK: task moved from Open to Completed.\n")

    print("=== complete_task on unknown id fails gracefully ===")
    result2 = complete_task(999999)
    assert not result2.success
    print("OK\n")

    print("=== Overdue / Due Today / Upcoming grouping ===")
    overdue_task = create_followup_task(description="Overdue test task", due_date=today - timedelta(days=2))
    today_task = create_followup_task(description="Due today test task", due_date=today)

    all_open = crud.list_tasks(status="Open")
    overdue = [t for t in all_open if t.due_date and t.due_date < today]
    due_today = [t for t in all_open if t.due_date and t.due_date == today]
    upcoming = [t for t in all_open if t.due_date and t.due_date > today]

    assert any(t.id == overdue_task.task_id for t in overdue)
    assert any(t.id == today_task.task_id for t in due_today)
    assert any(t.id == medium.task_id for t in upcoming)
    print(f"overdue={len(overdue)} due_today={len(due_today)} upcoming={len(upcoming)}")
    print("OK: grouping correctly reflects real due_date values.\n")

    print("All Tasks & Follow-ups checks passed.")


if __name__ == "__main__":
    main()
