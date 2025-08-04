"""
Simple MCP Controller for Crazyflie in Webots

This controller implements the communication layer between the MCP server
and the Webots simulation environment. It handles command processing,
flight operations, and status reporting.

Based on the existing enhanced Crazyflie controller and documentation.
"""

from controller import Robot, Motor, DistanceSensor, InertialUnit, GPS, Gyro, Camera
import json
import time
import math
import os
from pathlib import Path
import logging

# Import existing flight components
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "old" / "project-crazyflie" / "controllers"))

try:
    from core.flight_controller import CoreFlightController
    from actions.basic_actions import BasicDroneActions
    from core.collision_avoidance import CollisionAvoidanceSystem
except ImportError:
    # If imports fail, we'll use simplified versions
    CoreFlightController = None
    BasicDroneActions = None
    CollisionAvoidanceSystem = None

class MCPCommunication:
    """Handles file-based communication with MCP server"""
    
    def __init__(self, robot_name: str):
        self.robot_name = robot_name
        self.data_dir = Path(__file__).parent.parent.parent / "data" / robot_name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.commands_file = self.data_dir / "commands.json"
        self.status_file = self.data_dir / "status.json"
        self.image_file = self.data_dir / "camera_image.jpg"
        
        # Initialize empty files
        self.last_command_timestamp = 0
        self.initialize_files()
        
    def initialize_files(self):
        """Initialize communication files"""
        # Initialize status file
        initial_status = {
            "timestamp": time.time(),
            "webots_connected": True,
            "flight_status": "idle",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
            "collision_sensors": {},
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
    
    def get_new_command(self):
        """Check for new commands from MCP server"""
        try:
            if not self.commands_file.exists():
                return None
                
            with open(self.commands_file, 'r') as f:
                command = json.load(f)
                
            # Check if this is a new command
            command_timestamp = command.get('timestamp', 0)
            if command_timestamp > self.last_command_timestamp:
                self.last_command_timestamp = command_timestamp
                # Remove the command file after reading
                self.commands_file.unlink()
                return command
                
        except Exception as e:
            logging.error(f"Error reading command: {e}")
            
        return None
    
    def save_status(self, status_data):
        """Save current status to file"""
        try:
            status_data['last_update'] = time.time()
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving status: {e}")
    
    def save_image(self, image_data):
        """Save camera image to file"""
        try:
            with open(self.image_file, 'wb') as f:
                f.write(image_data)
            return True
        except Exception as e:
            logging.error(f"Error saving image: {e}")
            return False

class SimplifiedFlightController:
    """Simplified flight controller for basic operations"""
    
    def __init__(self, robot):
        self.robot = robot
        self.timestep = int(robot.getBasicTimeStep())
        
        # Initialize motors
        self.motors = self._init_motors()
        
        # Initialize sensors
        self.imu = robot.getDevice("inertial_unit")
        self.gps = robot.getDevice("gps")
        self.gyro = robot.getDevice("gyro")
        self.camera = robot.getDevice("camera")
        
        # Initialize distance sensors
        self.distance_sensors = self._init_distance_sensors()
        
        # Enable sensors
        self._enable_sensors()
        
        # Flight parameters
        self.target_altitude = 1.0
        self.is_flying = False
        self.hover_altitude = 1.0
        self.max_motor_velocity = 500  # Safe limit below Webots max of 600
        
    def _clamp_motor_velocity(self, velocity):
        """Ensure motor velocity is within safe limits"""
        return max(-self.max_motor_velocity, min(self.max_motor_velocity, velocity))
    
    def _set_motor_velocity_safe(self, motor, velocity):
        """Set motor velocity with safety clamping"""
        safe_velocity = self._clamp_motor_velocity(velocity)
        motor.setVelocity(safe_velocity)
        return safe_velocity
        
    def _init_motors(self):
        """Initialize quadcopter motors"""
        motor_names = ["m1_motor", "m2_motor", "m3_motor", "m4_motor"]
        motors = {}
        for name in motor_names:
            motor = self.robot.getDevice(name)
            motor.setPosition(float('inf'))
            motor.setVelocity(0)
            motors[name] = motor
        return motors
    
    def _init_distance_sensors(self):
        """Initialize 8-directional distance sensors"""
        sensor_names = [
            "range_north", "range_northeast", "range_east", "range_southeast",
            "range_south", "range_southwest", "range_west", "range_northwest"
        ]
        sensors = {}
        for name in sensor_names:
            try:
                sensor = self.robot.getDevice(name)
                sensors[name] = sensor
            except:
                # Sensor not available, create dummy entry
                sensors[name] = None
        return sensors
    
    def _enable_sensors(self):
        """Enable all sensors"""
        self.imu.enable(self.timestep)
        self.gps.enable(self.timestep)
        self.gyro.enable(self.timestep)
        self.camera.enable(self.timestep)
        
        for sensor in self.distance_sensors.values():
            if sensor:
                sensor.enable(self.timestep)
    
    def get_position(self):
        """Get current position and orientation"""
        try:
            gps_values = self.gps.getValues()
            roll, pitch, yaw = self.imu.getRollPitchYaw()
            
            return {
                "x": gps_values[0],
                "y": gps_values[1], 
                "z": gps_values[2],
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw
            }
        except:
            return {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    
    def get_collision_sensors(self):
        """Get collision sensor readings"""
        readings = {}
        for name, sensor in self.distance_sensors.items():
            if sensor:
                try:
                    readings[name] = sensor.getValue()
                except:
                    readings[name] = 999.0
            else:
                readings[name] = 999.0
        
        # Determine risk level
        min_distance = min(readings.values())
        if min_distance < 0.3:
            risk_level = "CRITICAL"
        elif min_distance < 0.8:
            risk_level = "WARNING"
        elif min_distance < 1.5:
            risk_level = "CAUTION"
        else:
            risk_level = "SAFE"
        
        readings["risk_level"] = risk_level
        return readings
    
    def capture_image(self):
        """Capture image from camera"""
        try:
            image = self.camera.getImage()
            if image:
                return image
        except:
            pass
        return None
    
    def takeoff(self, altitude=1.0):
        """Execute takeoff sequence"""
        print(f"[FLIGHT_CONTROLLER] 🚁 Takeoff to altitude: {altitude}m")
        self.target_altitude = altitude
        self.hover_altitude = altitude
        self.is_flying = True
        
        # Safe takeoff - limited motor velocity
        target_velocity = 200  # Conservative velocity for takeoff
        print(f"[FLIGHT_CONTROLLER] Setting motor velocity to: {target_velocity}")
        
        for motor_name, motor in self.motors.items():
            actual_velocity = self._set_motor_velocity_safe(motor, target_velocity)
            print(f"[FLIGHT_CONTROLLER] Motor {motor_name} set to {actual_velocity}")
        
        return f"Takeoff initiated to {altitude}m altitude"
    
    def land(self):
        """Execute landing sequence"""
        print("[FLIGHT_CONTROLLER] 🛬 Landing sequence initiated")
        self.target_altitude = 0.0
        self.is_flying = False
        
        # Stop all motors safely
        for motor_name, motor in self.motors.items():
            motor.setVelocity(0)
            print(f"[FLIGHT_CONTROLLER] Motor {motor_name} stopped")
        
        return "Landing sequence initiated"
    
    def hover(self, duration=0):
        """Maintain hover at current altitude"""
        current_pos = self.get_position()
        self.hover_altitude = current_pos["z"]
        
        # Basic hover control
        base_speed = 300  # Adjust for your model
        for motor in self.motors.values():
            motor.setVelocity(base_speed)
        
        return True
    
    def move_relative(self, forward, sideways, up, yaw, duration):
        """Execute relative movement"""
        # This is a simplified implementation
        # In practice, you would implement proper PID control
        
        current_pos = self.get_position()
        self.target_altitude = current_pos["z"] + up
        
        # Basic movement implementation
        # Adjust motor speeds based on desired movement
        base_speed = 300
        
        # Apply differential speeds for movement
        m1_speed = base_speed + forward * 50 - sideways * 50
        m2_speed = base_speed + forward * 50 + sideways * 50  
        m3_speed = base_speed - forward * 50 + sideways * 50
        m4_speed = base_speed - forward * 50 - sideways * 50
        
        # Apply speeds with limits
        speeds = [m1_speed, m2_speed, m3_speed, m4_speed]
        motor_names = ["m1_motor", "m2_motor", "m3_motor", "m4_motor"]
        
        for i, name in enumerate(motor_names):
            speed = max(0, min(600, speeds[i]))
            self.motors[name].setVelocity(speed)
        
        return True
    
    def set_altitude(self, altitude):
        """Set target altitude"""
        self.target_altitude = altitude
        self.hover_altitude = altitude
        
        # Adjust motor speeds based on altitude difference
        current_pos = self.get_position()
        altitude_error = altitude - current_pos["z"]
        
        base_speed = 300
        altitude_adjustment = altitude_error * 100  # Simple P controller
        
        for motor in self.motors.values():
            speed = max(0, min(600, base_speed + altitude_adjustment))
            motor.setVelocity(speed)
        
        return True
    
    def emergency_stop(self):
        """Emergency stop - cut all motors"""
        for motor in self.motors.values():
            motor.setVelocity(0)
        
        self.is_flying = False
        return True

class SimpleMCPController:
    """Main controller class integrating MCP communication with flight control"""
    
    def __init__(self):
        self.robot = Robot()
        self.timestep = int(self.robot.getBasicTimeStep())
        
        # Get robot name
        self.robot_name = "Crazyflie"  # Default name
        
        # Initialize communication
        self.mcp_comm = MCPCommunication(self.robot_name)
        
        # Initialize flight controller
        if CoreFlightController and BasicDroneActions:
            # Use advanced controller if available
            self.flight_controller = CoreFlightController()
            self.basic_actions = BasicDroneActions(self.flight_controller)
            self.use_advanced_controller = True
        else:
            # Use simplified controller
            self.flight_controller = SimplifiedFlightController(self.robot)
            self.use_advanced_controller = False
        
        # Status tracking
        self.current_action = "idle"
        self.action_progress = 0.0
        self.action_start_time = 0
        
        print(f"SimpleMCPController initialized for {self.robot_name}")
        print(f"Using {'advanced' if self.use_advanced_controller else 'simplified'} flight controller")
    
    def process_command(self, command):
        """Process MCP command"""
        action = command.get('action', '')
        
        print(f"[CONTROLLER] 🚁 Processing command: {action}")
        
        try:
            if action == "takeoff":
                altitude = command.get('altitude', 1.0)
                print(f"[CONTROLLER] ✈️ Executing takeoff to altitude: {altitude}m")
                result = self.flight_controller.takeoff(altitude)
                self.current_action = "takeoff"
                self.action_start_time = time.time()
                print(f"[CONTROLLER] ✅ Takeoff command executed: {result}")
                
            elif action == "land":
                print(f"[CONTROLLER] 🛬 Executing landing")
                result = self.flight_controller.land()
                self.current_action = "landing"
                self.action_start_time = time.time()
                
            elif action == "hover":
                duration = command.get('duration', 5.0)
                result = self.flight_controller.hover(duration)
                self.current_action = "hovering"
                self.action_start_time = time.time()
                
            elif action == "move_relative":
                forward = command.get('forward', 0.0)
                sideways = command.get('sideways', 0.0)
                up = command.get('up', 0.0)
                yaw = command.get('yaw', 0.0)
                duration = command.get('duration', 2.0)
                
                result = self.flight_controller.move_relative(forward, sideways, up, yaw, duration)
                self.current_action = "moving"
                self.action_start_time = time.time()
                
            elif action == "set_altitude":
                altitude = command.get('altitude', 1.0)
                result = self.flight_controller.set_altitude(altitude)
                self.current_action = "altitude_adjustment"
                self.action_start_time = time.time()
                
            elif action == "emergency_stop":
                result = self.flight_controller.emergency_stop()
                self.current_action = "emergency_stop"
                self.action_start_time = time.time()
                
            elif action == "get_camera_image":
                result = self.capture_camera_image()
                
            else:
                print(f"Unknown command: {action}")
                result = False
                
            return result
            
        except Exception as e:
            print(f"Error processing command {action}: {e}")
            return False
    
    def capture_camera_image(self):
        """Capture and save camera image"""
        try:
            image_data = self.flight_controller.capture_image()
            if image_data:
                success = self.mcp_comm.save_image(image_data)
                if success:
                    # Update image timestamp in status
                    status = self.get_current_status()
                    status['last_image_timestamp'] = time.time()
                    self.mcp_comm.save_status(status)
                return success
        except Exception as e:
            print(f"Error capturing image: {e}")
        return False
    
    def get_current_status(self):
        """Get current drone status"""
        # Get position
        if self.use_advanced_controller:
            # Use advanced controller methods if available
            position = self.flight_controller.get_position()
        else:
            position = self.flight_controller.get_position()
        
        # Get collision sensors
        collision_sensors = self.flight_controller.get_collision_sensors()
        
        # Determine flight status
        if self.current_action == "emergency_stop":
            flight_status = "emergency"
        elif self.current_action == "takeoff":
            flight_status = "takeoff"
        elif self.current_action == "landing":
            flight_status = "landing"
        elif self.current_action == "hovering":
            flight_status = "hovering"
        elif self.current_action == "moving":
            flight_status = "moving"
        else:
            flight_status = "idle"
        
        # Calculate action progress (simplified)
        if self.action_start_time > 0:
            elapsed = time.time() - self.action_start_time
            if elapsed < 5.0:  # Assume 5 seconds for most actions
                self.action_progress = min(1.0, elapsed / 5.0)
            else:
                self.action_progress = 1.0
                self.current_action = "idle"
        
        status = {
            "timestamp": time.time(),
            "webots_connected": True,
            "flight_status": flight_status,
            "position": position,
            "collision_sensors": collision_sensors,
            "current_action": self.current_action,
            "action_progress": self.action_progress,
            "system_health": "OK"
        }
        
        return status
    
    def run(self):
        """Main control loop"""
        print("[CONTROLLER] Starting SimpleMCPController main loop")
        print(f"[CONTROLLER] Data directory: {self.mcp_comm.data_dir}")
        
        step_count = 0
        while self.robot.step(self.timestep) != -1:
            step_count += 1
            
            # Check for new commands
            command = self.mcp_comm.get_new_command()
            if command:
                print(f"[CONTROLLER] Processing command: {command}")
                self.process_command(command)
            
            # Update status
            status = self.get_current_status()
            self.mcp_comm.save_status(status)
            
            # Print status periodically
            if step_count % 100 == 0:  # Every ~3 seconds (100 steps * 32ms)
                print(f"[CONTROLLER] Status: {status['flight_status']}, Action: {status['current_action']}, "
                      f"Position: ({status['position']['x']:.2f}, {status['position']['y']:.2f}, {status['position']['z']:.2f})")
                print(f"[CONTROLLER] Commands file exists: {self.mcp_comm.commands_file.exists()}")

if __name__ == "__main__":
    controller = SimpleMCPController()
    controller.run()
