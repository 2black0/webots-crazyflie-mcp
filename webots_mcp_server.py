'''
MCP Server for controlling the NAO robot in Webots.

This server works in conjunction with the Webots controller via the file system
and sockets to exchange commands and status.
'''

import asyncio
import base64
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_server.log',
    filemode='a',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Webots Robot Control Server")

# Paths for data exchange with the controller
DATA_DIR = Path(__file__).parent / "data"
COMMANDS_FILE = DATA_DIR / "commands.json"
STATUS_FILE = DATA_DIR / "status.json"

# Create the data directory
DATA_DIR.mkdir(exist_ok=True)

# Global variables for state
robot_status = {
    "running": False,
    "webots_connected": False,
    "head_position": {"yaw": 0.0, "pitch": 0.0},
    "arm_positions": {
        "left_shoulder_pitch": 1.5,
        "right_shoulder_pitch": 1.5,
        "left_shoulder_roll": 0.0,
        "right_shoulder_roll": 0.0
    },
    "robot_position": {"x": 0, "y": 0, "z": 0},
    "last_recognized_objects": [],
    "last_update": 0,
    "last_image_timestamp": 0
}

def load_status():
    """Loads the status from the file."""
    global robot_status
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                robot_status.update(data)
                logger.debug("Status loaded successfully.")
                return True
    except Exception as e:
        logger.error(f"Error loading status: {e}")
    return False

def save_command(command: dict):
    """Saves a command to a file for the controller."""
    try:
        command['timestamp'] = time.time()
        # Make sure the directory exists
        COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2, ensure_ascii=False)
        logger.info(f"Command '{command.get('action')}' saved successfully to {COMMANDS_FILE.resolve()}")
        return True
    except Exception as e:
        logger.error(f"Error saving command to {COMMANDS_FILE.resolve()}: {e}")
        return False



def wait_for_image_update(timeout=10.0):
    """Waits for an image update from the controller."""
    start_time = time.time()
    initial_image_time = robot_status.get('last_image_timestamp', 0)
    logger.info(f"Waiting for image update. Initial time: {initial_image_time}")

    while time.time() - start_time < timeout:
        load_status()
        if robot_status.get('last_image_timestamp', 0) > initial_image_time:
            logger.info("Image update detected.")
            return True
        time.sleep(0.1)
    logger.warning("Timeout waiting for image update.")
    return False


@mcp.tool()
def get_visual_perception() -> str:
    """
    Gets visual information from the robot's camera in jpg format.

    """
    logger.info("Visual information requested.")
    command = {
        "action": "get_camera_image"
    }

    if not save_command(command):
        logger.error("Error sending command to get image.")
        return "❌ Error sending command to get image"

    if not wait_for_image_update():
        logger.warning("Command to get image sent, but new image not received within timeout.")
        return "⚠️ Command sent, but new image not received"

    image_path = DATA_DIR / "camera_image.jpg"
    if not image_path.exists():
        logger.error(f"Image file not found at path: {image_path.resolve()}")
        return "❌ Image file not found after update"

    logger.info(f"Image successfully received: {image_path.resolve()}")
    return f"✅ Image received for analysis: {image_path.resolve()}"

@mcp.tool()
def get_robot_status() -> str:
    """Gets the current status of the robot."""
    logger.info("Robot status requested.")
    load_status()

    # Check if the status was updated recently (last 10 seconds)
    current_time = time.time()
    last_update = robot_status.get('last_update', 0)
    robot_status['running'] = (current_time - last_update) < 10.0
    logger.debug(f"Activity check: running={robot_status['running']} (last_update: {last_update})")


    status_info = {
        "running": robot_status['running'],
        "webots_connected": robot_status.get('webots_connected', False),
        "head_position": robot_status['head_position'],
        "arm_positions": robot_status['arm_positions'],
        "robot_position": robot_status.get('robot_position', {'x': 0, 'y': 0, 'z': 0}),
        "last_recognized_objects": robot_status['last_recognized_objects'],
        "last_update": robot_status.get('last_update', 0),
        "last_image_timestamp": robot_status.get('last_image_timestamp', 0)
    }
    logger.info("Robot status successfully generated.")
    return json.dumps(status_info, indent=2, ensure_ascii=False)

