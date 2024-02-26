from main import handler # main is supposed to be in the same dir (doesn't reference deploymer.main but a main.py with the handler function)
from wrapper import *    # import all workflow functions


# this will be listed as the handler in the `serverless.yml` file
def wrapper_aws(event: dict, context: any) -> dict:

    """
    The event will consist of two parts:
    {
        "body": {...},
        "workflow": {...}
    }
    The "body" is the actual function input, the workflow will be handled by the wrapper.

    # - the function handler always has the same format
        def handler(data, function_input)
    # - it will be moved by into the same directory as the wrapper by the deployer
    # - the wrapper calls the function handler and does the (un-)wrapping on the request & output
    # - the wrapper also handles the workflow choreography
        => defined in wrapper.py
    """

    # 1) update workflow: remove the current step
    workflow = event["workflow"]
    updated_workflow = update_workflow(workflow)

    # 2) if the next step pre-fetches data, call it here
    #    => this means it will get the actual function input from somewhere else (if any is expected)
    current_step = get_current_step(workflow)
    if current_step["pre-fetch"]:
        invoke_next(updated_workflow, None)

    # 3) if this current step pre-fetches
    #    a) pre-fetch the data
    #    b) if the handler expects an additional input, get the function input from somewhere (external) 
    data = None
    if current_step["pre-fetch"]:
        print("pre-fetching data")
        data = prefetch_data(current_step)
        # there might be some time between when the pre-fetching is done and when the inputs are ready
        # this means we might wait here a bit
        print("retreiving function input")
        input = get_function_input(current_step)
    else: 
        print("nothing to pre-fetch")
    
    # 4) call the function handler with (data, function_input)
    # data might be None
    result = handler(data, input)

    # 5) if the next step pre-fetches, upload the function input to somehwere the next step can find it
    # => the next step will have already been invoked earlier
    if get_next_step(workflow)["pre-fetch"]:
        print("uploading function input")
        upload_function_input(result)
    # else invoke the next step with {"workflow": ..., "body": handler_output}
    else:
        print("invoking next step")
        invoke_next(workflow, result)

    return {
        "statusCode": 200,
    }
