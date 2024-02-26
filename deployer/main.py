import json
import os
import sys
import subprocess
import shutil
import typing

from asdf import Provider, Serverless, TinyFaaSEnv, TinyFaaSNode, Function, NewFunction

from utils import dict2yaml


config = "../config.json"


def create_service(provider: Provider) -> None:

    # TODO create custom template to use for creation here
    # https://forum.serverless.com/t/custom-creation-templates/2828
    match provider:
        case Provider.AWS:
            cmd = f"cd ../deployment && sls create --template aws-python3"
        case Provider.GCP:
            cmd = f"cd ../deployment && ls && sls create --template google-python"
        case Provider.tinyFaaS:
            # TODO which template to use for tinyfaas?
            cmd = f"cd ../deployment && sls create"

    try:
        print(f"---{provider}---")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"result of service creation: {result.stdout}")
        print(f"error: {result.stderr}")
        print(f"---{provider}---")

    except subprocess.CalledProcessError as e:
        print(f"Error: {e.with_traceback(e.__traceback__)}")
        sys.exit(1)

def get_provider(function: dict) -> Provider:
    match Provider(function["provider"].lower()):
        case "aws":
            return Provider.AWS
        case "google":
            return Provider.GCP
        case "tinyfaas":
            return Provider.tinyFaaS
        case _:
            raise ValueError(f"Invalid provider: {function['provider']}")


# this only works for functions, not docker containers
# TODO add support for docker containers
def generate_aws(sls: Serverless, fn: Function) -> str:
    result = {
        "org": sls.org,
        "app": sls.app,
        "service": fn.service,
        "frameworkVersion": sls.frameworkVersion,
        "provider": {
            "name": "aws",
            "timeout": 180,
            "runtime": "python3.10",
            "architecture": "arm"
        },
        "functions": {
            fn.name: {
                "handler": fn.handler,
                "events": [
                    {
                        "http": {
                            "path": fn.path,
                            "method": fn.method,
                            "url": fn.url,
                            "async": fn.invokeAsync  # TODO make sure this is supposed be `async` and not `invokeAsync`
                        }
                    }
                ]
            }
        }
    }
    if fn.region is not None:
        result["provider"]["region"] = fn.region
    return dict2yaml(result)

def generate_gcp(sls: Serverless, project: str, fn: Function) -> str:
    result = {
        "org": sls.org,
        "app": sls.app,
        "service": fn.service,
        "provider": {
            # TODO add memory/timeout configuration
            "name": "google",
            "runtime": "python3.10",
            "project": project
        },
        "frameworkVersion": sls.frameworkVersion,
        "functions": {
            fn.name: {
                "handler": fn.handler,
                "events": [
                    {
                        "eventType": "providers/cloud.pubsub/eventTypes/topic.publish",
                        "resource": "'projects/${self:provider.project, \"\"}/topics/my-topic'"
                    }
                ]
            }
        }
    }
    if fn.region is not None:
        result["provider"]["region"] = fn.region
    return dict2yaml(result)


def generate_tinyfaas(name: str, env: TinyFaaSEnv, threads: int, source: str, deployToNames: list[str], nodes: list[TinyFaaSNode]) -> str:
    result = {
        "custom": {
            "tinyfaas": {
                "functions": [
                    {
                        "name": name,
                        "env": env,
                        "threads": threads,
                        "source": source,
                        "deployTo": deployToNames
                    }
                ],
                "nodes": nodes
            }
        },
        "plugins": [
            "serverless-tinyfaas"
        ]
    }
    return dict2yaml(result)


