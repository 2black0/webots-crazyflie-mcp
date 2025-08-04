# 🚁 Crazyflie MCP (Model Context Protocol) for Webots

A complete MCP server implementation for controlling Crazyflie drones in Webots simulation environment.

## 🚀 Quick Start

### Prerequisites
- Webots R2023b or later
- Python 3.10+
- Conda environment manager

### Setup & Run
```bash
# 1. Setup conda environment
conda create -n llm-drone python=3.11
conda activate llm-drone
pip install -r requirements.txt

# 2. Start the system
bash run.sh
```

## 🎮 Basic Usage

### Command Format
Send JSON commands to `data/Crazyflie/commands.json`:

```bash
# Takeoff to 1.5m altitude
echo '{"action":"takeoff","altitude":1.5}' > data/Crazyflie/commands.json

# Move forward 1 meter
echo '{"action":"move_relative","x":1.0,"y":0.0,"z":0.0}' > data/Crazyflie/commands.json

# Rotate 45 degrees
echo '{"action":"rotate","angle":45}' > data/Crazyflie/commands.json

# Land safely
echo '{"action":"land"}' > data/Crazyflie/commands.json
```

### Check Status
```bash
cat data/Crazyflie/status.json
```

## 🧪 Testing

### Test All Commands
```bash
./tests/test_all_commands.sh
```

### Test Individual Commands
```bash
./tests/test_individual_command.sh status
./tests/test_individual_command.sh takeoff
./tests/test_individual_command.sh move_forward
```

### System Health Check
```bash
./tests/validate_fixes.sh
./tests/quick_test.sh
```

## 📋 Available Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `get_status` | - | Get current drone status |
| `takeoff` | `altitude` | Launch drone to specified altitude |
| `land` | - | Safe landing sequence |
| `hover` | - | Maintain current position |
| `move_relative` | `x`, `y`, `z` | Move relative to current position |
| `move_to_position` | `x`, `y`, `z` | Move to absolute position |
| `rotate` | `angle` | Rotate by angle in degrees |
| `set_altitude` | `altitude` | Set specific altitude |
| `get_sensor_data` | - | Get all sensor readings |
| `emergency_stop` | - | Emergency stop and land |
| `reset_position` | - | Reset to origin position |

## 🏗️ Project Structure

```
crazyflie-webots-mcp/
├── README.md                        # This file
├── crazyflie_mcp_standalone.py      # Main MCP server
├── run.sh                           # System launcher
├── requirements.txt                 # Python dependencies
├── controllers/
│   └── mcp_simple/                  # Webots controller
├── worlds/                          # Webots world files
├── data/
│   └── Crazyflie/
│       ├── commands.json            # Input commands
│       └── status.json              # System responses
├── logs/                            # System logs
├── config/
│   └── settings.yaml                # Configuration
└── tests/                           # Testing scripts
    ├── test_all_commands.sh         # Comprehensive testing
    ├── test_individual_command.sh   # Individual command testing
    ├── validate_fixes.sh            # System validation
    └── quick_test.sh                # Quick health check
```

## 🔧 Configuration

### Run Modes
- **GUI Mode**: `bash run.sh --gui` (default)
- **Headless Mode**: `bash run.sh --headless` (optimized for automation)
- **Server Only**: `bash run.sh --server-only` (MCP server without Webots)

### Settings
Edit `config/settings.yaml` to customize:
- Flight parameters (altitude limits, velocities)
- Communication intervals
- Logging levels

## 📝 Logs

- **MCP Server**: `logs/mcp_server.log`
- **Webots Controller**: `logs/controller.log`
- **System**: `logs/webots_simulation.log`

## 🎯 Features

- ✅ Complete MCP protocol implementation
- ✅ File-based command communication
- ✅ Real-time status monitoring
- ✅ Comprehensive error handling
- ✅ Automated testing framework
- ✅ Headless mode optimization
- ✅ Production-ready stability

## 🚧 Development

### Adding New Commands
1. Add tool definition in `crazyflie_mcp_standalone.py`
2. Implement handler function
3. Update command mapping in `handle_command()`
4. Add test case in `tests/test_all_commands.sh`

### Debugging
- Check logs in `logs/` directory
- Use `tests/validate_fixes.sh` for system health
- Run individual tests for specific commands

## 📄 License

MIT License

---

**Status**: Production Ready ✅  
**Last Updated**: August 2025  
**Version**: 1.0.0  
**Structure**: Clean & Organized 🧹