@mcp.tool()
def set_head_position(yaw: float, pitch: float) -> str:
    """
    Sets the position of the robot's head.

    Args:
        yaw: Head rotation left-right (-1.0 to 1.0)
        pitch: Head tilt up-down (-1.0 to 1.0)
    """
    logger.info(f"Setting head position: yaw={yaw}, pitch={pitch}")
    # Limit the values
    yaw = max(-1.0, min(1.0, yaw))
    pitch = max(-1.0, min(1.0, pitch))

    command = {
        "action": "set_head_position",
        "yaw": yaw,
        "pitch": pitch
    }

    if save_command(command):
        # Update local state
        robot_status["head_position"]["yaw"] = yaw
        robot_status["head_position"]["pitch"] = pitch
        logger.info(f"Local head status updated: yaw={yaw:.2f}, pitch={pitch:.2f}")
        return f"✅ Head position set: yaw={yaw:.2f}, pitch={pitch:.2f}"
    else:
        logger.error("Error sending command to set head position.")
        return "❌ Error sending command"

@mcp.tool()
def set_arm_position(arm: str, shoulder_pitch: float, shoulder_roll: float) -> str:
    """
    Sets the position of the robot's arm.

    Args:
        arm: 'left' or 'right'
        shoulder_pitch: Arm up/down movement (0.0 to 2.0)
        shoulder_roll: Arm adduction/abduction (-1.0 to 1.0)
    """
    logger.info(f"Setting arm position '{arm}': pitch={shoulder_pitch}, roll={shoulder_roll}")
    if arm not in ["left", "right"]:
        logger.warning(f"Invalid value for 'arm': {arm}. Must be 'left' or 'right'.")
        return "❌ Invalid arm value. Use 'left' or 'right'"

    # Limit the values
    shoulder_pitch = max(0.0, min(2.0, shoulder_pitch))
    shoulder_roll = max(-1.0, min(1.0, shoulder_roll))

    command = {
        "action": "set_arm_position",
        "arm": arm,
        "shoulder_pitch": shoulder_pitch,
        "shoulder_roll": shoulder_roll
    }

    if save_command(command):
        # Update local state
        robot_status["arm_positions"][f"{arm}_shoulder_pitch"] = shoulder_pitch
        robot_status["arm_positions"][f"{arm}_shoulder_roll"] = shoulder_roll
        logger.info(f"Local arm status '{arm}' updated: pitch={shoulder_pitch:.2f}, roll={shoulder_roll:.2f}")
        return f"✅ {arm} arm position set: pitch={shoulder_pitch:.2f}, roll={shoulder_roll:.2f}"
    else:
        logger.error(f"Error sending command to set '{arm}' arm position.")
        return "❌ Error sending command"

@mcp.tool()
def reset_robot_pose() -> str:
    """Resets the robot to its initial position."""
    logger.info("Robot pose reset requested.")
    command = {
        "action": "reset_pose"
    }

    if save_command(command):
        # Update local state
        robot_status["head_position"]["yaw"] = 0.0
        robot_status["head_position"]["pitch"] = 0.0
        robot_status["arm_positions"]["left_shoulder_pitch"] = 1.5
        robot_status["arm_positions"]["right_shoulder_pitch"] = 1.5
        robot_status["arm_positions"]["left_shoulder_roll"] = 0.0
        robot_status["arm_positions"]["right_shoulder_roll"] = 0.0
        logger.info("Local status reset to initial position.")
        return "✅ Robot reset to initial position: head straight, arms down"
    else:
        logger.error("Error sending pose reset command.")
        return "❌ Error sending reset command"

