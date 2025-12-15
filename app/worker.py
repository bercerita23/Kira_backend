import asyncio
from app.repeated_tasks.question_and_prompt import prompt_generation
from app.repeated_tasks.visuals import visual_generation
from app.repeated_tasks.ready import ready_for_review
from app.config import settings
from typing import Callable, Dict

# Locks to prevent concurrent processing of same task
task_locks: Dict[str, asyncio.Lock] = {
    "prompt_generation": asyncio.Lock(),
    "ready_for_review": asyncio.Lock(),
    "visual_generation": asyncio.Lock(),
}

async def run_task(name: str, func: Callable, interval: int = 30):
    """
    Run a background task periodically, ensuring only one instance
    of this task is running at a time.
    """
    consecutive_errors = 0
    max_backoff = 300  # 5 minutes

    while True:
        lock = task_locks[name]
        if lock.locked():
            # Another instance is running, wait for next interval
            await asyncio.sleep(interval)
            continue

        try:
            async with lock:
                try:
                    await func()
                    consecutive_errors = 0  # Reset on success
                except Exception as e:
                    consecutive_errors += 1
                    error_msg = str(e)
                    print(f"Error in {name}: {error_msg}")
                    
                    # Exponential backoff on connection errors
                    if "remaining connection slots are reserved" in error_msg:
                        backoff = min(interval * (2 ** consecutive_errors), max_backoff)
                        print(f"{name}: Connection pool exhausted, backing off for {backoff}s")
                        await asyncio.sleep(backoff)
                        continue

            # Normal interval between runs
            await asyncio.sleep(interval)

        except Exception as outer_e:
            print(f"Critical error in task runner for {name}: {outer_e}")
            await asyncio.sleep(interval)

async def worker_main():
    """Run generation tasks concurrently with the same logic as before"""
    print(f"🚀 Worker starting in {settings.ENV} mode...")
    print("=" * 50)
    print("Running tasks concurrently:")
    print("  - PromptGen (every 30s)")
    print("  - VisualGen (every 30s)")
    print("  - ReadyCheck (every 30s)")
    print("=" * 50)
    
    # Run all tasks concurrently (same as old main.py)
    await asyncio.gather(
        run_task("prompt_generation", prompt_generation, 30),
        run_task("ready_for_review", ready_for_review, 30),
        run_task("visual_generation", visual_generation, 30),
    )

if __name__ == "__main__":
    asyncio.run(worker_main())