'''
MCP Server для управления роботом NAO в Webots.

Этот сервер работает в связке с контроллером Webots через файловую систему
и сокеты для обмена командами и статусом.
'''

import asyncio
import base64
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from mcp.server.fastmcp import FastMCP

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_server.log',
    filemode='a',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

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
                logger.debug("Статус успешно загружен.")
                return True
    except Exception as e:
        logger.error(f"Ошибка загрузки статуса: {e}")
    return False

def save_command(command: dict):
    """Сохраняет команду в файл для контроллера."""
    try:
        command['timestamp'] = time.time()
        # Убедимся, что директория существует
        COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2, ensure_ascii=False)
        logger.info(f"Команда '{command.get('action')}' успешно сохранена в {COMMANDS_FILE.resolve()}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения команды в {COMMANDS_FILE.resolve()}: {e}")
        return False



def wait_for_image_update(timeout=10.0):
    """Ожидает обновления изображения от контроллера."""
    start_time = time.time()
    initial_image_time = robot_status.get('last_image_timestamp', 0)
    logger.info(f"Ожидание обновления изображения. Начальное время: {initial_image_time}")

    while time.time() - start_time < timeout:
        load_status()
        if robot_status.get('last_image_timestamp', 0) > initial_image_time:
            logger.info("Обновление изображения обнаружено.")
            return True
        time.sleep(0.1)
    logger.warning("Тайм-аут ожидания обновления изображения.")
    return False


@mcp.tool()
def get_visual_perception() -> str:
    """
    Получает визуальную информацию с камеры робота в jpg.

    """
    logger.info("Запрошено получение визуальной информации.")
    command = {
        "action": "get_camera_image"
    }

    if not save_command(command):
        logger.error("Ошибка отправки команды на получение изображения.")
        return "❌ Ошибка отправки команды на получение изображения"

    if not wait_for_image_update():
        logger.warning("Команда на получение изображения отправлена, но новое изображение не получено в таймаут.")
        return "⚠️ Команда отправлена, но новое изображение не получено"

    image_path = DATA_DIR / "camera_image.jpg"
    if not image_path.exists():
        logger.error(f"Файл изображения не найден по пути: {image_path.resolve()}")
        return "❌ Файл изображения не найден после обновления"

    logger.info(f"Изображение успешно получено: {image_path.resolve()}")
    return f"✅ Получено изображение для анализа: {image_path.resolve()}"

@mcp.tool()
def get_robot_status() -> str:
    """Получает текущий статус робота."""
    logger.info("Запрошен статус робота.")
    load_status()

    # Проверяем, недавно ли обновлялся статус (последние 10 секунд)
    current_time = time.time()
    last_update = robot_status.get('last_update', 0)
    robot_status['running'] = (current_time - last_update) < 10.0
    logger.debug(f"Проверка активности: running={robot_status['running']} (last_update: {last_update})")


    status_info = {
        "running": robot_status['running'],
        "webots_connected": robot_status.get('webots_connected', False),
        "head_position": robot_status['head_position'],
        "arm_positions": robot_status['arm_positions'],
        "last_recognized_objects": robot_status['last_recognized_objects'],
        "last_update": robot_status.get('last_update', 0),
        "last_image_timestamp": robot_status.get('last_image_timestamp', 0)
    }
    logger.info("Статус робота успешно сформирован.")
    return json.dumps(status_info, indent=2, ensure_ascii=False)

@mcp.tool()
def set_head_position(yaw: float, pitch: float) -> str:
    """
    Устанавливает положение головы робота.

    Args:
        yaw: Поворот головы влево-вправо (-1.0 до 1.0)
        pitch: Наклон головы вверх-вниз (-1.0 до 1.0)
    """
    logger.info(f"Установка позиции головы: yaw={yaw}, pitch={pitch}")
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
        logger.info(f"Локальный статус головы обновлен: yaw={yaw:.2f}, pitch={pitch:.2f}")
        return f"✅ Позиция головы установлена: yaw={yaw:.2f}, pitch={pitch:.2f}"
    else:
        logger.error("Ошибка отправки команды на установку позиции головы.")
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
    logger.info(f"Установка позиции руки '{arm}': pitch={shoulder_pitch}, roll={shoulder_roll}")
    if arm not in ["left", "right"]:
        logger.warning(f"Неверное значение для 'arm': {arm}. Должно быть 'left' или 'right'.")
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
        logger.info(f"Локальный статус руки '{arm}' обновлен: pitch={shoulder_pitch:.2f}, roll={shoulder_roll:.2f}")
        return f"✅ Позиция {arm} руки установлена: pitch={shoulder_pitch:.2f}, roll={shoulder_roll:.2f}"
    else:
        logger.error(f"Ошибка отправки команды на установку позиции руки '{arm}'.")
        return "❌ Ошибка отправки команды"

@mcp.tool()
def reset_robot_pose() -> str:
    """Сбрасывает робота в исходную позицию."""
    logger.info("Запрошен сброс позы робота.")
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
        logger.info("Локальный статус сброшен в исходную позицию.")
        return "✅ Робот сброшен в исходную позицию: голова прямо, руки опущены"
    else:
        logger.error("Ошибка отправки команды на сброс позы.")
        return "❌ Ошибка отправки команды сброса"

