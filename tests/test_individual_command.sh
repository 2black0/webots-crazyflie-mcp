#!/bin/bash
# Individual MCP Command Testing Script

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

# Check if system is running
check_system() {
    if [[ ! -f "logs/mcp_server.pid" ]] || ! kill -0 $(cat logs/mcp_server.pid) 2>/dev/null; then
        echo -e "${RED}❌ MCP Server not running${NC}"
        echo "Please start the system first:"
        echo "  bash run.sh"
        return 1
    fi
    
    if [[ ! -f "logs/webots.pid" ]] || ! kill -0 $(cat logs/webots.pid) 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Webots not running (server-only mode?)${NC}"
    fi
    
    return 0
}

# Send command and get response
send_command() {
    local cmd="$1"
    local description="$2"
    
    echo -e "${BLUE}🚁 Testing:${NC} $description"
    echo -e "${BLUE}Command:${NC} $cmd"
    
    # Send command
    echo "$cmd" > data/Crazyflie/commands.json
    if [[ $? -ne 0 ]]; then
        echo -e "${RED}❌ Failed to send command${NC}"
        return 1
    fi
    
    # Wait for response
    echo "⏳ Waiting for response..."
    sleep 3
    
    # Get response
    if [[ -f "data/Crazyflie/status.json" ]]; then
        local response=$(cat data/Crazyflie/status.json)
        echo -e "${GREEN}✅ Response received:${NC}"
        echo "$response" | jq . 2>/dev/null || echo "$response"
        return 0
    else
        echo -e "${RED}❌ No response file found${NC}"
        return 1
    fi
}

# Usage help
show_help() {
    echo "🚁 Individual MCP Command Tester"
    echo "================================"
    echo ""
    echo "Usage: $0 [command_name|--interactive|--list|--help]"
    echo ""
    echo "Available commands:"
    echo "  status          - Get drone status"
    echo "  takeoff         - Launch drone"
    echo "  land            - Land drone"
    echo "  hover           - Maintain position"
    echo "  move_forward    - Move 1m forward"
    echo "  move_back       - Move 1m backward"
    echo "  move_right      - Move 1m right"
    echo "  move_left       - Move 1m left"
    echo "  move_up         - Move 0.5m up"
    echo "  move_down       - Move 0.5m down"
    echo "  rotate_left     - Rotate 45° left"
    echo "  rotate_right    - Rotate 45° right"
    echo "  goto_home       - Move to origin"
    echo "  set_altitude    - Set altitude to 2m"
    echo "  sensors         - Get sensor data"
    echo "  emergency       - Emergency stop"
    echo ""
    echo "Options:"
    echo "  --interactive   - Interactive mode"
    echo "  --list          - List all available commands"
    echo "  --help          - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 takeoff"
    echo "  $0 --interactive"
}

# Interactive mode
interactive_mode() {
    echo "🎮 Interactive MCP Command Tester"
    echo "================================="
    echo "Type command name or 'quit' to exit"
    echo "Type 'help' for available commands"
    echo ""
    
    while true; do
        echo -n "mcp> "
        read -r input
        
        case "$input" in
            "quit"|"exit"|"q")
                echo "Goodbye!"
                break
                ;;
            "help"|"h")
                show_help
                ;;
            "")
                continue
                ;;
            *)
                execute_command "$input"
                echo ""
                ;;
        esac
    done
}

# Execute command by name
execute_command() {
    local cmd_name="$1"
    
    case "$cmd_name" in
        "status")
            send_command '{"action":"status"}' "Get current drone status"
            ;;
        "takeoff")
            send_command '{"action":"takeoff"}' "Launch drone to hover position"
            ;;
        "land")
            send_command '{"action":"land"}' "Land drone safely"
            ;;
        "hover")
            send_command '{"action":"hover"}' "Maintain current position"
            ;;
        "move_forward")
            send_command '{"action":"move_relative","x":1.0,"y":0.0,"z":0.0}' "Move 1m forward"
            ;;
        "move_back")
            send_command '{"action":"move_relative","x":-1.0,"y":0.0,"z":0.0}' "Move 1m backward"
            ;;
        "move_right")
            send_command '{"action":"move_relative","x":0.0,"y":1.0,"z":0.0}' "Move 1m right"
            ;;
        "move_left")
            send_command '{"action":"move_relative","x":0.0,"y":-1.0,"z":0.0}' "Move 1m left"
            ;;
        "move_up")
            send_command '{"action":"move_relative","x":0.0,"y":0.0,"z":0.5}' "Move 0.5m up"
            ;;
        "move_down")
            send_command '{"action":"move_relative","x":0.0,"y":0.0,"z":-0.5}' "Move 0.5m down"
            ;;
        "rotate_left")
            send_command '{"action":"rotate","angle":-45}' "Rotate 45° left"
            ;;
        "rotate_right")
            send_command '{"action":"rotate","angle":45}' "Rotate 45° right"
            ;;
        "goto_home")
            send_command '{"action":"move_to_position","x":0.0,"y":0.0,"z":1.5}' "Move to home position"
            ;;
        "set_altitude")
            send_command '{"action":"set_altitude","altitude":2.0}' "Set altitude to 2 meters"
            ;;
        "sensors")
            send_command '{"action":"get_sensor_data"}' "Get all sensor readings"
            ;;
        "emergency")
            send_command '{"action":"emergency_stop"}' "Emergency stop and land"
            ;;
        "reset")
            send_command '{"action":"reset_position"}' "Reset to initial position"
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $cmd_name${NC}"
            echo "Use '$0 --help' to see available commands"
            return 1
            ;;
    esac
}

# Main script
if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

# Check if jq is available for JSON formatting
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠️  jq not found - JSON responses will not be formatted${NC}"
fi

# Parse arguments
case "$1" in
    "--help"|"-h")
        show_help
        ;;
    "--list"|"-l")
        echo "Available commands: status takeoff land hover move_forward move_back move_right move_left move_up move_down rotate_left rotate_right goto_home set_altitude sensors emergency reset"
        ;;
    "--interactive"|"-i")
        check_system || exit 1
        interactive_mode
        ;;
    *)
        check_system || exit 1
        execute_command "$1"
        ;;
esac
