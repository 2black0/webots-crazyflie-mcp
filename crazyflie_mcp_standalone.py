#!/usr/bin/env python3
"""
Crazyflie MCP Server - Standalone Version

A standalone server providing 11 essential tools for controlling 
Crazyflie drone in Webots simulation environment.

This version can run independently without complex MCP framework
for testing and development purposes.
"""

import asyncio
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Create necessary directories
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/crazyflie_mcp.log'),
    ]
)
logger = logging.getLogger(__name__)

# Configuration
ROOT_DATA_DIR = Path(__file__).parent / "data"
LOGS_DIR = Path(__file__).parent / "logs"

# Create necessary directories
ROOT_DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

def get_robot_data_dir(drone_name: str) -> Path:
    """Returns the data directory for a given drone."""
    return ROOT_DATA_DIR / drone_name

def get_commands_file(drone_name: str) -> Path:
    """Returns the commands file path for a given drone."""
    return get_robot_data_dir(drone_name) / "commands.json"

def get_status_file(drone_name: str) -> Path:
    """Returns the status file path for a given drone."""
    return get_robot_data_dir(drone_name) / "status.json"

def get_image_file(drone_name: str) -> Path:
    """Returns the camera image file path for a given drone."""
    return get_robot_data_dir(drone_name) / "camera_image.jpg"

