"""
MCP Server для управления роботом NAO в Webots.

Этот сервер работает в связке с контроллером Webots через файловую систему
и сокеты для обмена командами и статусом.
"""

import asyncio
import base64
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from mcp.server.fastmcp import FastMCP

# Создаем MCP сервер
mcp = FastMCP("Webots Robot Control Server")

# Пути для обмена данными с контроллером
DATA_DIR = Path(__file__).parent / "data"
COMMANDS_FILE = DATA_DIR / "commands.json"
STATUS_FILE = DATA_DIR / "status.json"

# Создаем директорию для данных
DATA_DIR.mkdir(exist_ok=True)

# Глобальные переменные для состояния
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
    "last_recognized_objects": [],
    "last_update": 0,
    "last_image_timestamp": 0
}

def load_status():
    """Загружает статус из файла."""
    global robot_status
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                robot_status.update(data)
                return True
    except Exception as e:
        print(f"Ошибка загрузки статуса: {e}")
    return False

def save_command(command: dict):
    """Сохраняет команду в файл для контроллера."""
    try:
        command['timestamp'] = time.time()
        # Убедимся, что директория существует
        COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2, ensure_ascii=False)
        print(f"[DEBUG] Команда успешно сохранена в {COMMANDS_FILE.resolve()}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка сохранения команды в {COMMANDS_FILE.resolve()}: {e}")
        return False



def wait_for_image_update(timeout=10.0):
    """Ожидает обновления изображения от контроллера."""
    start_time = time.time()
    initial_image_time = robot_status.get('last_image_timestamp', 0)

    while time.time() - start_time < timeout:
        load_status()
        if robot_status.get('last_image_timestamp', 0) > initial_image_time:
            return True
        time.sleep(0.1)
    return False


@mcp.tool()
def get_visual_perception() -> str:
    """
    Получает визуальную информацию с камеры робота.

    Returns:
        str: Абсолютный путь к файлу изображения для анализа.
    """
    command = {
        "action": "get_camera_image"
    }

    if not save_command(command):
        return "❌ Ошибка отправки команды на получение изображения"

    if not wait_for_image_update():
        return "⚠️ Команда отправлена, но новое изображение не получено"

    image_path = DATA_DIR / "camera_image.jpg"
    if not image_path.exists():
        return "❌ Файл изображения не найден после обновления"

    return f"✅ Получено изображение для анализа: {image_path.resolve()}"

@mcp.tool()
def get_robot_status() -> str:
    """Получает текущий статус робота."""
    load_status()

    # Проверяем, недавно ли обновлялся статус (последние 10 секунд)
    current_time = time.time()
    last_update = robot_status.get('last_update', 0)
    robot_status['running'] = (current_time - last_update) < 10.0

    status_info = {
        "running": robot_status['running'],
        "webots_connected": robot_status.get('webots_connected', False),
        "head_position": robot_status['head_position'],
        "arm_positions": robot_status['arm_positions'],
        "last_recognized_objects": robot_status['last_recognized_objects'],
        "last_update": robot_status.get('last_update', 0),
        "last_image_timestamp": robot_status.get('last_image_timestamp', 0)
    }

    return json.dumps(status_info, indent=2, ensure_ascii=False)

@mcp.tool()
def set_head_position(yaw: float, pitch: float) -> str:
    """
    Устанавливает положение головы робота.

    Args:
        yaw: Поворот головы влево-вправо (-1.0 до 1.0)
        pitch: Наклон головы вверх-вниз (-1.0 до 1.0)
    """
    # Ограничиваем значения
    yaw = max(-1.0, min(1.0, yaw))
    pitch = max(-1.0, min(1.0, pitch))

    command = {
        "action": "set_head_position",
        "yaw": yaw,
        "pitch": pitch
    }

    if save_command(command):
        # Обновляем локальное состояние
        robot_status["head_position"]["yaw"] = yaw
        robot_status["head_position"]["pitch"] = pitch

        return f"✅ Позиция головы установлена: yaw={yaw:.2f}, pitch={pitch:.2f}"
    else:
        return "❌ Ошибка отправки команды"

@mcp.tool()
def set_arm_position(arm: str, shoulder_pitch: float, shoulder_roll: float) -> str:
    """
    Устанавливает положение руки робота.

    Args:
        arm: 'left' или 'right'
        shoulder_pitch: Поднятие/опускание руки (0.0 до 2.0)
        shoulder_roll: Прижатие/отведение руки (-1.0 до 1.0)
    """
    if arm not in ["left", "right"]:
        return "❌ Неверное значение arm. Используйте 'left' или 'right'"

    # Ограничиваем значения
    shoulder_pitch = max(0.0, min(2.0, shoulder_pitch))
    shoulder_roll = max(-1.0, min(1.0, shoulder_roll))

    command = {
        "action": "set_arm_position",
        "arm": arm,
        "shoulder_pitch": shoulder_pitch,
        "shoulder_roll": shoulder_roll
    }

    if save_command(command):
        # Обновляем локальное состояние
        robot_status["arm_positions"][f"{arm}_shoulder_pitch"] = shoulder_pitch
        robot_status["arm_positions"][f"{arm}_shoulder_roll"] = shoulder_roll

        return f"✅ Позиция {arm} руки установлена: pitch={shoulder_pitch:.2f}, roll={shoulder_roll:.2f}"
    else:
        return "❌ Ошибка отправки команды"

