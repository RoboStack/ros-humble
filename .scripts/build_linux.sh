#!/usr/bin/env bash

# PLEASE NOTE: This script has been automatically generated by conda-smithy. Any changes here
# will be lost next time ``conda smithy rerender`` is run. If you would like to make permanent
# changes to this script, consider a proposal to conda-smithy so that other feedstocks can also
# benefit from the improvement.

set -xeuo pipefail
export PYTHONUNBUFFERED=1

export FEEDSTOCK_ROOT=`pwd`
export "CONDA_BLD_PATH=$HOME/conda-bld/"

curl -fsSL https://pixi.sh/install.sh | bash
export PATH="$HOME/.pixi/bin:$PATH"

for recipe in ${CURRENT_RECIPES[@]}; do
	pixi run -v rattler-build build \
		--recipe ${FEEDSTOCK_ROOT}/recipes/${recipe} \
		-m ${FEEDSTOCK_ROOT}/conda_build_config.yaml \
		-c robostack-staging -c conda-forge \
		--output-dir $CONDA_BLD_PATH

		# -m ${FEEDSTOCK_ROOT}/.ci_support/conda_forge_pinnings.yaml \

done

pixi run upload ${CONDA_BLD_PATH}/linux-*/*.conda --force
