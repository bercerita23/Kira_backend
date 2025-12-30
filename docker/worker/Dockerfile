FROM python:3.13.3-slim

WORKDIR /app

COPY requirements.worker.txt .

RUN pip install --no-cache-dir -r requirements.worker.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "app.worker"]