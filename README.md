# RoboStack (for ROS humble)

Note:  ROS humble is experimental. [ROS noetic](https://github.com/RoboStack/ros-noetic) is recommended for most users at this time.

[![Conda](https://img.shields.io/conda/dn/robostack-humble/ros-humble-desktop?style=flat-square)](https://anaconda.org/robostack/)
[![Gitter](https://img.shields.io/gitter/room/RoboStack/Lobby?style=flat-square)](https://gitter.im/RoboStack/Lobby)
[![GitHub Repo stars](https://img.shields.io/github/stars/robostack/ros-humble?style=flat-square)](https://github.com/RoboStack/ros-humble/)
[![QUT Centre for Robotics](https://img.shields.io/badge/collection-QUT%20Robotics-%23043d71?style=flat-square)](https://qcr.github.io/)

[![Platforms](https://img.shields.io/badge/platforms-linux%20%7C%20win%20%7C%20macos%20%7C%20macos_arm64%20%7C%20linux_aarch64-green.svg?style=flat-square)](https://github.com/RoboStack/ros-humble)
[![Azure DevOps builds (branch)](https://img.shields.io/github/workflow/status/RoboStack/ros-humble/build_linux/buildbranch_linux?label=build%20linux&style=flat-square)](https://github.com/RoboStack/ros-humble/actions/workflows/linux.yml)
[![Azure DevOps builds (branch)](https://img.shields.io/github/workflow/status/RoboStack/ros-humble/build_win/buildbranch_win?label=build%20win&style=flat-square)](https://github.com/RoboStack/ros-humble/actions/workflows/win.yml)
[![Azure DevOps builds (branch)](https://img.shields.io/github/workflow/status/RoboStack/ros-humble/build_osx/buildbranch_osx?label=build%20osx&style=flat-square)](https://github.com/RoboStack/ros-humble/actions/workflows/osx.yml)
[![Azure DevOps builds (branch)](https://img.shields.io/github/workflow/status/RoboStack/ros-humble/build_osx/buildbranch_osx_arm64?label=build%20osx-arm64&style=flat-square)](https://github.com/RoboStack/ros-humble/actions/workflows/osx_arm64.yml)
[![Azure DevOps builds (branch)](https://img.shields.io/github/workflow/status/RoboStack/ros-humble/build_linux/buildbranch_linux_aarch64?label=build%20aarch64&style=flat-square)](https://github.com/RoboStack/ros-humble/actions/workflows/linux_aarch64.yml)

[![GitHub issues](https://img.shields.io/github/issues-raw/robostack/ros-humble?style=flat-square)](https://github.com/RoboStack/ros-humble/issues)
[![GitHub closed issues](https://img.shields.io/github/issues-closed-raw/robostack/ros-humble?style=flat-square)](https://github.com/RoboStack/ros-humble/issues?q=is%3Aissue+is%3Aclosed)
[![GitHub pull requests](https://img.shields.io/github/issues-pr-raw/robostack/ros-humble?style=flat-square)](https://github.com/RoboStack/ros-humble/pulls)
[![GitHub closed pull requests](https://img.shields.io/github/issues-pr-closed-raw/robostack/ros-humble?style=flat-square)](https://github.com/RoboStack/ros-humble/pulls?q=is%3Apr+is%3Aclosed)

[__Table with all available packages & architectures__](https://robostack.github.io/humble.html)

## Why ROS and Conda?
Welcome to RoboStack, which tightly couples ROS with Conda, a cross-platform, language-agnostic package manager. We provide ROS binaries for Linux, macOS, Windows and ARM (Linux). Installing other recent packages via conda-forge side-by-side works easily, e.g. you can install TensorFlow/PyTorch in the same environment as ROS humble without any issues. As no system libraries are used, you can also easily install ROS humble on any recent Linux Distribution - including older versions of Ubuntu. As the packages are pre-built, it saves you from compiling from source, which is especially helpful on macOS and Windows. No root access is required, all packages live in your home directory. We have recently written up a [paper](https://arxiv.org/abs/2104.12910) and [blog post](https://medium.com/robostack/cross-platform-conda-packages-for-ros-fa1974fd1de3) with more information.

## Attribution
If you use RoboStack in your academic work, please refer to the following paper:
```bibtex
@article{FischerRAM2021,
    title={A RoboStack Tutorial: Using the Robot Operating System Alongside the Conda and Jupyter Data Science Ecosystems},
    author={Tobias Fischer and Wolf Vollprecht and Silvio Traversaro and Sean Yen and Carlos Herrero and Michael Milford},
    journal={IEEE Robotics and Automation Magazine},
    year={2021},
    doi={10.1109/MRA.2021.3128367},
}
```

## Installation

To get started with conda (or mamba) as package managers, you need to have a base conda installation. Please do _not_ use the Anaconda installer, but rather start with [`miniforge` / `mambaforge`](https://github.com/conda-forge/miniforge) or [`miniconda`](https://docs.conda.io/en/latest/miniconda.html), which are much more "minimal" installers. These installers will create a "base" environment that contains the package managers conda (and mamba if you go with `mambaforge`). After this installation is done, you can move on to the next steps.

> Note: Make sure to _not_ install the ROS packages in your base environment as this leads to issues down the track. On the other hand, conda and mamba must not be installed in the `ros_humble` environment, they should only be installed in base. Also do not source the system ROS environment, as the `PYTHONPATH` set in the setup script conflicts with the conda environment.

```bash
# if you don't have mamba yet, install it first:
conda install mamba -c conda-forge

# now create a new environment
mamba create -n ros_humble ros-humble-desktop python=3.10 -c robostack-humble -c conda-forge --no-channel-priority --override-channels
conda activate ros_humble

# optionally, install some compiler packages if you want to e.g. build packages in a colcon_ws:
mamba install compilers cmake pkg-config make ninja colcon-common-extensions

# on Windows, install Visual Studio 2017 or 2019 with C++ support 
# see https://docs.microsoft.com/en-us/cpp/build/vscpp-step-0-installation?view=msvc-160

# on Windows, install the Visual Studio command prompt via Conda:
mamba install vs2019_win-64

# note that in this case, you should also install the necessary dependencies with conda/mamba, if possible

# reload environment to activate required scripts before running anything
# on Windows, please restart the Anaconda Prompt / Command Prompt!
conda deactivate
conda activate ros_humble

# if you want to use rosdep, also do:
mamba install rosdep
rosdep init  # note: do not use sudo!
rosdep update
```

**Note: at the moment on Windows only the Command Prompt terminal is supported, while Powershell is not supported.**

## Reporting issues
Feel free to open issues in this repository's [issue tracker](https://github.com/RoboStack/ros-humble/issues) (please check whether your problem is already listed there before opening a new issue) or come around on [Gitter](https://gitter.im/RoboStack/Lobby) to have a chat / ask questions. Please note that this repository is _not an official distribution of ROS_ and relies on volunteers. It is further highly experimental - unfortunately things might not work immediately out-of-the-box, although we try our best.

## Jupyter-ROS and JupyterLab-ROS (note: there is no support for ROS2 yet in these projects)
To install Jupyter-ROS and JupyterLab-ROS which provide interactive experiences for robotics developers in Jupyter Notebooks, please see the relevant repositories for [Jupyter-ROS](https://github.com/RoboStack/jupyter-ros) and [JupyterLab-ROS](https://github.com/RoboStack/jupyterlab-ros).

## FAQ

#### When trying to build packages, you get CMake errors that packages could not be found, such as
```
CMake Error at /Users/me/miniconda3/envs/ros_humble/share/catkin/cmake/catkinConfig.cmake:83 (find_package):
  Could not find a package configuration file provided by "std_msgs" with any
  of the following names:

    std_msgsConfig.cmake
    std_msgs-config.cmake
```
First, make sure that the package is installed; in the example case it would be `mamba install ros-humble-std-msgs`. You can use `rosdep` to install dependencies. Second, make sure that your `CMAKE_PREFIX_PATH` points to your `ros_humble`, in the example case you could achieve this by `export CMAKE_PREFIX_PATH=/Users/me/miniconda3/envs/ros_humble/`. This might happen if `CMAKE_PREFIX_PATH` is not empty when you activate your `ros_humble`.

#### Can I use RoboStack in a non-conda virtual environment?
RoboStack is based on conda-forge and will not work without conda. However, check out [rospypi](https://github.com/rospypi/simple2) which can run in a pure Python virtualenv. rospypi supports tf2 and other binary packages.


## Contributing
This project is in early stages and we are looking for contributors to help it grow. Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for ways to contribute.

### Debugging / Running the "RoboStack" pipeline locally

The robostack project uses [vinca](https://github.com/RoboStack/vinca) to generate recipes from a yaml file. The yaml file is the `vinca_PLATFORM.yaml` files in this repository.

To walk through the steps of setting up vinca and running builds:

```bash
# make sure to add conda-forge to your channels in `~.condarc`
mamba install pip boa -c conda-forge

# install vinca
pip install git+https://github.com/RoboStack/vinca.git --no-deps

# move the vinca file you're interested in to `vinca.yaml`
cp vinca_linux_64.yaml vinca.yaml

# now you can run vinca. The platform argument is optional
vinca --platform=linux-64

# You can check the recipe and additional created files now
cat recipe.yaml
cat build_ament_cmake.sh ...

# To build the package(s) run boa.
# the -m applies the pinnings (versions) mentioned in the given yaml files
boa build . -m .ci_support/conda_forge_pinnings.yaml -m conda_build_config.yaml

# ALTERNATIVELY:
# Note you can also build "multiple" recipes which can be more efficient as not 
# all source tarballs are downloaded at once. 
vinca -m 
boa build recipes/ -m ... (as above)

# from this you can generate an azure pipeline locally, e.g.
vinca-azure -d recipes -t mytriggerbranch -p linux-64
# which will create a `linux.yml` file that contains the azure pipeline definition
```
