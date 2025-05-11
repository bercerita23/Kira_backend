import uvicorn
from config import settings
import os 

print(os.getcwd())

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.ENV in ["test", "dev"],
        log_level="debug" if settings.ENV in ["test", "dev"] else None,
    )