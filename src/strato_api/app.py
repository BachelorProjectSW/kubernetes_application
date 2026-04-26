from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.routes import router
from ..db.postgres import init_database
from ..custom_logging.log_queue import start_log_worker
import os
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #TODO change to only hosted frontend ip.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


init_database()
start_log_worker()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
