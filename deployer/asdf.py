import typing

from dataclasses import dataclass
from enum import Enum


class Provider(Enum):
    AWS = "aws"
    GCP = "google"
    tinyFaaS = "tinyfaas"


@dataclass
class DeploymentPlatform:
    provider: Provider
    region: str


@dataclass
class Serverless:
    org: str
    app: str
    frameworkVersion: int


class TinyFaaSEnv(Enum):
    JAVASCRIPT = "nodejs"
    PYTHON = "python3"
    BINARY = "binary"


@dataclass
class TinyFaaSNode:
    name: str
    url: str


@dataclass
class Function:
    name: str
    handler: str
    requirements: str
    provider: Provider
    region: typing.Optional[str]
    url: bool
    invokeAsync: bool
    method: str
    path: str
    service: str
    platformwrapper: str
    tinyFaaS_options: typing.Optional[dict]


def NewFunction(fName:str, fDict: dict) -> Function:

    # these fields are required for all providers
    # if one of them is missing, the deployment will fail
    try:
        name = fName.lower()
        handler = fDict["handler"]
        requirements = fDict["requirements"]
        match Provider(fDict["provider"].lower()):
            case Provider.AWS:
                provider = Provider.AWS
                platformwrapper = "wrapper_aws.py"
            case Provider.GCP:
                provider = Provider.GCP
                platformwrapper = "wrapper_gcp_pubsub.py"
            case Provider.tinyFaaS:
                provider = Provider.tinyFaaS
                platformwrapper = "wrapper_tinyfaas.py"
            case _:
                print("error while trying to create function instance")
                raise ValueError("Invalid provider")
    except KeyError as e:
        print("error while trying to create function instance")
        raise ValueError(f"Missing required field: {e}")

    # for tinyfaas function, the options are required
    if fDict.get("tinyFaaS_options", None) is None and provider == Provider.tinyFaaS:
        print("error while trying to create tinyfaas function instance")
        raise ValueError("tinyFaaS_options is required for tinyFaaS provider")

    # these can be replaced with default values
    try:
        url = fDict["url"]
        invokeAsync = fDict["invokeAsync"]
        method = fDict["method"]
        path = fDict["path"]
        service = fDict["service"]
        region = fDict["service"]
    except KeyError as e:
        print(e)
        print("one of [url|invokeAsync|method|path|service] is missing, using defaults for all")
        url = True
        invokeAsync = True
        method = "POST"
        path = name
        service = f"{name}-service"
        region = None

    return Function(
        name=name,
        handler=handler,
        requirements=requirements,
        provider=provider,
        region=region,
        url=url,
        invokeAsync=invokeAsync,
        method=method,
        path=path,
        service=service,
        platformwrapper=platformwrapper,
        tinyFaaS_options=fDict.get("tinyFaaS_options", None)
    )