def generate_serverless(config: dict, sls: Serverless, fn: Function) -> None:
    """
    generates the contents of a serverless.yaml file for different providers
    """
    print(f"generating serverless.yaml for provider {fn.provider}")
    res = ""
    match fn.provider:
        case Provider.AWS:
            res = generate_aws(sls, fn)
        case Provider.GCP:
            res = generate_gcp(sls, config["providers"]["GCP"]["project"], fn)
        case Provider.tinyFaaS:

            #
            # TEST THIS
            #

            assert fn.tinyFaaS_options is not None
            dir = lambda s: '/'.join(s.split('/')[:-1])
            assert dir(fn.handler) == dir(fn.requirements)
            source = dir(fn.handler)
            res = generate_tinyfaas(
                fn.name,
                fn.tinyFaaS_options["env"],
                fn.tinyFaaS_options["threads"],
                source,
                fn.tinyFaaS_options["deployTo"],
                config["providers"]["tinyFaaS"]["nodes"]
            )

            #
            # TEST THIS
            #

        case _:
            raise TypeError(f"unknown provider {fn["provider"]} is not supported")
    return res


def handle_aws_requirements() -> None:
    # TODO
    pass


def main():

    # TODO make sure the serverless-tinyfaas plugin is installed (check with subprocess + npm?)

    with open(config, 'r') as f:
        c = json.load(f)

    functions = c["functions"]
    providers = c["providers"]
    serverless = c["serverless"]  # TODO turn this into a `Serverless` object

    # create a new directory for the deployment
    print("creating deployment directory")
    if not os.path.exists("../deployment"):
        os.makedirs("../deployment")
    else:
        print("error: deployment directory already exists.")
        sys.exit(1)

    # create a new subdirectory/service/... for each function
    for function in functions.keys():

        print(function, functions[function])  # TODO remove
        fn = NewFunction(function, functions[function])

        # TODO remove
        if fn.name == "ocr" or fn.name == "tinyfaas-example":
            print("warning: skipping function OCR")
            continue

        # subdirectory
        print(f"> creating new subdir for {fn.name}")
        os.makedirs(f"../deployment/{fn.name}/") # TODO adjust accordingly in serverless.yml generating functions

        # copy function code
        # => assue code is called from `deployer` directory
        # => assume function code is in file `main.py` with a `handler` function
        print(f"> copying function code for {fn.name}")
        src, dst = f"../functions/{fn.name}/main.py", f"../deployment/{fn.name}/main.py"
        shutil.copyfile(src, dst)

        # copy requirements
        print(f"> copying requirements for {fn.name}")
        src, dst = f"../functions/{fn.name}/requirements.txt", f"../deployment/{fn.name}/requirements.txt"
        shutil.copyfile(src, dst)

        # handle requirements for AWS lambda functions
        # TODO

        # copy correct wrapper + wrapper.py
        print(f"> copying wrapper code for {fn.name}")
        src, dst = f"./wrapper/wrapper.py", f"../deployment/{fn.name}/wrapper.py"
        shutil.copyfile(src, dst)
        src, dst = f"./wrapper/{fn.platformwrapper}", f"../deployment/{function}/{fn.platformwrapper}"
        shutil.copyfile(src, dst)

        # generate the serverless.yml file
        sls = Serverless(serverless["org"], serverless["app"], serverless["frameworkVersion"])
        with open(f"../deployment/{fn.name}/serverless.yml", "w") as file:
            print(f"> creating serverless.yml for {fn.name}")
            file.write(generate_serverless(c, sls, fn))


    # TODO create serverless compose yml file

    # deploy all services 
    # TODO use subprocess to call `sls deploy` for each service
    # TODO use serverless compose: https://www.serverless.com/blog/serverless-framework-compose-multi-service-deployments

    # create service
    # for now: without templates and without matching porviders
    # maybe use this: https://forum.serverless.com/t/custom-creation-templates/2828
    # => which template to use for tinyFaaS?
    # FIXME
    # `sls create` ist nicht notwenig (geht auch nicht ohne template und keine lust ein eigenes zu erstellen!!)
    # stattdessesen: `sls deploy -c serverless.yml`
    # defür dann die serverless.yml schon vorher erstellen
    # TODO
    # wie geht das dann mit serverless compose? reicht nur das????
    # ---
    # jetzt erstmal: nur die serverless.yml schon erstellen und dann deployment nachdem alle dateien richtig angelegt sind (und aws dependencies runtergeladen sind)

if __name__ == '__main__':
    main()
