#from subprocess import Popen
import argparse
import os
import subprocess
import shutil
import hashlib
import datetime


def build_recipes(args):
    time = datetime.datetime.today()

    if os.path.exists(f"{args.source}/recipes/"):
        shutil.rmtree(f"{args.source}/recipes/")
    
    os.mkdir(f"{args.source}/recipes")

    br = os.popen(f"cd {args.source} && vinca -m").read()
    print(br)
    
    with open(f"logs/boa_recipe_log_{time}.txt", 'w') as file:
        file.write(br)

def build_packages(args):
    time = datetime.datetime.today()
    os.popen(f"cd {args.source} && boa build recipes -m ./.ci_support/conda_forge_pinnings.yaml -m ./conda_build_config.yaml > '../logs/boa_package_log_{time}.txt' 2>&1").read()
    #br = Popen(f"ros_build_recipes.bat {args.source}")
    #bp = Popen("ros_build_packages.bat")
    #input("Press any key to continue")
    return f"logs/boa_package_log_{time}.txt"

def get_argparser():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('-s', '--source', type=str, default="ros-humble", help="Directory of robostack")
    return parser

def run_all(args):
    build_recipes(args)
    return build_packages(args)
    





if __name__ =="__main__":
    parser = get_argparser()
    args = parser.parse_args()
    run_all(args)