# ROS-Humble-GitHub-Actions

An automated LLM-powered patching system for [RoboStack/ros-humble](https://github.com/RoboStack/ros-humble).

# Overview

This project extends the original RoboStack [ROS-Humble](https://github.com/RoboStack/ros-humble/) repository by implementing a Large Language Model (LLM) workflow that automatically generates and applies patches to the RoboStack project.

# Prerequisites

 - Runs on Ubuntu Linux (Windows and macOS not supported)
 - [Ollama](https://ollama.com/) for LLM API

# Setup/Installation

1. Clone the repository

```bash
cd <desired-project-location>
git clone https://github.com/Striker146/ros-humble-github-actions.git
```

2. Create and configure development environment

```bash
micromamba create -n robostackenv python=3.11
micromamba activate robostackenv
micromamba config append channels conda-forge
micromamba config append channels robostack-staging
micromamba install pip conda-build anaconda-client mamba conda catkin_pkg ruamel_yaml rosdistro empy networkx requests boa
```

3. Install additional required packages

```bash
pip install git+https://github.com/RoboStack/vinca.git --no-deps
pip install GitPython
```

**Note:** If running Ollama on a different machine or VM, follow the [network configuration guide](https://github.com/ollama/ollama/blob/main/docs/faq.md#setting-environment-variables-on-windows) to enable LLM access across your local network.

# Basic Usage

Activate the LLM workflow from the project root:

```bash
micromamba activate robostackenv
python .scripts/run_patch_workflow.py --ip <LLM_IP_ADDRESS> --port <LLM_PORT> --model <LLM_MODEL>
```

# Development Optimisation

For development work, you can significantly reduce build times (from hours to minutes) using the `--skip_existing` flag. Here's how to set it up:
1. Create a modified configuration:
   - Copy `vinca_linux_64.yaml` to `vinca.yaml`.
   - Under `packages_select_by_deps:`, remove all entries and add only `  - ros_base`.
   - Increment the `build_number` by 1.
2. Build the base packages:
```bash
python .scripts/builder.py
```
3. After the build completes, copy the build directory to an accessible location.
4. You can now use the `skip_existing` flag in the workflow by using the copied directory:
   
```bash
python .scripts/run_patch_workflow.py --ip <LLM_IP_ADDRESS> --port <LLM_PORT> --model <LLM_MODEL> --skip_existing <ROS_BASE_BUILD_DIR>
```

This ensures that the ROS Base package and it dependencies are not rebuilt, but allows for all other packages to be built.

# Attribution

Development setup instructions adapted from Robostack's [contribution guide](https://robostack.github.io/Contributing.html).
