import pytest
import ruamel.yaml

from vinca import v1_selectors

yaml = ruamel.yaml.YAML()


# -----------------------------------------------------------------------------#
# Fixtures                                                                      #
# -----------------------------------------------------------------------------#
@pytest.mark.parametrize(
    "platform,expected",
    [
        (
            "linux-64",
            {"requirements": {"host": ["unix-tool"]}},
        ),
        (
            "win-64",
            {"requirements": {"host": ["win-tool"]}},
        ),
    ],
)
def test_basic_os_selector(platform, expected):
    src = """
    requirements:
      host:
        - if: unix
          then: unix-tool
        - if: win
          then: win-tool
    """
    data = yaml.load(src)
    assert v1_selectors.evaluate_selectors(data, target_platform=platform) == expected


def test_then_else_branch():
    src = """
    - if: linux
      then:
        k: 1
      else:
        k: 2
    """
    data = yaml.load(src)
    assert v1_selectors.evaluate_selectors(data, target_platform="linux-64") == [
        {"k": 1}
    ]
    assert v1_selectors.evaluate_selectors(data, target_platform="win-64") == [{"k": 2}]


def test_spliced_list():
    src = """
    host:
      - if: linux
        then:
          - linux-tool-1
          - linux-tool-2
      - always-tool
    """
    data = yaml.load(src)
    out = v1_selectors.evaluate_selectors(data, target_platform="linux-64")
    assert out["host"] == ["linux-tool-1", "linux-tool-2", "always-tool"]
    out2 = v1_selectors.evaluate_selectors(data, target_platform="win-64")
    assert out2["host"] == ["always-tool"]
