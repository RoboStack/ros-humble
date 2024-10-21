import requests
import json
import re
from tkinter.filedialog import askopenfilename
from time import sleep
import tkinter as tk
from time import time
import argparse

print("hello world")
root = tk.Tk()
root.withdraw()

def get_argparser():
    parser = argparse.ArgumentParser(description="Process error and patch files.")
    # Add a required argument for the error file

    parser.add_argument(
        "-e", "--error", 
        required=False, 
        type=str, 
        default="etest.txt",
        help="Path to the error file"
    )

    # Add an optional argument for the patch file
    parser.add_argument(
        "-s", "--script_path", 
        required=False, 
        type=str,
        default="test.txt", 
        help="Path to the patch file (optional)"
    )
    return parser

def generate_AI_response(prompt):
    #"model":"llama3.1:8b-instruct-fp16"
    data = {"model":"llama3.1", "role": "system", "prompt":prompt, "stream": False}
    url = 'http://172.21.64.1:11434/api/generate'

    response = requests.post(url, json=data)
    response_json = response.json()
    print("HERE")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(F"Failed to get prompt. Got Error {response.status_code}")
    



def generate_repair(error, script):


    script_prompt = f"Here is the relevant script ```{script}```.\n"
    error_prompt = f"The error is that is causing the build to fail is \n ```{error} \n```. "
    
    prompt = "Recreate the script fully with the added fixes. " + error_prompt + script_prompt

    
    
    return generate_AI_response(prompt), prompt



def extract_response_code(text):
    code_blocks = re.findall(r'```(?:.*?)\n(.*?)\n```', text, re.DOTALL)
    patch_code = ''
    for block in code_blocks: 
        lines = block.split('\n')
        for line in lines:
            patch_code += line + '\n'
    return patch_code

def create_repair(error_file, output, script_file):
    print("Creating patch...")
    repair_response, prompt = generate_repair(script=script_file, error=error_file)
    print(repair_response["response"])
    repaired_patch = extract_response_code(repair_response["response"])
    repaired_file = open(f"{output}", "w")
    repaired_file.write(repaired_patch)
    print(f"Patch completed. The filename is '{repaired_file.name}'")
    repaired_file.close()



def fix(bad_script_path, error_log):
    script_file = open(bad_script_path,"r",encoding="utf-8").read()
    create_repair(error_file=error_log, script_file=script_file, output=bad_script_path)


if __name__ == "__main__":
    parser = get_argparser()
    args = parser.parse_args()
    fix(args)

"""
while(1):
    print("1: Generate a new Patch")
    print("2: Exit")
    user_inp = input("Choose an operation: ")
    if user_inp == "1":
        start_t = time()
        create_patch()
        end_t = time()
    elif user_inp == "2":
        print("Closing...")
        break
    print(f"Time Taken : {round(end_t - start_t)}")
"""