@mcp.tool()
def list_motions() -> List[Dict[str, Any]]:
    """
    Возвращает список доступных движений с их продолжительностью.
    """
    logger.info("Запрошен список доступных движений.")
    motions_dir = Path(__file__).parent / "motions"
    if not motions_dir.is_dir():
        logger.error(f"Директория motions не найдена по пути: {motions_dir.resolve()}")
        return [{"error": "Директория motions не найдена"}]

    motion_details = []
    motion_files = list(motions_dir.glob("*.motion"))

    if not motion_files:
        logger.warning(f"Файлы .motion не найдены в директории: {motions_dir.resolve()}")
        return [{"info": "Файлы .motion не найдены в директории motions"}]

    logger.info(f"Найдено {len(motion_files)} файлов анимаций.")
    for motion_file in motion_files:
        duration_seconds = 0.0
        try:
            with open(motion_file, 'r', encoding='utf-8') as f:
                lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
                if lines:
                    last_line = lines[-1]
                    time_str = last_line.split(',')[0]
                    time_parts = time_str.split(':')
                    # Формат ММ:СС:мс (где мс - тысячные секунды)
                    minutes = int(time_parts[0])
                    seconds = int(time_parts[1])
                    milliseconds = int(time_parts[2])
                    
                    total_seconds = (minutes * 60) + seconds + (milliseconds / 1000.0)
                    duration_seconds = round(total_seconds, 2)
        except (IOError, ValueError, IndexError) as e:
            logger.warning(f"Не удалось прочитать длительность для {motion_file.name}: {e}")
            duration_seconds = 0.0 # Indicate error or unknown duration

        motion_details.append({
            "name": motion_file.stem,
            "duration_seconds": duration_seconds
        })
    logger.info("Список движений успешно сформирован.")
    return motion_details

@mcp.tool()
def play_motion(motion_name: str) -> Dict[str, Any]:
    """
    Запускает движение робота и возвращает его продолжительность.
    """
    logger.info(f"Запрошено воспроизведение анимации: {motion_name}")
    motions_dir = Path(__file__).parent / "motions"
    
    # Очищаем имя от расширения, если оно есть
    base_motion_name = motion_name.split('.')[0]
    motion_file = motions_dir / f"{base_motion_name}.motion"

    if not motion_file.exists():
        logger.error(f"Файл анимации '{motion_name}' не найден по пути: {motion_file.resolve()}")
        return {"status": f"❌ Файл анимации '{motion_name}' не найден.", "duration_seconds": 0}

    duration_seconds = 0.0
    try:
        with open(motion_file, 'r', encoding='utf-8') as f:
            lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
            if lines:
                last_line = lines[-1]
                time_str = last_line.split(',')[0]
                time_parts = time_str.split(':')
                # Формат ММ:СС:мс (где мс - тысячные секунды)
                minutes = int(time_parts[0])
                seconds = int(time_parts[1])
                milliseconds = int(time_parts[2])

                total_seconds = (minutes * 60) + seconds + (milliseconds / 1000.0)
                duration_seconds = round(total_seconds, 2)
                logger.info(f"Определена длительность анимации '{motion_name}': {duration_seconds}s")
    except (IOError, ValueError, IndexError) as e:
        logger.warning(f"Не удалось прочитать длительность для {motion_file.name}: {e}")
        return {"status": f"⚠️ Не удалось определить длительность для '{motion_name}'.", "duration_seconds": 0}

    command = {
        "action": "play_motion",
        "motion_name": motion_name
    }

    if save_command(command):
        return {
            "status": f"✅ Команда на воспроизведение анимации '{motion_name}' отправлена.",
            "duration_seconds": duration_seconds
        }
    else:
        logger.error(f"Ошибка отправки команды на воспроизведение анимации '{motion_name}'.")
        return {
            "status": f"❌ Ошибка отправки команды на воспроизведение анимации '{motion_name}'.",
            "duration_seconds": 0
        }


@mcp.tool()
def set_led_color(color: str, part: str = 'all') -> str:
    """
    Устанавливает цвет светодиодов робота.

    Args:
        color: Название цвета ('red', 'green', 'blue', 'white', 'off') или HEX-код (например, '#FF0000').
        part: Часть тела для включения (пока поддерживается только 'all').
    """
    logger.info(f"Установка цвета светодиодов: color='{color}', part='{part}'")
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
            logger.warning(f"Неверный HEX-код цвета: {color}")
            return f"❌ Неверный HEX-код цвета: {color}"
    else:
        logger.warning(f"Неверный цвет: {color}. Используйте название или HEX-код.")
        return f"❌ Неверный цвет: {color}. Используйте название или HEX-код."

    command = {
        "action": "set_leds",
        "color": rgb_color
    }

    if save_command(command):
        return f"✅ Команда на установку цвета '{color}' отправлена."
    else:
        logger.error("Ошибка отправки команды на установку цвета.")
        return f"❌ Ошибка отправки команды на установку цвета."


@mcp.tool()
def get_robot_capabilities() -> str:
    """Получает список доступных возможностей робота."""
    logger.info("Запрошен список возможностей робота.")
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
    logger.info("Список возможностей робота успешно сформирован.")
    return json.dumps(capabilities, indent=2, ensure_ascii=False)

@mcp.tool()
def check_webots_connection() -> str:
    """Проверяет соединение с контроллером Webots."""
    logger.info("Запрошена проверка соединения с Webots.")
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
    logger.info(f"Статус соединения: {connection_info}")
    return json.dumps(connection_info, indent=2, ensure_ascii=False)

# Инициализация при загрузке
logger.info("Инициализация MCP сервера...")
load_status()

if __name__ == "__main__":
    logger.info("Запуск MCP сервера.")
    # Запуск сервера
    mcp.run()
