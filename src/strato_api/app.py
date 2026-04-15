from fastapi import FastAPI
from .routes.routes import router
from ..db.postgres import init_database
import os
import uvicorn

app = FastAPI()

app.include_router(router)

init_database()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
