import json
import os
import sys
import subprocess
import shutil

from enum import Enum


config = "../config.json"


class Provider(Enum):
    AWS = "aws"
    GCP = "google"
    tinyFaaS = "tinyFaaS"


def create_service(provider: Provider) -> None:

    # TODO create custom template to use for creation here
    # https://forum.serverless.com/t/custom-creation-templates/2828

    cmd = f"cd ../deployment && sls create --template {provider.value}-python3"

    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"result of service creation: {result.stdout}")

    except subprocess.CalledProcessError as e:
        print(f"Error: {e.with_traceback()}")
        sys.exit(1)


def get_provider(function: dict) -> Provider:
    match function["provider"]:
        case "aws":
            return Provider.AWS
        case "google":
            return Provider.GCP
        case "tinyFaaS":
            return Provider.tinyFaaS
        case _:
            raise ValueError(f"Invalid provider: {function['provider']}")


if __name__ == '__main__':

    with open(config, 'r') as f:
        c = json.load(f)
    functions = c["functions"]

    # create deployment dir (or check if it exists)
    # TODO remove the directory at the end
    if not os.path.exists("../deployment"):
        os.makedirs("../deployment")
    else:
        print("Error: Deployment directory already exists.")
        sys.exit(1)

    # for each function, create subdir
    for function in functions.keys():
        os.makedirs(f"../deployment/{function}/function") # function subdir relevant for `serverless.yml` and import in wrapper
        create_service(get_provider(function))

    # copy handler + correct wrapper
    for function in functions.keys():
        shutil.copyfile(f"../deployment/check/function/main.py", f"../deployment/{function}/function/main.py")
        shutil.copyfile(f"../deployment/check/function/wrapper_{get_provider(function)}.py", f"../deployment/{function}/function/wrapper_{get_provider(function)}.py")

    # create `serverless.yml` files


    # deploy all services 
    # TODO use subprocess to call `sls deploy` for each service
    # TODO use serverless compose: https://www.serverless.com/blog/serverless-framework-compose-multi-service-deployments


