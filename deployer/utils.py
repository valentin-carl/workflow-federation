import yaml
import typing


def dict2yaml(data: dict) -> typing.Optional[str]:
    try:
        yaml_string = yaml.dump(data, default_flow_style=False)
        return yaml_string
    except Exception as e:
        print(f"Error converting dictionary to YAML: {e}")
        return None
