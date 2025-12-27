# app/start_celery.py
from app.tasks import worker_loop
import time

print("[Bootstrap] Enqueuing worker loop", flush=True)
worker_loop.delay()

# Block forever so the process doesn't exit
while True:
    time.sleep(3600)
