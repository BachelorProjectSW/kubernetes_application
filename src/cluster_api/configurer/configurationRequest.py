from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn


class ConfigModel(BaseModel):
    """Model with the configuration for the nodes.

    model of configurations for a run of a experiment on a bunch of nodes.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        total_context_window: the number of tokens allowed.
        request_rate: maximum number of requests in the span of a minute.
        duration_minutes: the number of minutes the experiment shoudl take place.
        scaling_ interval: the time in which the experient should add nodes.
        node_priority: the order in which the nodes are turned on and off.

    """

    experiment_id: str
    total_context_window: int
    request_rate: int
    duration_minutes: int
    scaling_interval: int
    node_priority: str


app = FastAPI()


def render_yaml(template_path: str, yaml_data: ConfigModel):
    """Read a yaml Template amd injects conficuration values into the placeholders.

    the function loads template and uses Python´s string formatting,
    to map 'ConfigModel' to the template keys.

    Arguments:
        template_path: the path to the YAML template file.
        yaml_data: the configuration data with the values that shoudl be injected into.
        the template in the form of the "ConfiModel".

    Returns:
        str: The rendered YAML content as a string, with placeholders replaced
        by actual values.

    """
    print(yaml_data.model_dump())
    with open(template_path, 'r') as yaml_file:
        file = yaml_file.read()
    return file.format(replicas=yaml_data.total_context_window,
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
