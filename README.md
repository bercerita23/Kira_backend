# Backend w/ FastAPI 
- [Getting Started](#getting-started)
- [Usage](#usage)
- [API](#api)

## Getting Started 
### Install requirements 
```bash 
cd backend
pip install -r requirements.txt
```
### Start the server 
run the server.py script with 
```bash
python -m app.server to start the server
```

### Folder Strecture 
```bash
.
├── app
│   ├── crud
│   │   └── __init__.py
│   ├── database
│   │   ├── __init__.py
│   │   ├── db.py
│   │   └── session.py
│   ├── model
│   │   ├── __init__.py
│   │   ├── question_model.py
│   │   ├── quiz_model.py
│   │   ├── reward_model.py
│   │   ├── school_model.py
│   │   ├── user_history_model.py
│   │   └── user_model.py
│   ├── router
│   │   └── __init__.py
│   ├── schema
│   │   ├── __init__.py
│   │   ├── question_schema.py
│   │   ├── quiz_schema.py
│   │   ├── reward_schema.py
│   │   ├── school_schema.py
│   │   ├── user_history_schema.py
│   │   └── user_schema.py
│   ├── __init__.py
│   ├── config.py
│   ├── log.py
│   ├── main.py
│   ├── security.py
│   └── server.py
├── diagrams
│   └── backend_flow_diagram.drawio
├── tests
├── Dockerfile
├── README.md
└── requirements.txt

9 directories, 29 files

```
### Strectural Explanation 

```text
app/
├── crud/         # Handles query logic (TBD: raw SQL vs FastAPI CRUD repo)
├── database/     # Manages DB connection setup and session
├── model/        # Defines SQLAlchemy table schemas
├── router/       # API route definitions
├── schema/       # Pydantic models for input/output validation

config.py         # Loads environment variables from .env.local
log.py            # Configures logging for debugging and traceability
main.py           # Defines the FastAPI application instance
security.py       # Security utilities (e.g., hashing, token verification)
server.py         # Entry point script to launch the app
test/             # All unit and integration tests
pgsql
Copy
Edit
```

## API Doc

