import os
import re

def identify_failed_package(path):
    with open(path) as f:
        pattern = r"Output:\s*(\S+)"
        f_data = f.read()
        match = re.findall(pattern, f_data)
        target = match[-1]
        if match:
            return target
        else:
            return NotImplementedError



def check(path):
    file = open(path,"rb")
    try:  # catch OSError in case of a one line file 
        file.seek(-2, os.SEEK_END)
        while file.read(1) != b'\n':
            file.seek(-2, os.SEEK_CUR)
    except OSError:
        file.seek(0)
    last_line = file.readline().decode()
    print(last_line)
    sampled = re.sub(r'[╵\s]', '', last_line)
    build_success = not bool(len(sampled))
    if  build_success:
        return build_success, None
    else:
        return build_success, identify_failed_package(path)


"""
def check(path, target):
    file = open(path,"r",encoding="utf-8").read()
    pattern = re.compile(f'Output: {target}.*', re.DOTALL)
    match = pattern.search(file)
    print(match.group())
"""


if __name__ == "__main__":
    path_1 =  "Patches/boa_log_fail.txt"
    path_2 =  "Patches/boa_build_suc.txt"
    target = "ros-humble-hardware-interface"
    build_success = check(path_1)

    print(f"Built Successfully: {build_success}")