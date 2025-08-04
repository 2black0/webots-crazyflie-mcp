"""
MCP Communication Handler for Crazyflie Controller

Handles all file-based communication between the MCP server and Webots controller.
Provides robust error handling and JSON validation.
"""

import json
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MCPCommunication:
    """Handles file-based communication with MCP server"""
    
    def __init__(self, robot_name: str):
        self.robot_name = robot_name
        self.data_dir = Path(__file__).parent.parent.parent / "data" / robot_name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.commands_file = self.data_dir / "commands.json"
        self.status_file = self.data_dir / "status.json"
        self.image_file = self.data_dir / "camera_image.jpg"
        
        # Command tracking
        self.last_command_timestamp = 0
        self.last_status_update = 0
        
        # Initialize communication files
        self.initialize_files()
        
        logger.info(f"MCPCommunication initialized for {robot_name}")
        logger.info(f"Data directory: {self.data_dir}")
        
    def initialize_files(self):
        """Initialize communication files with default values"""
        try:
            # Initialize status file with default values
            initial_status = {
                "timestamp": time.time(),
                "webots_connected": True,
                "flight_status": "idle",
                "position": {
                    "x": 0.0, "y": 0.0, "z": 0.0,
                    "roll": 0.0, "pitch": 0.0, "yaw": 0.0
                },
                "collision_sensors": {
                    "range_north": 999.0,
                    "range_northeast": 999.0,
                    "range_east": 999.0,
                    "range_southeast": 999.0,
                    "range_south": 999.0,
                    "range_southwest": 999.0,
                    "range_west": 999.0,
                    "range_northwest": 999.0,
                    "risk_level": "SAFE"
                },
                "current_action": "initializing",
                "action_progress": 0.0,
                "last_update": time.time(),
                "last_image_timestamp": 0,
                "system_health": "OK"
            }
            
            self.save_status(initial_status)
            
            # Clear any existing commands
            if self.commands_file.exists():
                self.commands_file.unlink()
                logger.info("Cleared existing commands file")
                
            logger.info("Communication files initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing files: {e}")
    
    def get_new_command(self):
        """Check for new commands from MCP server"""
        try:
            if not self.commands_file.exists():
                return None
                
            print(f"[MCP_COMM] Reading command file: {self.commands_file}")
            
            # Read and validate command file
            with open(self.commands_file, 'r', encoding='utf-8') as f:
                command = json.load(f)
            
            print(f"[MCP_COMM] Command read: {command}")
            
            # Validate command structure
            if not isinstance(command, dict):
                print("[MCP_COMM] WARNING: Invalid command format: not a dictionary")
                self.commands_file.unlink()
                return None
            
            if 'action' not in command:
                print("[MCP_COMM] WARNING: Invalid command: missing 'action' field")
                self.commands_file.unlink()
                return None
            
            # Check if this is a new command
            command_timestamp = command.get('timestamp', 0)
            if command_timestamp > self.last_command_timestamp:
                self.last_command_timestamp = command_timestamp
                
                # Remove the command file after reading to prevent re-execution
                self.commands_file.unlink()
                
                print(f"[MCP_COMM] ✅ New command received: {command.get('action')}")
                return command
            else:
                # Old command, remove it
                self.commands_file.unlink()
                logger.debug("Removed old command file")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in command file: {e}")
            # Remove corrupted file
            if self.commands_file.exists():
                self.commands_file.unlink()
        except Exception as e:
            logger.error(f"Error reading command: {e}")
            
        return None
    
    def save_status(self, status_data):
        """Save current status to file with validation"""
        try:
            # Validate status data
            if not isinstance(status_data, dict):
                logger.error("Status data must be a dictionary")
                return False
            
            # Ensure required fields are present
            required_fields = ['timestamp', 'webots_connected', 'flight_status', 'position']
            for field in required_fields:
                if field not in status_data:
                    logger.warning(f"Missing required field in status: {field}")
            
            # Add timestamp
            status_data['last_update'] = time.time()
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.status_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.rename(self.status_file)
            
            self.last_status_update = time.time()
            return True
            
        except Exception as e:
            logger.error(f"Error saving status: {e}")
            # Clean up temporary file if it exists
            temp_file = self.status_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
            return False
    
    def save_image(self, image_data):
        """Save camera image to file"""
        try:
            if image_data is None:
                logger.warning("No image data provided")
                return False
            
            # Write image to temporary file first
            temp_file = self.image_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                f.write(image_data)
            
            # Atomic rename
            temp_file.rename(self.image_file)
            
            logger.info(f"Image saved successfully: {self.image_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            # Clean up temporary file if it exists
            temp_file = self.image_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
            return False
    
    def validate_command(self, command):
        """Validate command structure and parameters"""
        if not isinstance(command, dict):
            return False, "Command must be a dictionary"
        
        action = command.get('action')
        if not action:
            return False, "Missing 'action' field"
        
        # Validate specific command parameters
        if action == "takeoff":
            altitude = command.get('altitude', 1.0)
            if not isinstance(altitude, (int, float)) or altitude <= 0 or altitude > 10:
                return False, "Invalid altitude: must be between 0 and 10 meters"
                
        elif action == "move_relative":
            required_params = ['forward', 'sideways', 'up', 'yaw']
            for param in required_params:
                if param not in command:
                    return False, f"Missing required parameter: {param}"
                value = command[param]
                if not isinstance(value, (int, float)):
                    return False, f"Parameter {param} must be a number"
                    
        elif action == "set_altitude":
            altitude = command.get('altitude')
            if altitude is None:
                return False, "Missing altitude parameter"
            if not isinstance(altitude, (int, float)) or altitude < 0 or altitude > 10:
                return False, "Invalid altitude: must be between 0 and 10 meters"
        
        return True, "Valid command"
    
    def get_communication_stats(self):
        """Get statistics about communication health"""
        current_time = time.time()
        
        stats = {
            "commands_file_exists": self.commands_file.exists(),
            "status_file_exists": self.status_file.exists(),
            "image_file_exists": self.image_file.exists(),
            "last_command_timestamp": self.last_command_timestamp,
            "last_status_update": self.last_status_update,
            "time_since_last_status": current_time - self.last_status_update if self.last_status_update > 0 else 0,
            "data_directory": str(self.data_dir),
            "communication_health": "OK" if current_time - self.last_status_update < 5.0 else "WARNING"
        }
        
        return stats
    
    def cleanup(self):
        """Clean up communication files on shutdown"""
        try:
            files_to_clean = [self.commands_file, self.status_file]
            
            for file_path in files_to_clean:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up: {file_path}")
            
            logger.info("Communication cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Command validation helpers
def validate_position_data(position):
    """Validate position data structure"""
    if not isinstance(position, dict):
        return False
    
    required_fields = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
    for field in required_fields:
        if field not in position:
            return False
        if not isinstance(position[field], (int, float)):
            return False
    
    return True

def validate_collision_data(collision_data):
    """Validate collision sensor data structure"""
    if not isinstance(collision_data, dict):
        return False
    
    expected_sensors = [
        'range_north', 'range_northeast', 'range_east', 'range_southeast',
        'range_south', 'range_southwest', 'range_west', 'range_northwest'
    ]
    
    for sensor in expected_sensors:
        if sensor in collision_data:
            if not isinstance(collision_data[sensor], (int, float)):
                return False
    
    return True

def sanitize_status_data(status_data):
    """Sanitize status data to ensure valid JSON serialization"""
    if not isinstance(status_data, dict):
        return {}
    
    sanitized = {}
    
    # Copy safe fields
    safe_fields = [
        'timestamp', 'webots_connected', 'flight_status', 'current_action',
        'action_progress', 'last_update', 'last_image_timestamp', 'system_health'
    ]
    
    for field in safe_fields:
        if field in status_data:
            value = status_data[field]
            # Ensure numbers are finite
            if isinstance(value, float) and not (value == value):  # Check for NaN
                value = 0.0
            sanitized[field] = value
    
    # Sanitize position data
    if 'position' in status_data and validate_position_data(status_data['position']):
        sanitized['position'] = status_data['position']
    else:
        sanitized['position'] = {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    
    # Sanitize collision data
    if 'collision_sensors' in status_data and validate_collision_data(status_data['collision_sensors']):
        sanitized['collision_sensors'] = status_data['collision_sensors']
    else:
        sanitized['collision_sensors'] = {
            "range_north": 999.0, "range_northeast": 999.0, "range_east": 999.0, "range_southeast": 999.0,
            "range_south": 999.0, "range_southwest": 999.0, "range_west": 999.0, "range_northwest": 999.0,
            "risk_level": "UNKNOWN"
        }
    
    return sanitized
