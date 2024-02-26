"""
# workflow example
wf = {
    "steps": [
        {
            "id": 0,
            "function_name": "check",
            "node": "..."
        }
    ]
}
"""

def get_current_step(workflow: dict) -> dict:
    """
    return the function with the smallest id
    """
    minId = 1e12
    min = None
    for function in workflow["steps"]:
        if function["id"] < minId:
            minId = function["id"]
            min = function
    return min

def update_workflow(workflow: dict) -> dict:
    """
    :return: updated workflow and the current step
    """
    steps = workflow["steps"]
    current = get_current_step(workflow)
    steps.remove(current)
    workflow["steps"] = steps
    return workflow

def get_next_step(workflow: dict) -> dict:
    """
    find the next step to invoke
    # TODO update to enable fan-out, there could be multiple next steps to invoke
    """
    return get_current_step(update_workflow(workflow))

#
# TODO 
#

def upload_function_input(input: dict) -> None:
    pass

def invoke_next(function: dict, input: dict) -> dict:
    # TODO change inputs according to how function is actually used in function wrappers

    """
    this function assumes that the url for the next function triggers async invocation
    """

    pass

def prefetch_data(current_step: dict) -> None:
    pass

def get_function_input(current_step: dict) -> dict:
    pass
