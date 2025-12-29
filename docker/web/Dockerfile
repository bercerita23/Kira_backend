FROM python:3.13.3-slim

WORKDIR /app

COPY requirements.web.txt .

RUN pip install --no-cache-dir -r requirements.web.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "app.server"]