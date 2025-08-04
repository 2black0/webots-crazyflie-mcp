#!/bin/bash
# Complete Crazyflie MCP System Launcher

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
MCP_SERVER="crazyflie_mcp_standalone.py"
WORLD_FILE="worlds/complete_apartment.wbt"
CONTROLLER_DIR="controllers/mcp_simple"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')]${NC} ⚠️  $1"
}

print_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')]${NC} ❌ $1"
}

echo "🚁 Crazyflie MCP System Launcher"
echo "=================================="

# Activate conda environment
print_status "Activating conda environment 'llm-drone'..."
if command -v conda &> /dev/null; then
    # Initialize conda for bash
    eval "$(conda shell.bash hook)"
    conda activate llm-drone
    if [[ $? -eq 0 ]]; then
        print_status "✅ Conda environment 'llm-drone' activated"
        print_status "Python: $(which python3)"
    else
        print_error "Failed to activate conda environment 'llm-drone'"
        print_status "Please ensure the environment exists: conda create -n llm-drone python=3.10"
        exit 1
    fi
else
    print_error "Conda not found. Please install Anaconda/Miniconda"
    exit 1
fi

# Parse arguments
MODE="full"
WEBOTS_GUI=false
if [[ "$1" == "--server-only" ]]; then
    MODE="server"
elif [[ "$1" == "--webots-only" ]]; then
    MODE="webots"
elif [[ "$1" == "--gui" ]]; then
    MODE="full"
    WEBOTS_GUI=true
elif [[ "$1" == "--help" ]]; then
    echo "Usage: $0 [--server-only|--webots-only|--gui|--help]"
    echo "  --server-only : Run only MCP server"
    echo "  --webots-only : Run only Webots simulation (headless)"
    echo "  --gui         : Run complete system with Webots GUI"
    echo "  --help        : Show this help"
    echo "  (no args)     : Run complete system (headless Webots)"
    exit 0
fi

# Check prerequisites
print_status "Checking prerequisites..."

# Verify Python from conda environment
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found in llm-drone environment"
    exit 1
fi

# Check if we're in the right environment
CURRENT_ENV=$(conda info --envs | grep '*' | awk '{print $1}')
if [[ "$CURRENT_ENV" != "llm-drone" ]]; then
    print_warning "Not in llm-drone environment (current: $CURRENT_ENV)"
    print_status "Attempting to activate llm-drone..."
    conda activate llm-drone || exit 1
fi

print_status "Environment: $(conda info --envs | grep '*')"
print_status "Python path: $(which python3)"

# Check required Python packages
print_status "Checking Python dependencies..."
python3 -c "import yaml, numpy, cv2" 2>/dev/null
if [[ $? -ne 0 ]]; then
    print_warning "Missing dependencies. Installing..."
    pip install pyyaml numpy opencv-python
fi

# Find Webots executable
WEBOTS_CMD=""
if command -v webots &> /dev/null; then
    WEBOTS_CMD="webots"
elif [[ -f "/Applications/Webots.app/Contents/MacOS/webots" ]]; then
    WEBOTS_CMD="/Applications/Webots.app/Contents/MacOS/webots"
elif [[ -f "/usr/local/bin/webots" ]]; then
    WEBOTS_CMD="/usr/local/bin/webots"
fi

if [[ "$MODE" != "server" ]] && [[ -z "$WEBOTS_CMD" ]]; then
    print_warning "Webots not found"
    print_status "Please install Webots, or run with --server-only"
    if [[ "$MODE" == "full" ]]; then
        MODE="server"
        print_status "Switching to server-only mode"
    elif [[ "$MODE" == "webots" ]]; then
        print_error "Cannot run Webots without Webots installed"
        exit 1
    fi
fi

# Check files
if [[ ! -f "$MCP_SERVER" ]]; then
    print_error "MCP server file not found: $MCP_SERVER"
    exit 1
fi

if [[ "$MODE" != "server" ]] && [[ ! -f "$WORLD_FILE" ]]; then
    print_error "World file not found: $WORLD_FILE"
    exit 1
fi

if [[ "$MODE" != "server" ]] && [[ ! -d "$CONTROLLER_DIR" ]]; then
    print_error "Controller directory not found: $CONTROLLER_DIR"
    exit 1
fi

# Create directories
mkdir -p data logs
print_status "Directories created/verified"

