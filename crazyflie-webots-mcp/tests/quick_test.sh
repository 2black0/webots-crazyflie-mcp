#!/bin/bash
# Quick Manual Test for MCP Communication

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "🔧 Quick MCP Communication Test"
echo "================================"

# Start system in background
echo "Starting system..."
bash run.sh > tests/manual_test.log 2>&1 &
SYSTEM_PID=$!

echo "Waiting for startup (10 seconds)..."
sleep 10

# Check if running
if ! kill -0 $SYSTEM_PID 2>/dev/null; then
    echo "❌ System failed to start"
    cat manual_test.log
    exit 1
fi

echo "✅ System started (PID: $SYSTEM_PID)"

# Test basic communication
echo ""
echo "Testing status command..."
echo '{"action":"status"}' > data/Crazyflie/commands.json
sleep 3

if [[ -f "data/Crazyflie/status.json" ]]; then
    echo "✅ Response received:"
    cat data/Crazyflie/status.json
else
    echo "❌ No response"
fi

echo ""
echo "Testing takeoff command..."
echo '{"action":"takeoff"}' > data/Crazyflie/commands.json
sleep 3

if [[ -f "data/Crazyflie/status.json" ]]; then
    echo "✅ Response received:"
    cat data/Crazyflie/status.json
else
    echo "❌ No response"
fi

echo ""
echo "System logs:"
echo "=== MCP Server Log ==="
tail -5 logs/mcp_server.log 2>/dev/null || echo "No MCP log found"

echo ""
echo "=== Webots Log ==="
tail -5 logs/webots.log 2>/dev/null || echo "No Webots log found"

# Cleanup
echo ""
echo "Stopping system..."
kill $SYSTEM_PID 2>/dev/null
sleep 2
pkill -f "crazyflie_mcp_standalone.py" 2>/dev/null
pkill -f "webots.*complete_apartment.wbt" 2>/dev/null

rm -f manual_test.log
echo "✅ Test completed"