@mcp.tool()
def reset_robot_pose() -> str:
    """Сбрасывает робота в исходную позицию."""
    command = {
        "action": "reset_pose"
    }

    if save_command(command):
        # Обновляем локальное состояние
        robot_status["head_position"]["yaw"] = 0.0
        robot_status["head_position"]["pitch"] = 0.0
        robot_status["arm_positions"]["left_shoulder_pitch"] = 1.5
        robot_status["arm_positions"]["right_shoulder_pitch"] = 1.5
        robot_status["arm_positions"]["left_shoulder_roll"] = 0.0
        robot_status["arm_positions"]["right_shoulder_roll"] = 0.0

        return "✅ Робот сброшен в исходную позицию: голова прямо, руки опущены"
    else:
        return "❌ Ошибка отправки команды сброса"

@mcp.tool()
def list_motions() -> List[str]:
    """Возвращает список доступных файлов анимации."""
    motions_dir = Path(__file__).parent / "motions"
    if not motions_dir.is_dir():
        return ["❌ Директория motions не найдена"]
    
    motion_files = [f.stem for f in motions_dir.glob("*.motion")]
    if not motion_files:
        return ["ℹ️ Файлы .motion не найдены в директории motions"]
        
    return motion_files

@mcp.tool()
def play_motion(motion_name: str) -> str:
    """Воспроизводит файл анимации из папки motions."""
    command = {
        "action": "play_motion",
        "motion_name": motion_name
    }

    if save_command(command):
        return f"✅ Команда на воспроизведение анимации '{motion_name}' отправлена."
    else:
        return f"❌ Ошибка отправки команды на воспроизведение анимации '{motion_name}'."


@mcp.tool()
def set_led_color(color: str, part: str = 'all') -> str:
    """
    Устанавливает цвет светодиодов робота.

    Args:
        color: Название цвета ('red', 'green', 'blue', 'white', 'off') или HEX-код (например, '#FF0000').
        part: Часть тела для включения (пока поддерживается только 'all').
    """
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
            return f"❌ Неверный HEX-код цвета: {color}"
    else:
        return f"❌ Неверный цвет: {color}. Используйте название или HEX-код."

    command = {
        "action": "set_leds",
        "color": rgb_color
    }

    if save_command(command):
        return f"✅ Команда на установку цвета '{color}' отправлена."
    else:
        return f"❌ Ошибка отправки команды на установку цвета."


@mcp.tool()
def get_robot_capabilities() -> str:
    """Получает список доступных возможностей робота."""
    capabilities = {
        "movement": {
            "head_yaw": {"min": -1.0, "max": 1.0, "description": "Поворот головы влево-вправо"},
            "head_pitch": {"min": -1.0, "max": 1.0, "description": "Наклон головы вверх-вниз"},
            "shoulder_pitch": {"min": 0.0, "max": 2.0, "description": "Поднятие/опускание руки"},
            "shoulder_roll": {"min": -1.0, "max": 1.0, "description": "Прижатие/отведение руки"}
        },
        "sensors": {
            "camera": {"description": "Камера  Webots"}
        },
        "actions": {
            "pose_reset": {"description": "Сброс в исходную позицию"}
        }
    }

    return json.dumps(capabilities, indent=2, ensure_ascii=False)

@mcp.tool()
def check_webots_connection() -> str:
    """Проверяет соединение с контроллером Webots."""
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

    return json.dumps(connection_info, indent=2, ensure_ascii=False)

# Ресурсы для Claude Desktop
@mcp.resource("robot://status")
def get_robot_status_resource() -> str:
    """Ресурс для получения текущего статуса робота."""
    return get_robot_status()

@mcp.resource("robot://objects")
def get_recognized_objects_resource() -> str:
    """Ресурс для получения списка распознанных объектов."""
    return get_recognized_objects()

@mcp.resource("robot://capabilities")
def get_robot_capabilities_resource() -> str:
    """Ресурс для получения возможностей робота."""
    return get_robot_capabilities()

@mcp.resource("robot://connection")
def check_webots_connection_resource() -> str:
    """Ресурс для проверки соединения с Webots."""
    return check_webots_connection()

# Инициализация при загрузке
load_status()

if __name__ == "__main__":
    # Запуск сервера
    mcp.run()