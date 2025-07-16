import unittest
import sys

import launch
from launch import LaunchDescription
import launch_ros.actions
import launch_testing.actions
import launch_testing.asserts

# Minimal URDF as a Python string
minimal_robot_urdf = """<?xml version="1.0"?>
<robot name="minimal_robot">
    <link name="base_link" />
    <link name="child_link" />
    <joint name="base_to_child" type="fixed">
        <parent link="base_link" />
        <child link="child_link" />
        <origin xyz="0 0 1" rpy="0 0 0" />
    </joint>
</robot>
"""

def generate_test_description():
    # Launch robot_state_publisher with our URDF
    rsp_node = launch_ros.actions.Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': minimal_robot_urdf}]
    )

    ld = LaunchDescription([
        rsp_node,
        launch_testing.actions.ReadyToTest()
    ])
    # We return a dictionary so we can refer to our node later if needed.
    return ld, {'rsp_node': rsp_node}

class TestRobotStatePublisher(unittest.TestCase):

    def test_node_output(self, proc_output):
        # Check that some output indicative of URDF parsing appears.
        # The robot_state_publisher usually logs "got segment ..." for each link.
        proc_output.assertWaitFor(
            expected_output="got segment", timeout=0.5, stream='stderr'
        )

# See https://github.com/RoboStack/ros-humble/pull/320#issuecomment-3078288316
@unittest.skipIf(sys.platform == "darwin", "Post‑shutdown exit‑code is either -6 or -9 on macOS, do not check it.")
@launch_testing.post_shutdown_test()
class TestRobotStatePublisherPostShutdown(unittest.TestCase):

    def test_exit_codes(self, proc_info):
        # Verify that all launched processes exited with code 0.
        launch_testing.asserts.assertExitCodes(proc_info)
