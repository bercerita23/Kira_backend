"""Pytest config: stub the env vars Pydantic Settings demands at import time.

`app.config.settings = get_settings(env='prod')` runs at the first
`from app.config import ...`, which would otherwise fail in CI / local
sandboxes that have no `.env.prod`. Stubbing via `setdefault` lets a real
`.env.prod` (or already-exported env vars) win when present.
"""
import os

_DEFAULTS = {
    "PROJECT_NAME": "kira-test",
    "API_VERSION": "0.0.0-test",
    "ENV": "test",
    "SECRET_KEY": "test-secret",
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
    "SERVER_HOST": "0.0.0.0",
    "SERVER_PORT": "8000",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "POSTGRES_PORT": "5432",
    "FIRST_SUPERUSER_USERNAME": "test",
    "FIRST_SUPERUSER_EMAIL": "test@example.com",
    "FIRST_SUPERUSER_PASSWORD": "test",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_S3_BUCKET_NAME": "test",
    "GOOGLE_API_KEY": "test",
    "OPENAI_API_KEY": "test",
    "FRONTEND_URL": "http://localhost:3000",
}

for _k, _v in _DEFAULTS.items():
    os.environ.setdefault(_k, _v)
