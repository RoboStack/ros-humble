#from subprocess import Popen
import os
import shutil
import datetime


def build_recipes():
    time = datetime.datetime.today()

    if os.path.exists(f"./recipes/"):
        print("Cleaning recipes")
        shutil.rmtree(f"./recipes/")
    
    os.mkdir(f"./recipes")

    br = os.popen(f"cd . && vinca -m").read()
    print(br)
    
    with open(f"./logs/boa_recipe_log_{time}.txt", 'w') as file:
        file.write(br)

def build_packages():
    time = datetime.datetime.today()
    os.popen(f"cd . && boa build recipes -m ./.ci_support/conda_forge_pinnings.yaml -m ./conda_build_config.yaml > './logs/boa_package_log_{time}.txt' 2>&1").read()
    #br = Popen(f"ros_build_recipes.bat {args.source}")
    #bp = Popen("ros_build_packages.bat")
    #input("Press any key to continue")
    return f"logs/boa_package_log_{time}.txt"


def run_all():
    build_recipes()
    return build_packages()
    





if __name__ =="__main__":
    run_all()