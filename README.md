# MCP Server for NAO Robot Control in Webots

This project integrates a NAO robot simulated in the Webots environment with the **Model Context Protocol (MCP)**. This allows controlling the robot and receiving data from it using large language models (LLMs), such as Claude, through MCP-supported clients (e.g., Claude Desktop).

## 🚀 Features

- **Direct Control**: Send commands to the robot (head movement, arm movement, walking) directly from an LLM.
- **Real-time Data Retrieval**: Access the robot's status, including motor positions and camera data.
- **Object Recognition**: Uses Webots' built-in recognition system to identify objects in the camera's field of view.
- **Efficient Architecture**: The MCP server runs in a separate thread within the Webots controller, ensuring direct and fast interaction without file operation delays.
- **Ease of Use**: Starts automatically with the simulation in Webots.

## 🏗️ Architecture

The project consists of two main components:

1.  `controllers/my_controller/my_controller.py`:
    - The main controller script launched by the Webots environment.
    - Responsible for all low-level robot control logic: initializing motors, camera, and animations.
    - Creates a command queue (`queue.Queue`) and a status dictionary (`dict`) for data exchange with the MCP server.
    - Starts the MCP server in a separate thread.
    - In the main simulation loop, it processes commands from the queue and updates the status dictionary.

2.  `mcp_robot_server.py`:
    - Contains the `RobotMCPServer` class, which encapsulates all the MCP server logic (`FastMCP`).
    - Takes the command queue and status dictionary in its constructor.
    - Defines **tools (`@mcp.tool`)** for performing actions (e.g., `set_head_position`) and **resources (`@mcp.resource`)** for retrieving data (e.g., `robot://status`).
    - When a tool is called, a command is placed in the queue, and the server waits for a signal from the controller that the command has been executed.

Communication between the controller and the server occurs directly in memory, ensuring high performance and responsiveness.

## ⚙️ How to Run

1.  **Open the project in Webots**: Launch Webots and open the `worlds/test.wbt` world file from this project.
2.  **Start the simulation**: Click the "Play" button (▶) on the simulation panel.
3.  **Automatic Launch**: Webots will automatically start the `my_controller.py` controller for the NAO robot.
4.  **Server Ready**: The controller, in turn, will start the MCP server. You will see messages in the Webots console about the successful initialization of the robot and the server launch.
5.  **Connect a client**: You can now connect to the running MCP server from any MCP client (e.g., Claude Desktop) to start controlling the robot.

## 🛠️ Available Tools and Resources

The server provides the following set of tools for controlling the robot:

- `get_robot_status()`: Get the full status of the robot.
- `set_head_position(yaw, pitch)`: Set the head position.
- `set_arm_position(arm, shoulder_pitch, shoulder_roll)`: Set the arm position.
- `start_head_scan()` / `stop_head_scan()`: Control head scanning.
- `get_recognized_objects()`: Get the list of recognized objects.
- `reset_robot_pose()`: Reset the robot's pose.
- `toggle_walking()`: Toggle walking on/off.
- `get_robot_capabilities()`: Get information about the robot's capabilities.

And corresponding resources for data retrieval (e.g., `robot://status`).
