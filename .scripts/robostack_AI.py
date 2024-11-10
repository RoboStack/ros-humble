import requests
import re

def generate_AI_response(args, prompt):
    """
    Sends a prompt to an AI model server and retrieves the generated response.

    This function constructs a JSON payload with the specified model and prompt,
    sends it to the AI model server via a POST request, and returns the server's response.

    Args:
        args (Namespace): An object containing the following attributes:
            - model (str): The name or identifier of the AI model to use.
            - ip (str): The IP address of the AI model server.
            - port (int): The port number on which the AI model server is running.
        prompt (str): The input prompt to send to the AI model.

    Returns:
        dict: The JSON response from the AI model server.

    Raises:
        Exception: If the server returns a status code other than 200.

    Example:
        >>> prompt = "What will be the temperature of QUT @ Brisbane in 2030?"
        >>> response = generate_AI_response(args, prompt)
        >>> print(response)
        {'In Brisbane it's expected for temperatures to reach upwards of 48c.'}

    Notes:
        - Ensure that the AI model server is running and accessible at the specified IP address and port.
        - The server is expected to have be Ollama, meaning it will have an endpoint at '/api/generate' that accepts POST requests with a JSON payload.
    """
    data = {"model":f"{args.model}", "role": "system", "prompt":prompt, "stream": False}
    url = f'http://{args.ip}:{args.port}/api/generate'
    response = requests.post(url, json=data)
    response_json = response.json()
    print("HERE")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(F"Failed to get prompt. Got Error {response.status_code}")
    
def generate_prompt(error, script):
    """
    Constructs a prompt by embedding the provided error message and script.

    Args:
        error (str): The error message causing the build to fail.
        script (str): The relevant script associated with the error.

    Returns:
        str: A formatted prompt containing the error message and script.
    """
    script_prompt = f"Here is the relevant script ```{script}```.\n"
    error_prompt = f"The error is that is causing the build to fail is \n ```{error} \n```. "
    prompt = "Recreate the script fully with the added fixes. " + error_prompt + script_prompt
    return prompt

def extract_response_code(text):
    """
    Extracts code blocks from the provided text.

    This function searches for code blocks enclosed within triple backticks (```)
    in the input text and concatenates them into a single string.

    Args:
        text (str): The input text containing code blocks.

    Returns:
        str: A string containing all extracted code blocks concatenated together.
    """
    code_blocks = re.findall(r'```(?:.*?)\n(.*?)\n```', text, re.DOTALL)
    script_code = ''
    for block in code_blocks: 
        lines = block.split('\n')
        for line in lines:
            script_code += line + '\n'
    return script_code

def fix(args, bad_script_path, error_log):
    """
    Automates the repair of a faulty script using AI-generated suggestions.

    This function reads the content of a script that has encountered an error,
    generates a prompt combining the script and its error log, sends this prompt
    to an AI model to receive a suggested fix, extracts the corrected code from
    the AI's response, and overwrites the original script with the repaired code.

    Args:
        args (Namespace): Args from run_patch_workflow containing the following attributes:
            - model (str): The name or identifier of the AI model to use.
            - ip (str): The IP address of the AI model server.
            - port (int): The port number on which the AI model server is running.
        bad_script_path (str): The file path to the script that needs to be repaired.
        error_log (str): The error message or log associated with the script's failure.

    Returns:
        None

    Raises:
        Exception: If the AI model fails to provide a valid response or if the
                   repaired code cannot be extracted.
        IOError: If there is an error reading from or writing to the script file.

    Example:
        >>> from argparse import Namespace
        >>> args = Namespace(model='llama3.1:8b', ip='127.0.0.1', port=8000)
        >>> bad_script_path = 'path/to/faulty_script.py'
        >>> error_log = 'SyntaxError: unexpected EOF while parsing'
        >>> fix(args, bad_script_path, error_log)

    Notes:
        - Ensure that the AI model server is running and accessible at the specified IP address and port.
        - The function overwrites the original script file with the repaired code.
    """
    script_file = open(bad_script_path,"r",encoding="utf-8").read()
    print("Creating Repair...")
    prompt = generate_prompt(script=script_file, error=error_log)
    repair_response = generate_AI_response(args, prompt)
    print(repair_response["response"])
    repaired_code = extract_response_code(repair_response["response"])
    repaired_file = open(f"{bad_script_path}", "w")
    repaired_file.write(repaired_code)
    print(f"Script completed. The filename is '{repaired_file.name}'")
    repaired_file.close()