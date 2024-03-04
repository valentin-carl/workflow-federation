import json
import os
import sys
import subprocess
import shutil

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
            "architecture": "arm64"
        },
        "functions": {
            fn.name: {
                "handler": "wrapper_aws.wrapper_aws",
                "url": fn.url,
                "events": [
                    {
                        "http": {
                            "path": fn.path,
                            "method": fn.method,
                            "async": fn.invokeAsync 
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
        "service": fn.service,
        "provider": {
            # TODO add memory/timeout configuration
            "name": "google",
            "runtime": "python39",  # newest version supported by serverless
            "project": project
        },
        "frameworkVersion": sls.frameworkVersion,
        "functions": {
            fn.name: {
                "handler": "wrapper_gcp",
                "events": [
                    {
                        "event": {
                            "eventType": "providers/cloud.pubsub/eventTypes/topic.publish",
                            "resource": 'projects/${self:provider.project, \"\"}/topics/my-topic'
                        }
                    }
                ]
            }
        },
        "plugins": [
            "serverless-google-cloudfunctions"
        ]
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

        case _:
            raise TypeError(f"unknown provider {fn["provider"]} is not supported")
    return res


def handle_aws_requirements(requirementsPath: str, targetDir: str) -> None:

    cmd = f"pip install -t {targetDir} -r {requirementsPath}"

    try:
        print(f"installing requirements for aws lambda function")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"result of requirements installation: {result.stdout}")
        print(f"error: {result.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"couldn't install requirements {requirementsPath} for lambda function")
        print(f"Error: {e.with_traceback(e.__traceback__)}")
        sys.exit(1)


def generate_serverless_compose(functions: list[str]) -> str:
    res = {"services": {}}
    for function in functions:
        res["services"][f"{function}-service"] = {"path": function}
    print(f"serverless-compose: {dict2yaml(res)}")
    return res


# deploy all services 
# - Option 1: use serverless compose: https://www.serverless.com/blog/serverless-framework-compose-multi-service-deployments
# - Option 2: use subprocess to call `sls deploy` for each service


def main() -> None:

    with open(config, 'r') as f:
        c = json.load(f)

    functions = c["functions"]
    s = c["serverless"]  # TODO turn this into a `Serverless` object
    serverless = Serverless(s["org"], s["app"], s["frameworkVersion"])

    # create a new directory for the deployment
    print("creating deployment directory")
    if not os.path.exists("../deployment"):
        os.makedirs("../deployment")
    else:
        print("error: deployment directory already exists.")
        sys.exit(1)

    deployed_fns = []

    # create new subdir for each function structure according to provider
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

        match fn.provider:
            # TODO add prints?
            case Provider.AWS:
                """
                expected structure:
                ./
                - main.py
                - wrapper_aws.py
                - wrapper.py
                - serverless.yml
                - requirements.txt
                - module-1/
                    - ...
                - module-2/
                    - ...
                """

                # 1. main.py
                src = f"../functions/{fn.name}/main.py"
                dst = f"../deployment/{fn.name}/main.py"
                shutil.copyfile(src, dst)

                # 2. aws wrapper + wrapper
                src = f"./wrapper/wrapper_aws.py"
                dst = f"../deployment/{fn.name}/wrapper_aws.py"
                shutil.copyfile(src, dst)

                src = f"./wrapper/wrapper.py"
                dst = f"../deployment/{fn.name}/wrapper.py"
                shutil.copyfile(src, dst)

                # 3. serverless.yml
                sls = generate_serverless(c, serverless, fn)
                with open(f"../deployment/{fn.name}/serverless.yml", "w") as file:
                    file.write(sls)

                # 4. requirements
                src = f"../functions/{fn.name}/requirements.txt"
                dst = f"../deployment/{fn.name}/requirements.txt"
                shutil.copyfile(src, dst)

                # 5. download imported module code
                handle_aws_requirements(dst, f"../deployment/{fn.name}/") 

            case Provider.GCP:
                """
                expected structure:
                ./
                - main.py (previously `wrapper_gcp_pubsub.py`)
                - user_main.py (previously main.py)
                - wrapper.py
                - serverless.yml
                - requirements.txt
                """

                # 1. main.py
                src = f"../functions/{fn.name}/main.py" 
                dst = f"../deployment/{fn.name}/user_main.py"
                shutil.copyfile(src, dst)

                # 2. google cloud wrapper & wrapper.py
                src = f"./wrapper/wrapper_gcp_pubsub.py"
                dst = f"../deployment/{fn.name}/main.py"
                shutil.copyfile(src, dst) 

                src = f"./wrapper/wrapper.py"
                dst = f"../deployment/{fn.name}/wrapper.py"
                shutil.copyfile(src, dst) 

                # 3. serverless.yml
                sls = generate_serverless(c, serverless, fn)
                with open(f"../deployment/{fn.name}/serverless.yml", "w") as file:
                    file.write(sls)

                # 4. requriements
                src = f"../functions/{fn.name}/requirements.txt"
                dst = f"../deployment/{fn.name}/requirements.txt"
                shutil.copyfile(src, dst)

            case Provider.tinyFaaS:
                """
                expected structure:
                ./
                - serverless.yml
                - functions/
                    - `function-name`/
                        - main.py
                        - requirements.txt
                        - wrapper.py
                        - wrapper_tinyfaas.py
                # TODO make sure the fn.fn import stuff from tinyfaas works if the fn function isn't in main.py
                # TODO this sturcture should work for deploying (although sls says the opposite), but test with a different function than email
                """

                # serverless-tinyfaas expects a slightly different stucture than sls for aws/google
                os.makedirs(f"../deployment/{fn.name}/functions/{fn.name}")

                # 1. main.py
                src = f"../functions/{fn.name}/main.py" 
                dst = f"../deployment/{fn.name}/functions/{fn.name}/main.py"
                shutil.copyfile(src, dst)

                # 2. tinyfaas wrapper & wrapper.py
                src = f"./wrapper/wrapper_tinyfaas.py"
                dst = f"../deployment/{fn.name}/functions/{fn.name}/wrapper_tinyfaas.py"
                shutil.copyfile(src, dst) 

                src = f"./wrapper/wrapper.py"
                dst = f"../deployment/{fn.name}/functions/{fn.name}/wrapper.py"
                shutil.copyfile(src, dst) 
                
                # 3. serverless.yml
                sls = generate_serverless(c, serverless, fn)
                with open(f"../deployment/{fn.name}/serverless.yml", "w") as file:
                    file.write(sls)

                # 4. requriements
                src = f"../functions/{fn.name}/requirements.txt"
                dst = f"../deployment/{fn.name}/functions/{fn.name}/requirements.txt"
                shutil.copyfile(src, dst)

        # store to create serverless compose yml later
        deployed_fns.append(fn.name)

    # generate the serverless compose file
    sc = generate_serverless_compose(deployed_fns)
    print(sc)
    with open(f"../deployment/serverless-compose.yml", "w") as file:
        file.write(dict2yaml(sc))
    
    # TODO deploy!
    #subprocess.run("cd ../deployment && sls deploy", shell=True, check=True)
    

if __name__ == '__main__':
    main()