# Global state
drone_status = {
    "running": False,
    "webots_connected": False,
    "flight_status": "idle",  # idle, takeoff, hovering, landing, moving, emergency
    "position": {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    "collision_sensors": {},
    "current_action": "none",
    "action_progress": 0.0,
    "last_update": 0,
    "last_image_timestamp": 0,
    "system_health": "OK"
}

def load_status(drone_name: str) -> bool:
    """Load drone status from file."""
    global drone_status
    status_file = get_status_file(drone_name)
    try:
        if status_file.exists():
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                drone_status.update(data)
                logger.debug(f"Status for {drone_name} loaded successfully.")
                return True
    except Exception as e:
        logger.error(f"Error loading status for {drone_name}: {e}")
    return False

def save_command(drone_name: str, command: dict) -> bool:
    """Save command to file for the controller."""
    commands_file = get_commands_file(drone_name)
    try:
        command['timestamp'] = time.time()
        # Ensure directory exists
        commands_file.parent.mkdir(parents=True, exist_ok=True)
        with open(commands_file, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2, ensure_ascii=False)
        logger.info(f"Command '{command.get('action')}' for {drone_name} saved to {commands_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving command for {drone_name}: {e}")
        return False

def wait_for_status_update(drone_name: str, timeout: float = 5.0) -> bool:
    """Wait for status update from controller."""
    start_time = time.time()
    initial_update_time = drone_status.get('last_update', 0)
    
    while time.time() - start_time < timeout:
        load_status(drone_name)
        if drone_status.get('last_update', 0) > initial_update_time:
            return True
        time.sleep(0.1)
    return False

def wait_for_image_update(drone_name: str, timeout: float = 10.0) -> bool:
    """Wait for image update from controller."""
    start_time = time.time()
    initial_image_time = drone_status.get('last_image_timestamp', 0)
    
    while time.time() - start_time < timeout:
        load_status(drone_name)
        if drone_status.get('last_image_timestamp', 0) > initial_image_time:
            return True
        time.sleep(0.1)
    return False

# ========================================
# FLIGHT CONTROL TOOLS (5 tools)
# ========================================

def takeoff(drone_name: str, altitude: float = 1.0) -> str:
    """Execute basic takeoff sequence to specified altitude."""
    logger.info(f"Takeoff command for {drone_name} to altitude {altitude}m")
    
    # Validate altitude
    altitude = max(0.1, min(10.0, altitude))
    
    command = {
        "action": "takeoff",
        "altitude": altitude
    }
    
    if save_command(drone_name, command):
        return f"✅ Takeoff command sent for {drone_name} to altitude {altitude:.1f}m"
    else:
        return f"❌ Error sending takeoff command for {drone_name}"

def land(drone_name: str) -> str:
    """Execute controlled landing sequence."""
    logger.info(f"Landing command for {drone_name}")
    
    command = {
        "action": "land"
    }
    
    if save_command(drone_name, command):
        return f"✅ Landing command sent for {drone_name}"
    else:
        return f"❌ Error sending landing command for {drone_name}"

def hover(drone_name: str, duration: float = 5.0) -> str:
    """Maintain stable hovering position for specified duration."""
    logger.info(f"Hover command for {drone_name} for {duration}s")
    
    command = {
        "action": "hover",
        "duration": duration
    }
    
    if save_command(drone_name, command):
        if duration > 0:
            return f"✅ Hover command sent for {drone_name} for {duration:.1f} seconds"
        else:
            return f"✅ Indefinite hover command sent for {drone_name}"
    else:
        return f"❌ Error sending hover command for {drone_name}"

def move_relative(drone_name: str, forward: float, sideways: float, up: float, yaw: float, duration: float = 2.0) -> str:
    """Execute relative movement in multiple axes."""
    logger.info(f"Relative movement for {drone_name}: forward={forward}, sideways={sideways}, up={up}, yaw={yaw}, duration={duration}")
    
    # Limit movement ranges for safety
    forward = max(-5.0, min(5.0, forward))
    sideways = max(-5.0, min(5.0, sideways))
    up = max(-3.0, min(3.0, up))
    yaw = max(-3.14, min(3.14, yaw))
    duration = max(0.5, min(30.0, duration))
    
    command = {
        "action": "move_relative",
        "forward": forward,
        "sideways": sideways,
        "up": up,
        "yaw": yaw,
        "duration": duration
    }
    
    if save_command(drone_name, command):
        return f"✅ Relative movement command sent for {drone_name}: forward={forward:.1f}m, sideways={sideways:.1f}m, up={up:.1f}m, yaw={yaw:.2f}rad over {duration:.1f}s"
    else:
        return f"❌ Error sending movement command for {drone_name}"

def emergency_stop(drone_name: str) -> str:
    """Execute immediate emergency stop with motor cutoff."""
    logger.warning(f"EMERGENCY STOP command for {drone_name}")
    
    command = {
        "action": "emergency_stop"
    }
    
    if save_command(drone_name, command):
        return f"🚨 EMERGENCY STOP executed for {drone_name}"
    else:
        return f"❌ Error sending emergency stop command for {drone_name}"

# ========================================
# SENSING & STATUS TOOLS (4 tools)
# ========================================

def get_drone_position(drone_name: str) -> str:
    """Get current drone position, orientation, and velocity."""
    logger.info(f"Position request for {drone_name}")
    load_status(drone_name)
    
    position_data = {
        "position": drone_status.get('position', {"x": 0.0, "y": 0.0, "z": 0.0}),
        "orientation": {
            "roll": drone_status.get('position', {}).get('roll', 0.0),
            "pitch": drone_status.get('position', {}).get('pitch', 0.0),
            "yaw": drone_status.get('position', {}).get('yaw', 0.0)
        },
        "timestamp": drone_status.get('last_update', 0)
    }
    
    return json.dumps(position_data, indent=2)

def get_drone_status(drone_name: str) -> str:
    """Get comprehensive drone status including flight state and system health."""
    logger.info(f"Status request for {drone_name}")
    load_status(drone_name)
    
    # Check if controller is active (updated within last 10 seconds)
    current_time = time.time()
    last_update = drone_status.get('last_update', 0)
    is_running = (current_time - last_update) < 10.0
    
    status_data = {
        "running": is_running,
        "webots_connected": drone_status.get('webots_connected', False),
        "flight_status": drone_status.get('flight_status', 'idle'),
        "position": drone_status.get('position', {"x": 0.0, "y": 0.0, "z": 0.0}),
        "current_action": drone_status.get('current_action', 'none'),
        "action_progress": drone_status.get('action_progress', 0.0),
        "system_health": drone_status.get('system_health', 'OK'),
        "last_update": last_update,
        "time_since_update": current_time - last_update
    }
    
    return json.dumps(status_data, indent=2)

def get_visual_perception(drone_name: str) -> str:
    """Capture image from drone's camera for analysis."""
    logger.info(f"Visual perception request for {drone_name}")
    
    command = {
        "action": "get_camera_image"
    }
    
    if not save_command(drone_name, command):
        return f"❌ Error sending camera command for {drone_name}"
    
    if not wait_for_image_update(drone_name):
        return f"⚠️ Camera command sent for {drone_name}, but image not received within timeout"
    
    image_path = get_image_file(drone_name)
    if not image_path.exists():
        return f"❌ Image file for {drone_name} not found after update"
    
    return f"✅ Image captured for {drone_name}: {image_path.resolve()}"

def get_collision_sensors(drone_name: str) -> str:
    """Get readings from 8-directional collision sensors."""
    logger.info(f"Collision sensor request for {drone_name}")
    load_status(drone_name)
    
    collision_data = drone_status.get('collision_sensors', {})
    
    # If no collision data, return empty structure
    if not collision_data:
        collision_data = {
            "range_north": 999.0,
            "range_northeast": 999.0,
            "range_east": 999.0,
            "range_southeast": 999.0,
            "range_south": 999.0,
            "range_southwest": 999.0,
            "range_west": 999.0,
            "range_northwest": 999.0,
            "risk_level": "UNKNOWN"
        }
    
    return json.dumps(collision_data, indent=2)

# ========================================
# SYSTEM CONTROL TOOLS (2 tools)
# ========================================

def set_altitude(drone_name: str, altitude: float) -> str:
    """Set and maintain specific altitude."""
    logger.info(f"Set altitude command for {drone_name} to {altitude}m")
    
    # Validate altitude
    altitude = max(0.1, min(10.0, altitude))
    
    command = {
        "action": "set_altitude",
        "altitude": altitude
    }
    
    if save_command(drone_name, command):
        return f"✅ Altitude command sent for {drone_name} to {altitude:.1f}m"
    else:
        return f"❌ Error sending altitude command for {drone_name}"

def check_drone_connection(drone_name: str) -> str:
    """Perform health check and verify drone connection status."""
    logger.info(f"Connection check for {drone_name}")
    load_status(drone_name)
    
    current_time = time.time()
    last_update = drone_status.get('last_update', 0)
    time_since_update = current_time - last_update
    is_connected = time_since_update < 10.0
    
    connection_info = {
        "connected": is_connected,
        "webots_connected": drone_status.get('webots_connected', False),
        "last_update": last_update,
        "time_since_update": time_since_update,
        "system_health": drone_status.get('system_health', 'UNKNOWN'),
        "flight_status": drone_status.get('flight_status', 'unknown'),
        "commands_file_exists": get_commands_file(drone_name).exists(),
        "status_file_exists": get_status_file(drone_name).exists(),
        "data_directory": str(get_robot_data_dir(drone_name))
    }
    
    return json.dumps(connection_info, indent=2)

# ========================================
# UTILITY TOOLS
# ========================================

def get_crazyflie_capabilities() -> str:
    """Get detailed list of all available Crazyflie MCP tools and capabilities."""
    logger.info("Capabilities request")
    
    capabilities = {
        "server_info": {
            "name": "Crazyflie Webots MCP Server",
            "version": "1.0.0",
            "description": "Standalone server for Crazyflie drone control in Webots",
            "architecture": "File-based communication with 11 essential tools"
        },
        "flight_control": {
            "takeoff": {
                "description": "Execute basic takeoff sequence",
                "parameters": ["drone_name", "altitude (optional, default: 1.0)"]
            },
            "land": {
                "description": "Execute controlled landing sequence",
                "parameters": ["drone_name"]
            },
            "hover": {
                "description": "Maintain stable hovering position",
                "parameters": ["drone_name", "duration (optional, default: 5.0)"]
            },
            "move_relative": {
                "description": "Relative movement in multiple axes",
                "parameters": ["drone_name", "forward", "sideways", "up", "yaw", "duration (optional)"]
            },
            "emergency_stop": {
                "description": "Immediate emergency stop with motor cutoff",
                "parameters": ["drone_name"]
            }
        },
        "sensing_status": {
            "get_drone_position": {
                "description": "Get current position and orientation",
                "parameters": ["drone_name"]
            },
            "get_drone_status": {
                "description": "Get comprehensive flight status",
                "parameters": ["drone_name"]
            },
            "get_visual_perception": {
                "description": "Capture camera image for analysis",
                "parameters": ["drone_name"]
            },
            "get_collision_sensors": {
                "description": "Get 8-directional collision sensor readings",
                "parameters": ["drone_name"]
            }
        },
        "system_control": {
            "set_altitude": {
                "description": "Set and maintain specific altitude",
                "parameters": ["drone_name", "altitude"]
            },
            "check_drone_connection": {
                "description": "Health check and connection verification",
                "parameters": ["drone_name"]
            }
        }
    }
    
    return json.dumps(capabilities, indent=2)

def list_active_drones() -> List[Dict[str, Any]]:
    """List all active drones with their current status."""
    logger.info("Active drones list requested")
    
    if not ROOT_DATA_DIR.is_dir():
        return []
    
    active_drones = []
    current_time = time.time()
    
    for drone_dir in ROOT_DATA_DIR.iterdir():
        if drone_dir.is_dir():
            drone_name = drone_dir.name
            
            # Load status for each drone
            original_status = drone_status.copy()
            load_status(drone_name)
            
            last_update = drone_status.get('last_update', 0)
            is_active = (current_time - last_update) < 30.0  # Active within last 30 seconds
            
            if is_active:
                active_drones.append({
                    "name": drone_name,
                    "position": drone_status.get('position', {"x": 0.0, "y": 0.0, "z": 0.0}),
                    "flight_status": drone_status.get('flight_status', 'unknown'),
                    "last_update": last_update,
                    "time_since_update": current_time - last_update
                })
            
            # Restore original status
            drone_status.update(original_status)
    
    return active_drones

# ========================================
# COMMAND LINE INTERFACE
# ========================================

def execute_command(command_name: str, *args) -> str:
    """Execute a command by name with arguments."""
    commands = {
        'takeoff': takeoff,
        'land': land,
        'hover': hover,
        'move_relative': move_relative,
        'emergency_stop': emergency_stop,
        'get_drone_position': get_drone_position,
        'get_drone_status': get_drone_status,
        'get_visual_perception': get_visual_perception,
        'get_collision_sensors': get_collision_sensors,
        'set_altitude': set_altitude,
        'check_drone_connection': check_drone_connection,
        'get_crazyflie_capabilities': get_crazyflie_capabilities,
        'list_active_drones': list_active_drones
    }
    
    if command_name not in commands:
        return f"❌ Unknown command: {command_name}"
    
    try:
        func = commands[command_name]
        result = func(*args)
        return str(result)
    except Exception as e:
        return f"❌ Error executing {command_name}: {e}"

def print_help():
    """Print help information."""
    print("""
🚁 Crazyflie MCP Server - Standalone Version

Available Commands:
  Flight Control:
    takeoff <drone_name> [altitude]              - Execute takeoff
    land <drone_name>                            - Execute landing
    hover <drone_name> [duration]                - Hover in place
    move_relative <drone_name> <fx> <fy> <fz> <yaw> [duration] - Relative movement
    emergency_stop <drone_name>                  - Emergency stop
    
  Sensing & Status:
    get_drone_position <drone_name>              - Get position/orientation
    get_drone_status <drone_name>                - Get comprehensive status
    get_visual_perception <drone_name>           - Capture camera image
    get_collision_sensors <drone_name>           - Get sensor readings
    
  System Control:
    set_altitude <drone_name> <altitude>         - Set target altitude
    check_drone_connection <drone_name>          - Check connection status
    
  Utility:
    get_crazyflie_capabilities                   - List all capabilities
    list_active_drones                           - List active drones
    
  Other:
    help                                         - Show this help
    exit                                         - Exit server

Examples:
  takeoff Crazyflie 1.5
  move_relative Crazyflie 1.0 0.0 0.5 0.0 3.0
  get_drone_status Crazyflie
""")

def initialize_server():
    """Initialize the standalone MCP server."""
    logger.info("Initializing Crazyflie MCP Server (Standalone Mode)...")
    
    # Create directories
    ROOT_DATA_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    
    logger.info("✅ Crazyflie MCP Server initialized successfully")
    logger.info("📡 Server ready to accept drone control commands")
    logger.info("🛠️ 11 essential tools available for drone operations")

def file_monitoring_mode():
    """Monitor command files for non-interactive usage."""
    logger.info("Starting file monitoring mode...")
    
    commands_file = "data/Crazyflie/commands.json"
    status_file = "data/Crazyflie/status.json"
    
    # Initialize status file with basic info
    status_data = {
        "system": "ready", 
        "mode": "file_monitoring",
        "timestamp": time.time()
    }
    
    try:
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to initialize status file: {e}")
    
    last_command_time = 0
    
    while True:
        try:
            # Check if commands file exists and has been modified
            if os.path.exists(commands_file):
                file_mtime = os.path.getmtime(commands_file)
                
                if file_mtime > last_command_time:
                    last_command_time = file_mtime
                    
                    # Read command
                    try:
                        with open(commands_file, 'r') as f:
                            command_data = json.load(f)
                        
                        logger.info(f"Received command: {command_data}")
                        
                        # Execute command
                        action = command_data.get('action')
                        if action == 'takeoff':
                            result = takeoff('Crazyflie', command_data.get('altitude', 1.0))
                        elif action == 'land':
                            result = land('Crazyflie')
                        elif action == 'hover':
                            result = hover('Crazyflie', command_data.get('duration', 5.0))
                        elif action == 'move_relative':
                            result = move_relative('Crazyflie', 
                                                 command_data.get('x', 0),    # forward (x)
                                                 command_data.get('y', 0),    # sideways (y)
                                                 command_data.get('z', 0),    # up (z)
                                                 command_data.get('yaw', 0),  # yaw rotation
                                                 command_data.get('duration', 2.0))
                        elif action == 'set_altitude':
                            result = set_altitude('Crazyflie', command_data.get('altitude', 1.0))
                        elif action == 'emergency_stop':
                            result = emergency_stop('Crazyflie')
                        elif action == 'get_sensor_data':
                            # Combine multiple sensor functions
                            position = get_drone_position('Crazyflie')
                            visual = get_visual_perception('Crazyflie')
                            collision = get_collision_sensors('Crazyflie')
                            result = f"Position: {position}, Visual: {visual}, Collision: {collision}"
                        elif action == 'status':
                            result = get_drone_status('Crazyflie')
                        elif action == 'reset_position':
                            # Use emergency stop as reset (closest available function)
                            result = emergency_stop('Crazyflie')
                        elif action == 'rotate':
                            # Convert degrees to radians for rotation
                            angle_rad = command_data.get('angle', 0) * 3.14159 / 180.0
                            result = move_relative('Crazyflie', 0, 0, 0, angle_rad, 2.0)
                        elif action == 'move_to_position':
                            # Use relative movement to approximate absolute positioning
                            # This would need current position to calculate relative movement
                            result = "move_to_position not directly supported - use move_relative"
                        else:
                            result = f"❌ Unknown action: {action}"
                        
                        logger.info(f"Command result: {result}")
                        
                        # Update status with result
                        status_update = {
                            "last_command": action,
                            "last_result": result,
                            "timestamp": time.time(),
                            "system": "ready"
                        }
                        
                        try:
                            with open(status_file, 'w') as f:
                                json.dump(status_update, f, indent=2)
                        except Exception as e:
                            logger.error(f"Failed to update status file: {e}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in command file: {e}")
                        status_update = {
                            "error": f"Invalid JSON: {e}",
                            "timestamp": time.time(),
                            "system": "error"
                        }
                        try:
                            with open(status_file, 'w') as f:
                                json.dump(status_update, f, indent=2)
                        except Exception:
                            pass
                            
                    except Exception as e:
                        logger.error(f"Error processing command: {e}")
                        status_update = {
                            "error": str(e),
                            "timestamp": time.time(),
                            "system": "error"
                        }
                        try:
                            with open(status_file, 'w') as f:
                                json.dump(status_update, f, indent=2)
                        except Exception:
                            pass
            
            # Sleep to avoid busy waiting
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            logger.info("File monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in file monitoring: {e}")
            time.sleep(1)

def main():
    """Main entry point with mode detection."""
    initialize_server()
    
    # Check if running in interactive mode (has stdin) or file mode
    if sys.stdin.isatty():
        # Interactive mode
        print("🚁 Crazyflie MCP Server - Standalone Version")
        print("=" * 50)
        print("Type 'help' for commands or 'exit' to quit")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 Goodbye!")
                    break
                    
                if user_input.lower() == 'help':
                    print_help()
                    continue
                
                # Parse command and arguments
                parts = user_input.split()
                command_name = parts[0]
                args = parts[1:]
                
                # Execute command
                result = execute_command(command_name, *args)
                print(f"\n{result}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    else:
        # Non-interactive mode - use file monitoring
        file_monitoring_mode()

if __name__ == "__main__":
    main()
