os.system("celery -A app.celery_app.celery_app worker --beat --loglevel=info")
# app/start_celery.py
import os

os.system("celery -A app.celery_app.celery_app worker --beat --loglevel=info")
