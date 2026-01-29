import networkx as nx
import yaml
import glob
import sys
import os

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# def setup_yaml():
#   """ https://stackoverflow.com/a/8661021 """
#   represent_dict_order = lambda self, data:  self.represent_mapping('tag:yaml.org,2002:map', data.items())
#   yaml.add_representer(OrderedDict, represent_dict_order)
# setup_yaml()

# the stages

"""
# use the official gcc image, based on debian
# can use verions as well, like gcc:5.2
# see https://hub.docker.com/_/gcc/
image: ubuntu:20.04

build:
  stage: build
  script:
    - echo "Hello"
"""


def main():
    metas = []

    for f in glob.glob(os.path.join(sys.argv[1], "*.yaml")):
        print(f)
        with open(f) as fi:
            metas.append(yaml.load(fi.read(), Loader=Loader))

    requirements = {}

    for pkg in metas:
        requirements[pkg["package"]["name"]] = (
            pkg["requirements"]["host"] + pkg["requirements"]["run"]
        )

    print(requirements)

    G = nx.DiGraph()
    for pkg, reqs in requirements.items():
        G.add_node(pkg)
        for r in reqs:
            if r.startswith("ros-"):
                G.add_edge(pkg, r)

    # import matplotlib.pyplot as plt
    # nx.draw(G, with_labels=True, font_weight='bold')
    # plt.show()

    tg = list(reversed(list(nx.topological_sort(G))))
    print(tg)
    print(requirements["ros-melodic-ros-core"])

    stages = []
    current_stage = []
    for pkg in tg:
        for r in requirements[pkg]:
            if r in current_stage:
                stages.append(current_stage)
                current_stage = []
        current_stage.append(pkg)

    stages.append(current_stage)

    print(stages)

    gitlab_template = {"image": "condaforge/linux-anvil-cos7-x86_64"}

    stage_names = []
    for i, s in enumerate(stages):
        stage_name = f"stage_{i}"
        stage_names.append(stage_name)
        for pkg in s:
            gitlab_template[pkg] = {
                "stage": stage_name,
                "script": [
                    'export FEEDSTOCK_ROOT="$CI_BUILDS_DIR"',
                    "export GIT_BRANCH=$CI_COMMIT_REF_NAME",
                    'export RECIPE_ROOT="$FEEDSTOCK_ROOT/recipe"',
                    "sed -i '$ichown -R conda:conda \"$FEEDSTOCK_ROOT\"' /opt/docker/bin/entrypoint",
                    ".scripts/build_linux.sh",
                ],
                "variables": {"CURRENT_BUILD_PKG_NAME": pkg},
                # 'needs': [r for r in requirements[pkg] if r.startswith('ros-')]
            }

    gitlab_template["stages"] = stage_names

    with open(".gitlab-ci.yml", "w") as fo:
        fo.write(yaml.dump(gitlab_template, Dumper=Dumper))
