import requests
import re

def generate_AI_response(ip, prompt):
    #"model":"llama3.1:8b-instruct-fp16"
    data = {"model":"llama3.1", "role": "system", "prompt":prompt, "stream": False}
    url = f'http://{ip}:11434/api/generate'
    response = requests.post(url, json=data)
    response_json = response.json()
    print("HERE")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(F"Failed to get prompt. Got Error {response.status_code}")
    
def generate_prompt(error, script):
    script_prompt = f"Here is the relevant script ```{script}```.\n"
    error_prompt = f"The error is that is causing the build to fail is \n ```{error} \n```. "
    prompt = "Recreate the script fully with the added fixes. " + error_prompt + script_prompt
    return prompt

def extract_response_code(text):
    code_blocks = re.findall(r'```(?:.*?)\n(.*?)\n```', text, re.DOTALL)
    patch_code = ''
    for block in code_blocks: 
        lines = block.split('\n')
        for line in lines:
            patch_code += line + '\n'
    return patch_code

def fix(ip, bad_script_path, error_log):
    script_file = open(bad_script_path,"r",encoding="utf-8").read()
    print("Creating Repair...")
    prompt = generate_prompt(script=script_file, error=error_log)
    repair_response = generate_AI_response(ip, prompt)
    print(repair_response["response"])
    repaired_code = extract_response_code(repair_response["response"])
    repaired_file = open(f"{bad_script_path}", "w")
    repaired_file.write(repaired_code)
    print(f"Script completed. The filename is '{repaired_file.name}'")
    repaired_file.close()