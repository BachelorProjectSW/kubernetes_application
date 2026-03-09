from fastapi import FastAPI,Request
from pydantic import BaseModel
import uvicorn



class ConfigModel(BaseModel):
    experiment_id: str
    total_context_window: int
    request_rate: int
    duration_minutes: int
    scaling_interval: int
    node_priority: str

app = FastAPI()

def render_yaml(template_path: str, yaml_data: ConfigModel):
    print(yaml_data.model_dump())
    with open(template_path,'r') as yaml_file:
        file=yaml_file.read()
    return file.format(replicas=yaml_data.total_context_window, meta_name=yaml_data.duration_minutes)


def save_yaml(data_path: str, yaml_data: str):
    with open(data_path,'w') as yaml_file:
        yaml_file.write(yaml_data)




@app.post("/configure-yaml")
def configure_yaml(configModel: ConfigModel):
    render= render_yaml("config.yaml", configModel)
    save_yaml("given_specs.yaml", render)
    return {"hello": "world"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)




