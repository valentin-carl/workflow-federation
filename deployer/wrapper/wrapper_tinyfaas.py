import typing
import json

from wrapper import *
from main import handler


def wrapper_tinyfaas(event: typing.Optional[str]) -> typing.Optional[str]:

    """
    event is None or a string containing the usual workflow data + input in json format
    """

    assert event is not None

    inputDict = json.loads(event)
    workflow = inputDict["workflow"]
    try:
        input = inputDict["body"] # function args | might not be part of event if this function pre-fetches
    except KeyError:
        print("no function input: this function pre-fetches data or takes no arguments")
        input = None

    # 1) update workflow: remove the current step
    updated_workflow = update_workflow(workflow)

    # 2) if the next step pre-fetches data, call it here
    #   => this means it will get the actual function input from somewhere else (if any is expected)
    current_step = get_current_step(workflow)
    if current_step["pre-fetch"]:
        invoke_next(updated_workflow, None)

    # 3) if this current step pre-fetches
    #   a) pre-fetch the data
    #   b) if the handler expects an additional input, get the function input from somewhere (external)
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

    return json.dumps({
        "statusCode": 200,
    })
