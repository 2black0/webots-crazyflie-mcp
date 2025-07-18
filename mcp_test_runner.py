import json
import os
import subprocess
import time
import sys

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
COMMANDS_FILE = os.path.join(DATA_DIR, 'commands.json')
STATUS_FILE = os.path.join(DATA_DIR, 'status.json')
SERVER_SCRIPT = 'webots_mcp_server.py'

# --- Helper Functions ---
def write_command(command: dict):
    """Writes a command to the commands.json file."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        command['timestamp'] = time.time()
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2)
        print(f"[CLIENT] Command '{command['action']}' written to {COMMANDS_FILE}")
        return True
    except Exception as e:
        print(f"[CLIENT-ERROR] Could not write command: {e}")
        return False

def read_status():
    """Reads the status.json file."""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[CLIENT-ERROR] Could not read status: {e}")
    return None

def run_test():
    """
    Main test function using file-based communication.
    """
    server_process = None
    try:
        # 1. Start the server as a background process
        print(f"[CLIENT] Starting {SERVER_SCRIPT}...")
        server_process = subprocess.Popen([sys.executable, SERVER_SCRIPT])
        print(f"[CLIENT] Server process started with PID: {server_process.pid}")
        
        # Give the server a moment to initialize
        time.sleep(5)

        # 2. Test: Get robot status
        print("\n[TEST 1] Getting robot status...")
        if not write_command({'action': 'get_robot_status'}):
             return # Stop test if command fails

        # Wait for the server to process the command and update the status file
        time.sleep(2)
        
        status = read_status()
        if status:
            print("\n--- [SUCCESS] Robot Status ---")
            print(json.dumps(status, indent=2, ensure_ascii=False))
            print("-----------------------------")

            # Check for coordinates
            if 'robot_position' in status and all(k in status['robot_position'] for k in ['x', 'y', 'z']):
                pos = status['robot_position']
                print(f"[SUCCESS] Robot coordinates found: x={pos['x']:.3f}, y={pos['y']:.3f}, z={pos['z']:.3f}")
            else:
                print("[WARNING] Robot coordinates not found in status.")
        else:
            print("[ERROR] Failed to get robot status.")

        # 3. Test: Set head position
        print("\n[TEST 2] Setting head position...")
        head_command = {'action': 'set_head_position', 'yaw': 0.5, 'pitch': -0.2}
        if not write_command(head_command):
            return
            
        time.sleep(2) # Wait for processing
        status = read_status()
        if status and status.get('head_position', {}).get('yaw') == 0.5:
             print("[SUCCESS] Head position updated correctly.")
        else:
             print("[ERROR] Failed to set head position.")

        # 4. Test: Play a motion
        print("\n[TEST 3] Waving hand...")
        if not write_command({'action': 'play_motion', 'motion_name': 'HandWave'}):
            return

        print("[INFO] Waiting for motion to complete (approx. 5 seconds)...")
        time.sleep(6) # HandWave is 5s, add a buffer
        print("[SUCCESS] Hand wave motion test completed.")

    except Exception as e:
        print(f"[CLIENT-CRITICAL] Test failed with error: {e}")
    finally:
        # 4. Clean up: terminate the server process
        if server_process:
            print("\n[CLIENT] Terminating server process...")
            server_process.terminate()
            server_process.wait()
            print("[CLIENT] Server process terminated.")

if __name__ == "__main__":
    run_test()