from fastapi import FastAPI
from cluster_api.routes.routes import router
from cluster_api.util.logger import init_csv
import os
import uvicorn

app = FastAPI()

app.include_router(router)

init_csv()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8040"))
    uvicorn.run(app, host="0.0.0.0", port=port)
