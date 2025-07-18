"""
Controller for the NAO robot in Webots with MCP server integration.

This controller:
1. Manages the robot in Webots
2. Runs the MCP server in a separate thread
3. Exchanges data with the MCP server through files
4. Validates motor positions for safe control
"""

import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from controller import Robot, Motion

# --- Paths for data exchange ---
CONTROLLER_DIR = Path(__file__).parent
ROBOT_DIR = CONTROLLER_DIR.parent.parent
DATA_DIR = ROBOT_DIR / "data"
COMMANDS_FILE = DATA_DIR / "commands.json"
STATUS_FILE = DATA_DIR / "status.json"

# Create the data directory
DATA_DIR.mkdir(exist_ok=True)

# Clear the commands file on controller startup
if COMMANDS_FILE.exists():
    try:
        os.remove(COMMANDS_FILE)
        print("✅ Old commands file cleared on startup.")
    except OSError as e:
        print(f"❌ Error clearing commands file on startup: {e}")

# --- NAO motor position ranges (in radians) ---
MOTOR_LIMITS = {
    # Head
    "HeadYaw": (-2.0857, 2.0857),      # ±119.5°
    "HeadPitch": (-0.6720, 0.5149),    # -38.5° to 29.5°

    # Shoulders
    "LShoulderPitch": (-2.0857, 2.0857),  # ±119.5°
    "RShoulderPitch": (-2.0857, 2.0857),  # ±119.5°
    "LShoulderRoll": (-0.3142, 1.3265),   # -18° to 76°
    "RShoulderRoll": (-1.3265, 0.3142),   # -76° to 18°

    # Elbows
    "LElbowYaw": (-2.0857, 2.0857),    # ±119.5°
    "RElbowYaw": (-2.0857, 2.0857),    # ±119.5°
    "LElbowRoll": (-1.5446, -0.0349),  # -88.5° to -2°
    "RElbowRoll": (0.0349, 1.5446),    # 2° to 88.5°

    # Wrists
    "LWristYaw": (-1.8238, 1.8238),    # ±104.5°
    "RWristYaw": (-1.8238, 1.8238),    # ±104.5°

    # Hips
    "LHipYawPitch": (-1.145303, 0.740810),  # -65.62° to 42.44°
    "RHipYawPitch": (-1.145303, 0.740810),  # -65.62° to 42.44°
    "LHipRoll": (-0.379472, 0.790477),      # -21.74° to 45.29°
    "RHipRoll": (-0.790477, 0.379472),      # -45.29° to 21.74°
    "LHipPitch": (-1.773912, 0.484090),     # -101.63° to 27.73°
    "RHipPitch": (-1.773912, 0.484090),     # -101.63° to 27.73°

    # Knees
    "LKneePitch": (-0.092346, 2.112528),    # -5.29° to 121.04°
    "RKneePitch": (-0.092346, 2.112528),    # -5.29° to 121.04°

    # Ankles
    "LAnklePitch": (-1.189516, 0.922747),   # -68.15° to 52.86°
    "RAnklePitch": (-1.189516, 0.922747),   # -68.15° to 52.86°
    "LAnkleRoll": (-0.397880, 0.769001),    # -22.79° to 44.06°
    "RAnkleRoll": (-0.769001, 0.397880),    # -44.06° to 22.79°
}

# --- Robot initialization ---
robot = Robot()
timestep = int(robot.getBasicTimeStep())

# --- Global variables ---
robot_state = {
    "walking_active": False,
    "last_command_time": 0,
    "current_motion": None,
    "last_image_timestamp": 0
}
motions = {}

# --- Motor initialization ---
motors = {}
motor_names = [
    "HeadYaw", "HeadPitch",
    "LShoulderPitch", "RShoulderPitch",
    "LShoulderRoll", "RShoulderRoll",
    "LElbowYaw", "RElbowYaw",
    "LElbowRoll", "RElbowRoll",
    "LWristYaw", "RWristYaw",
    "LHipYawPitch", "RHipYawPitch",
    "LHipRoll", "RHipRoll",
    "LHipPitch", "RHipPitch",
    "LKneePitch", "RKneePitch",
    "LAnklePitch", "RAnklePitch",
    "LAnkleRoll", "RAnkleRoll"
]

motors_found = True
try:
    for motor_name in motor_names:
        motors[motor_name] = robot.getDevice(motor_name)
    print("✅ All motors found")
except Exception as e:
    motors_found = False
    print(f"❌ Error initializing motors: {e}")

# --- Camera initialization ---
camera = None
camera_found = True
try:
    camera = robot.getDevice("CameraTop")
    if camera:
        camera.enable(timestep)
        print("✅ Camera found and enabled")
    else:
        camera_found = False
        print("❌ 'CameraTop' not found")
