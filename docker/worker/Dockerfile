FROM python:3.13.3-slim

WORKDIR /app

COPY requirements.worker.txt .

RUN pip install --no-cache-dir -r requirements.worker.txt

COPY . .

EXPOSE 8000

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--beat", "--loglevel=info", "-c", "1"]