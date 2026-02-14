from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import select

from backend.core.logger import LOG
from backend.database import async_db
from backend.database.models import TaskRun, TaskSchedule
from backend.enums import Task, TaskStatus

# in memory set to track currently running tasks
_running_tasks: set[Task] = set()


def is_task_running(task: Task) -> bool:
    """Check if a task is currently running (in-memory check)."""
    return task in _running_tasks


def get_running_tasks() -> set[Task]:
    """Get all currently running tasks."""
    return _running_tasks.copy()


@asynccontextmanager
async def track_task_execution(task: Task) -> AsyncGenerator[None, None]:
    """
    Context manager to track task execution status.

    Usage:
        async with track_task_execution(Task.SYNC_ALL_MEDIA):
            await sync_movies()
            await sync_series()

    This will:
    - Add task to in-memory running set (checked by API for real-time status)
    - Write COMPLETED/FAILED to DB only when task finishes (historical record)
    - Remove task from running set when complete
    """
    start_time = datetime.now(timezone.utc)

    # add to in-memory running set
    _running_tasks.add(task)
    LOG.info(f"Task {task.friendly_name()} started")

    # get task schedule for DB relationship
    task_schedule_id = None
    async with async_db() as session:
        result = await session.execute(
            select(TaskSchedule).where(TaskSchedule.task == task)
        )
        task_schedule = result.scalar_one_or_none()
        if task_schedule:
            task_schedule_id = task_schedule.id

    try:
        yield

        # task completed successfully - write to DB
        async with async_db() as session:
            task_run = TaskRun(
                task_schedule_id=task_schedule_id,
                task=task,
                status=TaskStatus.COMPLETED,
            )
            task_run.started_at = start_time
            task_run.completed_at = datetime.now(timezone.utc)

            session.add(task_run)
            await session.commit()
            LOG.info(f"Task {task.friendly_name()} completed successfully")

    except Exception as e:
        # task failed - write to DB
        async with async_db() as session:
            task_run = TaskRun(
                task_schedule_id=task_schedule_id,
                task=task,
                status=TaskStatus.FAILED,
            )
            task_run.started_at = start_time
            task_run.completed_at = datetime.now(timezone.utc)
            task_run.error_message = str(e)

            session.add(task_run)
            await session.commit()
            LOG.error(f"Task {task.friendly_name()} failed: {e}")

        raise  # raise the exception

    finally:
        # always remove from running set
        _running_tasks.discard(task)