@mcp.tool()
def list_motions() -> List[Dict[str, Any]]:
    """
    Returns a list of available motions with their durations.
    """
    logger.info("List of available motions requested.")
    motions_dir = Path(__file__).parent / "motions"
    if not motions_dir.is_dir():
        logger.error(f"Motions directory not found at path: {motions_dir.resolve()}")
        return [{"error": "Motions directory not found"}]

    motion_details = []
    motion_files = list(motions_dir.glob("*.motion"))

    if not motion_files:
        logger.warning(f".motion files not found in directory: {motions_dir.resolve()}")
        return [{"info": ".motion files not found in the motions directory"}]

    logger.info(f"Found {len(motion_files)} animation files.")
    for motion_file in motion_files:
        duration_seconds = 0.0
        try:
            with open(motion_file, 'r', encoding='utf-8') as f:
                lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
                if lines:
                    last_line = lines[-1]
                    time_str = last_line.split(',')[0]
                    time_parts = time_str.split(':')
                    # Format MM:SS:ms (where ms is milliseconds)
                    minutes = int(time_parts[0])
                    seconds = int(time_parts[1])
                    milliseconds = int(time_parts[2])
                    
                    total_seconds = (minutes * 60) + seconds + (milliseconds / 1000.0)
                    duration_seconds = round(total_seconds, 2)
        except (IOError, ValueError, IndexError) as e:
            logger.warning(f"Failed to read duration for {motion_file.name}: {e}")
            duration_seconds = 0.0 # Indicate error or unknown duration

        motion_details.append({
            "name": motion_file.stem,
            "duration_seconds": duration_seconds
        })
    logger.info("Motion list successfully generated.")
    return motion_details

@mcp.tool()
def play_motion(motion_name: str) -> Dict[str, Any]:
    """
    Starts a robot motion and returns its duration.
    """
    logger.info(f"Animation playback requested: {motion_name}")
    motions_dir = Path(__file__).parent / "motions"
    
    # Clear the name from the extension if it exists
    base_motion_name = motion_name.split('.')[0]
    motion_file = motions_dir / f"{base_motion_name}.motion"

    if not motion_file.exists():
        logger.error(f"Animation file '{motion_name}' not found at path: {motion_file.resolve()}")
        return {"status": f"❌ Animation file '{motion_name}' not found.", "duration_seconds": 0}

    duration_seconds = 0.0
    try:
        with open(motion_file, 'r', encoding='utf-8') as f:
            lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
            if lines:
                last_line = lines[-1]
                time_str = last_line.split(',')[0]
                time_parts = time_str.split(':')
                # Format MM:SS:ms (where ms is milliseconds)
                minutes = int(time_parts[0])
                seconds = int(time_parts[1])
                milliseconds = int(time_parts[2])

                total_seconds = (minutes * 60) + seconds + (milliseconds / 1000.0)
                duration_seconds = round(total_seconds, 2)
                logger.info(f"Animation duration for '{motion_name}' determined: {duration_seconds}s")
    except (IOError, ValueError, IndexError) as e:
        logger.warning(f"Failed to read duration for {motion_file.name}: {e}")
        return {"status": f"⚠️ Failed to determine duration for '{motion_name}'.", "duration_seconds": 0}

    command = {
        "action": "play_motion",
        "motion_name": motion_name
    }

    if save_command(command):
        return {
            "status": f"✅ Command to play animation '{motion_name}' sent.",
            "duration_seconds": duration_seconds
        }
    else:
        logger.error(f"Error sending command to play animation '{motion_name}'.")
        return {
            "status": f"❌ Error sending command to play animation '{motion_name}'.",
            "duration_seconds": 0
        }


@mcp.tool()
def set_led_color(color: str, part: str = 'all') -> str:
    """
    Sets the color of the robot's LEDs.

    Args:
        color: Color name ('red', 'green', 'blue', 'white', 'off') or HEX code (e.g., '#FF0000').
        part: Body part to light up (currently only 'all' is supported).
    """
    logger.info(f"Setting LED color: color='{color}', part='{part}'")
    color_map = {
        "red": 0xFF0000,
        "green": 0x00FF00,
        "blue": 0x0000FF,
        "white": 0xFFFFFF,
        "off": 0x000000
    }

    if color.lower() in color_map:
        rgb_color = color_map[color.lower()]
    elif color.startswith('#') and len(color) == 7:
        try:
            rgb_color = int(color[1:], 16)
        except ValueError:
            logger.warning(f"Invalid HEX color code: {color}")
            return f"❌ Invalid HEX color code: {color}"
    else:
        logger.warning(f"Invalid color: {color}. Use a name or HEX code.")
        return f"❌ Invalid color: {color}. Use a name or HEX code."

    command = {
        "action": "set_leds",
        "color": rgb_color
    }

    if save_command(command):
        return f"✅ Command to set color '{color}' sent."
    else:
        logger.error("Error sending command to set color.")
        return f"❌ Error sending command to set color."


