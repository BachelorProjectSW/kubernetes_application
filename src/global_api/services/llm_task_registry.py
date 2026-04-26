import asyncio

active_llm_tasks: set[asyncio.Task] = set()


def register_current_task() -> asyncio.Task | None:
    task = asyncio.current_task()
    if task is not None:
        active_llm_tasks.add(task)
    return task


def unregister_task(task: asyncio.Task | None) -> None:
    if task is not None:
        active_llm_tasks.discard(task)


def cancel_active_llm_tasks() -> int:
    tasks = list(active_llm_tasks)

    for task in tasks:
        task.cancel()

    return len(tasks)