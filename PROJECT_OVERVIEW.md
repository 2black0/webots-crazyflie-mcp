# Project Overview: NAO Robot Control in Webots

I have carefully studied the structure of your project and the `my_controller_plus_mcp.py` file.

Here are the key points I have highlighted:

*   **Purpose:** This script is a controller for the NAO robot in the Webots simulator.
*   **Architecture:** It acts as a "bridge" between the Webots simulation and an external control server (MCP).
*   **Communication:** Data exchange with the MCP server occurs through two files in the `data/` folder:
    *   `commands.json`: The controller reads commands from this file (e.g., turn head, play animation).
    *   `status.json`: The controller writes its current status to this file (motor positions, active actions).
*   **Robot Control:**
    *   **Movements:** The script can control individual motors (head, hands) directly.
    *   **Animations:** It loads and plays pre-made animation files (`.motion`) from the `motions/` folder. It is important that other commands are blocked while an animation is playing.
*   **Main Loop:** In an infinite loop of the Webots simulation, the script constantly checks for new commands and updates the status file.

Overall, this is a well-structured controller that separates the robot control logic from the control server logic.
