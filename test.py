from fastapi import FastAPI,Request
import uvicorn

app = FastAPI()

@app.post("/configure-yaml")
def configure_yaml(request: Request):
    print(request.json)
    return {"hello": "world"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)