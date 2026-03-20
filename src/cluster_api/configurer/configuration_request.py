from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import uvicorn


class ConfigModel(BaseModel):
    """Model with the configuration for the nodes.

    model of configurations for a run of a experiment on a bunch of nodes.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        duration_minutes: the number of minutes the experiment shoudl take place.
        node_priority: the order in which the nodes are turned on and off (list require python 3.14).
        start_time_replay: the time in which the user desires the experiemtn to start.
        request_rate: the number of request allowed in a minute.
        latency_reshold: when the experiemtn shoudl start shutting down nodes.
        scaling_ interval: the time in which the experient should add nodes.
        strategy_weights: the priority of which strategies shoudl be considered first.

    request_rate: maximum number of requests in the span of a minute.

    """

    experiment_id: str
    duration_minutes: int
    node_priority: list[str]
    start_time_replay: datetime
    request_rate: int
    latency_treshold: int
    scaling_interval: int
    strategy_weights: list[str]


app = FastAPI()


def render_yaml(template_path: str, yaml_data: ConfigModel):
    """Read a yaml Template amd injects conficuration values into the placeholders.

    the function loads template and uses Python´s string formatting,
    to map 'ConfigModel' to the template keys.

    Arguments:
        template_path: the path to the YAML template file.
        yaml_data: the configuration data with the values that should be injected into.
        the template in the form of the "ConfigModel".

    Returns:
        str: The rendered YAML content as a string, with placeholders replaced
        by actual values.

    """
    print(yaml_data.model_dump())
    with open(template_path, 'r') as yaml_file:
        file = yaml_file.read()
    return file.format(replicas=yaml_data.request_rate,
                       meta_name=yaml_data.duration_minutes)


def save_config(data_path: str, yaml_data: str):
    """Take the data and adds it to a yaml file.

    It takes the configuratoin data and adds it to a yaml,
    either creates a new file or overwrites existing file.

    Arguments:
        data_path: path to where the newly generated YAML content should be placed.
        yaml_data: the data content that should be placed in the YAML file,
        should be in the form of the Yaml_tamplate with the placeholders replaced.

    """
    with open(data_path, 'w') as yaml_file:
        yaml_file.write(yaml_data)


@app.post("/configure-yaml")
def configure_yaml(config_model: ConfigModel):
    """Handle API requests to generate and save a specific YAML configuration file.

    This endpoint takes a configuration model, injects its values into a,
    base YAML template, and writes the final configuration to a,
    specification file.

    Args:
       config_model (ConfigModel): A Pydantic model containing the,
           configuration parameters provided in the request body.

    Returns:
       we do not know for now.

    """
    reformed_config = render_yaml("yaml_files/config.yaml", config_model)
    save_config("yaml_files/given_specs.yaml", reformed_config)
    return {"hello": "world"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
