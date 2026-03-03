from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
import uvicorn

app = FastAPI()


@app.get("/config", response_class=HTMLResponse)
async def read_items():
    return get_file("input.html")

    
@app.get("/output", response_class=HTMLResponse)
async def read_items():
    return get_file("output.html")

    
@app.get("/", response_class=HTMLResponse)
async def read_items():
    return get_file("index.html")
    
def get_file(path):
    with open(path, "r") as file:
        return file.read()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    uvicorn.run(app, host="0.0.0.0", port=port)