# Cleanup function
cleanup() {
    print_status "Shutting down system..."
    
    # Kill MCP server
    if [[ -f "logs/mcp_server.pid" ]]; then
        MCP_PID=$(cat logs/mcp_server.pid)
        if kill -0 $MCP_PID 2>/dev/null; then
            kill $MCP_PID 2>/dev/null
            print_status "MCP Server stopped"
        fi
        rm -f logs/mcp_server.pid
    fi
    
    # Kill Webots
    if [[ -f "logs/webots.pid" ]]; then
        WEBOTS_PID=$(cat logs/webots.pid)
        if kill -0 $WEBOTS_PID 2>/dev/null; then
            kill $WEBOTS_PID 2>/dev/null
            print_status "Webots stopped"
        fi
        rm -f logs/webots.pid
    fi
    
    # Clean up any remaining processes
    pkill -f "crazyflie_mcp_standalone.py" 2>/dev/null
    pkill -f "webots.*complete_apartment.wbt" 2>/dev/null
    
    print_status "Cleanup completed"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start services based on mode
if [[ "$MODE" == "server" ]] || [[ "$MODE" == "full" ]]; then
    print_status "Starting MCP Server..."
    python3 "$MCP_SERVER" > logs/mcp_server.log 2>&1 &
    MCP_PID=$!
    
    sleep 2
    if kill -0 $MCP_PID 2>/dev/null; then
        echo $MCP_PID > logs/mcp_server.pid
        print_status "✅ MCP Server started (PID: $MCP_PID)"
    else
        print_error "MCP Server failed to start"
        cat logs/mcp_server.log
        exit 1
    fi
fi

if [[ "$MODE" == "webots" ]] || [[ "$MODE" == "full" ]]; then
    print_status "Starting Webots simulation (headless mode)..."
    
    # Set up Webots environment variables
    if [[ -d "/Applications/Webots.app/Contents" ]]; then
        export WEBOTS_HOME="/Applications/Webots.app/Contents"
        export PYTHONPATH="$WEBOTS_HOME/lib/controller/python:$PYTHONPATH"
        print_status "Webots environment: WEBOTS_HOME=$WEBOTS_HOME"
    fi
    
    # Webots headless flags for MCP usage (unless GUI mode requested)
    if [[ "$WEBOTS_GUI" == "true" ]]; then
        WEBOTS_FLAGS=""
        print_status "GUI mode enabled - Webots window will be visible"
    else
        WEBOTS_FLAGS="--minimize --no-rendering --batch --mode=fast"
        print_status "Headless mode - optimized for MCP operations"
    fi
    
    "$WEBOTS_CMD" $WEBOTS_FLAGS "$WORLD_FILE" > logs/webots.log 2>&1 &
    WEBOTS_PID=$!
    
    sleep 3
    if kill -0 $WEBOTS_PID 2>/dev/null; then
        echo $WEBOTS_PID > logs/webots.pid
        print_status "✅ Webots simulation started (PID: $WEBOTS_PID) - Headless mode"
        print_status "Controller: mcp_simple (MCP communication bridge)"
    else
        print_error "Webots failed to start"
        cat logs/webots.log
        if [[ "$MODE" == "full" ]]; then
            cleanup
        fi
        exit 1
    fi
fi

# System status
echo ""
print_status "🎉 System is running!"
echo ""

if [[ "$MODE" == "full" ]]; then
    print_status "Complete system active:"
    print_status "  • MCP Server: Providing 11 drone control tools"
    print_status "  • Webots Sim: Crazyflie simulation running"
    print_status "  • Controller: MCP communication bridge active"
elif [[ "$MODE" == "server" ]]; then
    print_status "MCP Server only mode:"
    print_status "  • Server ready to accept drone commands"
    print_status "  • Use interactive mode or external clients"
elif [[ "$MODE" == "webots" ]]; then
    print_status "Webots only mode:"
    print_status "  • Simulation running with MCP controller"
    print_status "  • Waiting for external MCP server connection"
fi

echo ""
print_status "🔧 Useful commands:"
print_status "  • View MCP logs: tail -f logs/mcp_server.log"
print_status "  • View Webots logs: tail -f logs/webots.log"
print_status "  • Send command: echo '{\"action\":\"takeoff\"}' > data/Crazyflie/commands.json"
print_status "  • Check status: cat data/Crazyflie/status.json"
echo ""
print_status "Press Ctrl+C to stop the system"

# Monitor loop
while true; do
    sleep 5
    
    # Check MCP server
    if [[ -f "logs/mcp_server.pid" ]]; then
        MCP_PID=$(cat logs/mcp_server.pid)
        if ! kill -0 $MCP_PID 2>/dev/null; then
            print_error "MCP Server stopped unexpectedly"
            break
        fi
    fi
    
    # Check Webots
    if [[ -f "logs/webots.pid" ]]; then
        WEBOTS_PID=$(cat logs/webots.pid)
        if ! kill -0 $WEBOTS_PID 2>/dev/null; then
            print_warning "Webots simulation stopped"
            break
        fi
    fi
done

cleanup