@mcp.tool()
def get_robot_capabilities() -> str:
    """Gets a detailed, structured list of the robot's available capabilities in English."""
    logger.info("Detailed robot capabilities requested.")
    capabilities = {
        "Sensing": {
            "get_visual_perception": {
                "description": "Captures a high-resolution image from the robot's forward-facing camera. Returns a confirmation message with the path to the saved image file.",
                "returns": "string (confirmation message)"
            },
            "get_robot_status": {
                "description": "Retrieves a comprehensive status report of the robot's current state.",
                "returns": {
                    "running": "boolean (True if the controller is active)",
                    "webots_connected": "boolean (True if the connection to the simulator is confirmed)",
                    "head_position": {"yaw": "float", "pitch": "float"},
                    "arm_positions": {
                        "left_shoulder_pitch": "float",
                        "right_shoulder_pitch": "float",
                        "left_shoulder_roll": "float",
                        "right_shoulder_roll": "float"
                    },
                    "robot_position": {"x": "float", "y": "float", "z": "float"},
                    "last_update": "float (timestamp)"
                }
            }
        },
        "Actuators": {
            "set_head_position": {
                "description": "Controls the orientation of the robot's head.",
                "parameters": {
                    "yaw": "float (-1.0 to 1.0, left/right rotation)",
                    "pitch": "float (-1.0 to 1.0, up/down tilt)"
                }
            },
            "set_arm_position": {
                "description": "Controls the position of one of the robot's arms.",
                "parameters": {
                    "arm": "string ('left' or 'right')",
                    "shoulder_pitch": "float (0.0 to 2.0, forward/backward movement)",
                    "shoulder_roll": "float (-1.0 to 1.0, side-to-side movement)"
                }
            },
            "set_led_color": {
                "description": "Sets the color of the robot's LEDs. All LEDs are set to the same color.",
                "parameters": {
                    "color": "string (e.g., 'red', 'green', '#FF0000')",
                    "part": "string (currently only 'all' is supported)"
                }
            }
        },
        "Pre-defined Motions": {
            "list_motions": {
                "description": "Lists all available pre-recorded motion files that the robot can perform.",
                "returns": "array of objects, each with 'name' (string) and 'duration_seconds' (float)"
            },
            "play_motion": {
                "description": "Executes a pre-recorded motion file by its name.",
                "parameters": {
                    "motion_name": "string (the name of the motion, e.g., 'HandWave')"
                },
                "returns": "object with 'status' (string) and 'duration_seconds' (float)"
            }
        },
        "System & State": {
            "reset_robot_pose": {
                "description": "Resets the robot to a default standing position with arms down and head forward.",
                "returns": "string (confirmation message)"
            },
            "check_webots_connection": {
                "description": "Verifies the communication link with the Webots simulator controller.",
                "returns": "object with connection details"
            }
        }
    }
    logger.info("Detailed robot capabilities list successfully generated.")
    return json.dumps(capabilities, indent=2, ensure_ascii=False)

@mcp.tool()
def check_webots_connection() -> str:
    """Checks the connection with the Webots controller."""
    logger.info("Webots connection check requested.")
    load_status()

    current_time = time.time()
    last_update = robot_status.get('last_update', 0)
    #is_connected = (current_time - last_update) < 10.0

    connection_info = {
        "connected": True,
        "last_update": last_update,
        "time_since_update": current_time - last_update,
        "commands_file_exists": COMMANDS_FILE.exists(),
        "status_file_exists": STATUS_FILE.exists(),
        "webots_reported_status": robot_status.get('webots_connected', False)
    }
    logger.info(f"Connection status: {connection_info}")
    return json.dumps(connection_info, indent=2, ensure_ascii=False)

# Initialization on load
logger.info("Initializing MCP server...")
load_status()

if __name__ == "__main__":
    logger.info("Starting MCP server.")
    # Start the server
    mcp.run()
