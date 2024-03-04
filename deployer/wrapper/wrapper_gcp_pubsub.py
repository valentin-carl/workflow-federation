# might look like error here but file will be moved, which makes import correct
from user_main import handler
import wrapper
import functions_framework


@functions_framework.cloud_event
def wrapper_gcp(cloud_event):

    # get data & workflow
    try:
        workflow = cloud_event.data["workflow"]
    except KeyError as e:
        print("workflow information missing; error")
        print(e)
        return {
            "statusCode": 400
        }
    try:
        input = cloud_event.data["body"]
    except KeyError as e:
        print("no function input -- assuming intentional")
        print(e)
        input = None

    # 1) update workflow: remove the current step
    updated_workflow = wrapper.update_workflow(workflow)

    # 2) if the next step pre-fetches data, call it here
    #   => this means it will get the actual function input from somewhere else (if any is expected)
    current_step = wrapper.get_current_step(workflow)
    if current_step["pre-fetch"]:
        # None input because not known yet
        wrapper.invoke_next(updated_workflow, None)

    # 3) if this current step pre-fetches
    #   a) pre-fetch the data
    #   b) if the handler expects an additional input, get the function input from somewhere (external)
    data = None
    if current_step["pre-fetch"]:
        print("pre-fetching data")
        data = wrapper.prefetch_data(current_step)
        # there might be some time between when the pre-fetching is done and when the inputs are ready
        # this means we might wait here a bit
        print("retreiving function input")
        input = wrapper.get_function_input(current_step)
    else:
        print("nothing to pre-fetch")

    # 4) call the function handler with (data, function_input)
    # data might be None
    result = handler(data, input)

    # 5) if the next step pre-fetches, upload the function input to somehwere the next step can find it
    # => the next step will have already been invoked earlier (without any function input)
    next = wrapper.get_next_step(workflow)
    if next is not None:
        if wrapper.get_next_step(workflow)["pre-fetch"]:
            print("uploading function input")
            wrapper.upload_function_input(result)
        # else invoke the next step with {"workflow": ..., "body": handler_output}
        else:
            # next function hasn't been invoked yet
            print("invoking next step")
            wrapper.invoke_next(workflow, result)
    else:
        print("reached end of workflow")