except Exception as e:
    camera_found = False
    print(f"❌ Error initializing camera: {e}")

# --- LED initialization ---
leds = {}
led_names = [
    "ChestBoard/Led", "RFoot/Led", "LFoot/Led",
    "Face/Led/Right", "Face/Led/Left",
    "Ears/Led/Right", "Ears/Led/Left"
]
leds_found = True
try:
    for led_name in led_names:
        leds[led_name] = robot.getDevice(led_name)
    print("✅ All LEDs found")
except Exception as e:
    leds_found = False
    print(f"❌ Error initializing LEDs: {e}")

# --- GPS initialization ---
gps = None
gps_found = True
try:
    gps = robot.getDevice("gps")
    if gps:
        gps.enable(timestep)
        print("✅ GPS found and enabled")
    else:
        gps_found = False
        print("❌ GPS sensor not found")
except Exception as e:
    gps_found = False
    print(f"❌ Error initializing GPS: {e}")


# --- Validation functions ---
def validate_motor_position(motor_name, position):
    """
    Validates the motor position according to its physical limitations.

    Args:
        motor_name (str): The name of the motor
        position (float): The target position in radians

    Returns:
        tuple: (validated_position, is_valid, warning_message)
    """
    if motor_name not in MOTOR_LIMITS:
        return position, False, f"Unknown motor: {motor_name}"

    min_pos, max_pos = MOTOR_LIMITS[motor_name]

    if min_pos <= position <= max_pos:
        return position, True, None

    # Clamp the position to the allowable limits
    clamped_position = max(min_pos, min(max_pos, position))

    warning = (f"Motor position {motor_name} ({position:.3f} rad = {math.degrees(position):.1f}°) "
              f"is outside the limits [{min_pos:.3f}, {max_pos:.3f}] rad "
              f"[{math.degrees(min_pos):.1f}°, {math.degrees(max_pos):.1f}°]. "
              f"Clamped to {clamped_position:.3f} rad ({math.degrees(clamped_position):.1f}°)")

    return clamped_position, False, warning

def validate_motor_positions(positions_dict):
    """
    Validates a dictionary of motor positions.

    Args:
        positions_dict (dict): A dictionary of {motor_name: position}

    Returns:
        tuple: (validated_positions, warnings_list)
    """
    validated_positions = {}
    warnings = []

    for motor_name, position in positions_dict.items():
        validated_pos, is_valid, warning = validate_motor_position(motor_name, position)
        validated_positions[motor_name] = validated_pos

        if not is_valid and warning:
            warnings.append(warning)

    return validated_positions, warnings

def set_motor_position_safe(motor_name, position):
    """
    Safely sets the motor position with validation.

    Args:
        motor_name (str): The name of the motor
        position (float): The target position in radians

    Returns:
        bool: True if the position was set successfully
    """
    if not motors_found or motor_name not in motors:
        print(f"❌ Motor {motor_name} not found")
        return False

    validated_pos, is_valid, warning = validate_motor_position(motor_name, position)

    if warning:
        print(f"⚠️ {warning}")

    try:
        motors[motor_name].setPosition(validated_pos)
        return True
    except Exception as e:
        print(f"❌ Error setting motor position {motor_name}: {e}")
        return False

# --- Control functions ---
def set_initial_pose():
    """Sets the initial pose of the robot with validation."""
    if not motors_found:
        return

    # Safe initial positions
    initial_positions = {
        "HeadYaw": 0.0,
        "HeadPitch": 0.0,
        "LShoulderPitch": 0.0,
        "RShoulderPitch": 0.0,
        "LShoulderRoll": 0.0,
        "RShoulderRoll": 0.0,
        "LElbowYaw": 0.0,
        "RElbowYaw": 0.0,
        "LElbowRoll": -0.5,  # Slightly bent elbows
        "RElbowRoll": 0.5,   # Slightly bent elbows
        "LWristYaw": 0.0,
        "RWristYaw": 0.0,
        "LHipYawPitch": 0.0,
        "RHipYawPitch": 0.0,
        "LHipRoll": 0.0,
        "RHipRoll": 0.0,
        "LHipPitch": 0.0,
        "RHipPitch": 0.0,
        "LKneePitch": 0.0,
        "RKneePitch": 0.0,
        "LAnklePitch": 0.0,
        "RAnklePitch": 0.0,
        "LAnkleRoll": 0.0,
        "RAnkleRoll": 0.0
    }

    validated_positions, warnings = validate_motor_positions(initial_positions)

    for warning in warnings:
        print(f"⚠️ {warning}")

    for motor_name, position in validated_positions.items():
        if motor_name in motors:
            motors[motor_name].setPosition(position)

    print("✅ Initial pose set with validation")

