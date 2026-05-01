from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.routes import router
from ..db.postgres import init_database
import os
import uvicorn

app = FastAPI()

# Allow all website traffic as its all hosted on the tailscale network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


init_database()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
