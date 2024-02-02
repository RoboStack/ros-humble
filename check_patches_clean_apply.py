# Useful script when checking whether patches apply cleanly.
# First, run `vinca` (without `-m` flag) to generate a recipe.yaml.
# Then, run this script to generate a new pseudo list that only contains sources that have patches applied.
# This you can then run through `boa` which will try and apply the patches.

import yaml
import shutil
import os

SCRIPT_DIR = './'

shutil.move(SCRIPT_DIR + '/recipe.yaml', SCRIPT_DIR + '/recipe.yaml.bak')

# Load the YAML file
with open('recipe.yaml.bak', 'r') as file:
    data = yaml.safe_load(file)

prepend_data = {
    'package': {
        'name': 'ros-dummy',
        'version': '2024.01.17'
    }
}

append_data = {
    'build': {
        'number': 0
    },
    'about': {
        'home': 'https://www.ros.org/',
        'license': 'BSD-3-Clause',
        'summary': 'Robot Operating System'
    },
    'extra': {
        'recipe-maintainers': [
            'ros-forge'
        ]
    }
}

# Filter out entries without 'patches'
filtered_data = [entry for entry in data['source'] if 'patches' in entry]

final_data = {**prepend_data, 'source': filtered_data, **append_data}

# Write the filtered data back to a YAML file
with open('recipe.yaml', 'w') as file:
    yaml.dump(final_data, file, sort_keys=False)