def load_motions():
    """Loads all animation files from the motions folder."""
    global motions
    motions_dir = ROBOT_DIR / "motions"
    for motion_file in motions_dir.glob("*.motion"):
        name = motion_file.stem
        motions[name] = Motion(str(motion_file))
    print(f"✅ Loaded {len(motions)} animations.")

def get_motion_first_pose(motion_path):
    """Reads the first pose from a .motion file with validation."""
    try:
        with open(motion_path, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.split(',')
                if len(parts) > 1 and 'Pose' in parts[1]:
                    pose_data = {}
                    header_line = ""
                    with open(motion_path, 'r') as f_header:
                        header_line = f_header.readline().strip()

                    motor_names_from_file = header_line.split(',')[2:]

                    for i, value_str in enumerate(parts[2:]):
                        if i < len(motor_names_from_file):
                            motor_name = motor_names_from_file[i]
                            pose_data[motor_name] = float(value_str)

                    # Validate the positions from the animation file
                    validated_pose, warnings = validate_motor_positions(pose_data)

                    if warnings:
                        print(f"⚠️ Warnings for animation {motion_path.name}:")
                        for warning in warnings:
                            print(f"   {warning}")

                    return validated_pose
    except Exception as e:
        print(f"❌ Error reading first pose from {motion_path}: {e}")
    return None

def start_motion(motion_name):
    """Smoothly transitions to the initial pose and starts the animation."""
    global robot_state
    if robot_state['current_motion'] and not robot_state['current_motion'].isOver():
        robot_state['current_motion'].stop()
        print("⏹️ Previous animation stopped")

    # Clear the name from the extension if it exists
    motion_name = motion_name.split('.')[0]

    motion = motions.get(motion_name)
    if not motion:
        print(f"❌ Animation '{motion_name}' not found in loaded.")
        robot_state['current_motion'] = None
        return

    motion_path = ROBOT_DIR / "motions" / (motion_name + ".motion")
    first_pose = get_motion_first_pose(motion_path)

    if first_pose:
        print("🔄 Smooth transition to the first pose with validation")
        transition_duration = 1.0  # Transition duration in seconds
        start_time = robot.getTime()
        current_positions = {}

        # Get the current positions with validation
        for name, motor in motors.items():
            try:
                current_positions[name] = motor.getTargetPosition()
            except:
                current_positions[name] = 0.0

        while robot.getTime() - start_time < transition_duration:
            elapsed = robot.getTime() - start_time
            ratio = elapsed / transition_duration

            for name, target_pos in first_pose.items():
                if name in motors:
                    current_pos = current_positions.get(name, 0.0)
                    new_pos = current_pos + (target_pos - current_pos) * ratio
                    set_motor_position_safe(name, new_pos)

            robot.step(timestep)
        print("✅ Transition to the first pose completed")

    # --- Play the main animation ---
    try:
        motion.play()
        robot_state['current_motion'] = motion
        print(f"▶️ Playing animation: {motion_name}")
    except Exception as e:
        print(f"❌ Error starting animation {motion_name}: {e}")
        robot_state['current_motion'] = None

def update_motion():
    """Checks and updates the status of the current animation."""
    global robot_state
    if robot_state['current_motion'] and robot_state['current_motion'].isOver():
        print(f"✅ Animation completed")
        robot_state['current_motion'] = None

def process_commands():
    """Processes commands from the MCP server with validation."""
    # Block commands during animation
    if robot_state['current_motion'] and not robot_state['current_motion'].isOver():
        return

    if not COMMANDS_FILE.exists():
        return

    try:
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            command = json.load(f)

        command_time = command.get('timestamp', 0)
        if command_time <= robot_state['last_command_time']:
            return

        robot_state['last_command_time'] = command_time
        action = command.get('action')

        if action == "set_head_position":
            if motors_found:
                yaw = command.get('yaw', 0.0)
                pitch = command.get('pitch', 0.0)

                success_yaw = set_motor_position_safe("HeadYaw", yaw)
                success_pitch = set_motor_position_safe("HeadPitch", pitch)

                if success_yaw and success_pitch:
                    print(f"✅ Head set: yaw={yaw:.3f} rad ({math.degrees(yaw):.1f}°), "
                          f"pitch={pitch:.3f} rad ({math.degrees(pitch):.1f}°)")

        elif action == "reset_pose":
            set_initial_pose()

        elif action == "play_motion":
            motion_name = command.get("motion_name")
            if motion_name:
                start_motion(motion_name)
            else:
                print("❌ 'play_motion' command does not contain 'motion_name'")

        elif action == "get_camera_image":
            if camera_found and camera:
                image_path = DATA_DIR / "camera_image.jpg"
                camera.saveImage(str(image_path), 100)
                robot_state['last_image_timestamp'] = time.time()
                print(f"✅ Image saved to {image_path}")
            else:
                print("❌ Camera not found, cannot get image")

        elif action == "set_leds":
            if leds_found:
                color = command.get('color', 0)
                for led_name, led in leds.items():
                    try:
                        led.set(color)
                    except Exception as e:
                        print(f"❌ Error setting color for {led_name}: {e}")
                print(f"✅ Set LED color: {hex(color)}")
            else:
                print("❌ LEDs not found, cannot set color")

        elif action == "validate_position":
            # New command to check the validity of a position
            motor_name = command.get("motor_name")
            position = command.get("position", 0.0)

            if motor_name:
                validated_pos, is_valid, warning = validate_motor_position(motor_name, position)
                print(f"🔍 Validating {motor_name}: {position:.3f} rad ({math.degrees(position):.1f}°)")
                if is_valid:
                    print(f"✅ Position is valid")
                else:
                    print(f"⚠️ {warning}")
            else:
                print("❌ 'validate_position' command does not contain 'motor_name'")

    except json.JSONDecodeError:
        # Expected error if the file is empty or incorrect
        pass
    except Exception as e:
        print(f"❌ Error processing command: {e}")

def update_status():
    """Updates the status for the MCP server."""
    current_time = time.time()

    # Get the current motor positions
    head_position = {"yaw": 0.0, "pitch": 0.0}
    arm_positions = {
        "left_shoulder_pitch": 0.0,
        "right_shoulder_pitch": 0.0,
        "left_shoulder_roll": 0.0,
        "right_shoulder_roll": 0.0,
        "left_elbow_yaw": 0.0,
        "right_elbow_yaw": 0.0,
        "left_elbow_roll": 0.0,
        "right_elbow_roll": 0.0,
        "left_wrist_yaw": 0.0,
        "right_wrist_yaw": 0.0
    }

    if motors_found:
        try:
            head_position["yaw"] = motors["HeadYaw"].getTargetPosition()
            head_position["pitch"] = motors["HeadPitch"].getTargetPosition()
            arm_positions["left_shoulder_pitch"] = motors["LShoulderPitch"].getTargetPosition()
            arm_positions["right_shoulder_pitch"] = motors["RShoulderPitch"].getTargetPosition()
            arm_positions["left_shoulder_roll"] = motors["LShoulderRoll"].getTargetPosition()
            arm_positions["right_shoulder_roll"] = motors["RShoulderRoll"].getTargetPosition()
            arm_positions["left_elbow_yaw"] = motors["LElbowYaw"].getTargetPosition()
            arm_positions["right_elbow_yaw"] = motors["RElbowYaw"].getTargetPosition()
            arm_positions["left_elbow_roll"] = motors["LElbowRoll"].getTargetPosition()
            arm_positions["right_elbow_roll"] = motors["RElbowRoll"].getTargetPosition()
            arm_positions["left_wrist_yaw"] = motors["LWristYaw"].getTargetPosition()
            arm_positions["right_wrist_yaw"] = motors["RWristYaw"].getTargetPosition()
        except Exception as e:
            print(f"❌ Error getting motor positions: {e}")

    # Form the status
    status_data = {
        "timestamp": current_time,
        "webots_connected": True,
        "robot_position": {"x": 0, "y": 0, "z": 0}, # Placeholder
        "head_position": head_position,
        "arm_positions": arm_positions,
        "walking_active": robot_state['walking_active'],
        "last_image_timestamp": robot_state.get('last_image_timestamp', 0),
        "motor_limits": {name: {"min": limits[0], "max": limits[1]} for name, limits in MOTOR_LIMITS.items()}
    }

    # Get the robot's coordinates if GPS is available
    if gps_found and gps:
        try:
            coords = gps.getValues()
            status_data["robot_position"] = {"x": coords[0], "y": coords[1], "z": coords[2]}
        except Exception as e:
            print(f"❌ Error getting GPS coordinates: {e}")

    # Write the status to the file
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error writing status: {e}")

# --- Main loop ---
if __name__ == "__main__":
    print("🔧 Initializing with motor position validation...")
    print(f"📊 Loaded {len(MOTOR_LIMITS)} motor position ranges")

    set_initial_pose()
    load_motions()

    print("🚀 Robot controller started. Waiting for commands...")

    # Main simulation loop
    while robot.step(timestep) != -1:
        process_commands()
        update_motion()
        update_status()

    print("🚪 Robot controller is shutting down.")
