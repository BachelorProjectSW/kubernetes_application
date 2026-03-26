from fastapi import FastAPI
from .routes.routes import router
from ..custom_logging.logger import init_csv
import os
import uvicorn

app = FastAPI()

app.include_router(router)

init_csv()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8040"))
    uvicorn.run(app, host="0.0.0.0", port=port)
