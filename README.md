# Webots MCP Controller

This project provides a framework for controlling a NAO robot in the Webots simulator using the Model-Context-Protocol (MCP). It allows for interaction with the robot using natural language through compatible clients.

## Features

- **File-Based Communication**: A robust communication system between the MCP server and the Webots controller using `json` files.
- **Motor Position Validation**: All motor commands are validated against the robot's physical limits to prevent errors.
- **Motion Playback**: Play pre-recorded `.motion` files.
- **Sensing**: Access to camera and GPS data.
- **Actuator Control**: Control head, arms, and LEDs.
- **Dynamic Robot Discovery**: The server can handle multiple robots, identifying them by their `ROBOT_NAME`.

## Architecture

The system is composed of two main components:

1.  **`webots_mcp_server.py`**: 
    - This script runs the `FastMCP` server, exposing the robot's capabilities as tools.
    - It communicates with the Webots controller by writing commands to a `commands.json` file and reading the robot's state from a `status.json` file.
    - It handles multiple robots by creating separate data directories for each.

2.  **`controllers/my_controller_plus_mcp/my_controller_plus_mcp.py`**:
    - This is the main controller script for the NAO robot in Webots.
    - It runs in the Webots simulation environment and is responsible for all low-level robot control.
    - It continuously reads the `commands.json` file for new commands from the MCP server.
    - It writes the robot's current status (motor positions, sensor data) to the `status.json` file.

## How to Run

1.  **Open the project in Webots**: Launch Webots and open the `worlds/MCP-test.wbt` world file.
2.  **Start the simulation**: Click the "Play" button (▶).
3.  **Connect a client**: Connect to the project using an MCP client (e.g., Gemini CLI). The client is responsible for automatically starting the `webots_mcp_server.py` script based on its configuration. For example, a `settings.json` file for the client might contain:
    ```json
    "I-robot-mcp": {
      "command": "python.exe",
      "args": [
        "d:/webots-mcp/webots_mcp_server.py"
      ]
    }
    ```
4.  **Control the Robot**: Once the client is connected and the server is running, you can start interacting with the robot.

## Available Tools

The server provides the following tools for controlling the robot:

- `get_visual_perception(robot_name)`: Get an image from the robot's camera.
- `get_robot_position(robot_name)`: Get the robot's current position.
- `get_robot_status(robot_name)`: Get the full status of the robot.
- `set_head_position(robot_name, yaw, pitch)`: Set the head position.
- `set_arm_position(robot_name, arm, shoulder_pitch, shoulder_roll)`: Set the arm position.
- `reset_robot_pose(robot_name)`: Reset the robot's pose.
- `list_motions()`: List all available motions.
- `play_motion(robot_name, motion_name)`: Play a pre-recorded motion.
- `set_led_color(robot_name, color, part)`: Set the color of the robot's LEDs.
- `get_robot_capabilities(robot_name)`: Get information about the robot's capabilities.
- `check_webots_connection(robot_name)`: Check the connection with the Webots controller.
- `list_robots()`: List all active robots.