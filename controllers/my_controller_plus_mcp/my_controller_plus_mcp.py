"""
Контроллер для робота NAO в Webots с интеграцией MCP сервера.

Этот контроллер:
1. Управляет роботом в Webots
2. Запускает MCP сервер в отдельном потоке
3. Обменивается данными с MCP сервером через файлы
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

# --- Пути для обмена данными ---
CONTROLLER_DIR = Path(__file__).parent
ROBOT_DIR = CONTROLLER_DIR.parent.parent
DATA_DIR = ROBOT_DIR / "data"
COMMANDS_FILE = DATA_DIR / "commands.json"
STATUS_FILE = DATA_DIR / "status.json"

# Создаем директорию для данных
DATA_DIR.mkdir(exist_ok=True)

# Очищаем файл команд при запуске контроллера
if COMMANDS_FILE.exists():
    try:
        os.remove(COMMANDS_FILE)
        print("✅ Старый файл команд очищен при запуске.")
    except OSError as e:
        print(f"❌ Ошибка очистки файла команд при запуске: {e}")

# --- Инициализация робота ---
robot = Robot()
timestep = int(robot.getBasicTimeStep())

# --- Глобальные переменные ---
robot_state = {
    "head_scan_active": False,
    "head_scan_amplitude": 1.0,
    "head_scan_frequency": 0.5,
    "walking_active": False,
    "last_command_time": 0,
    "current_motion": None,
    "last_image_timestamp": 0
}
motions = {}

# --- Инициализация моторов ---
motors = {}
motor_names = [
    "HeadYaw", "HeadPitch",
    "LShoulderPitch", "RShoulderPitch",
    "LShoulderRoll", "RShoulderRoll",
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
    print("✅ Все моторы найдены")
except Exception as e:
    motors_found = False
    print(f"❌ Ошибка инициализации моторов: {e}")


# --- Инициализация камеры ---
camera = None
camera_found = True
try:
    camera = robot.getDevice("CameraTop")
    if camera:
        camera.enable(timestep)
        print("✅ Камера найдена и включена")
    else:
        camera_found = False
        print("❌ Камера 'CameraTop' не найдена")
except Exception as e:
    camera_found = False
    print(f"❌ Ошибка инициализации камеры: {e}")


# --- Функции управления ---
def set_initial_pose():
    """Устанавливает исходную позицию робота."""
    if not motors_found:
        return

    motors["HeadYaw"].setPosition(0.0)
    motors["HeadPitch"].setPosition(0.0)
    motors["LShoulderPitch"].setPosition(1.5)
    motors["RShoulderPitch"].setPosition(1.5)
    motors["LShoulderRoll"].setPosition(0.0)
    motors["RShoulderRoll"].setPosition(0.0)
    motors["LHipYawPitch"].setPosition(0.0)
    motors["RHipYawPitch"].setPosition(0.0)
    motors["LHipRoll"].setPosition(0.0)
    motors["RHipRoll"].setPosition(0.0)
    motors["LHipPitch"].setPosition(0.0)
    motors["RHipPitch"].setPosition(0.0)
    motors["LKneePitch"].setPosition(0.0)
    motors["RKneePitch"].setPosition(0.0)
    motors["LAnklePitch"].setPosition(0.0)
    motors["RAnklePitch"].setPosition(0.0)
    motors["LAnkleRoll"].setPosition(0.0)
    motors["RAnkleRoll"].setPosition(0.0)

    print("✅ Исходная позиция установлена")

def load_motions():
    """Загружает все файлы анимации из папки motions."""
    global motions
    motions_dir = ROBOT_DIR / "motions"
    for motion_file in motions_dir.glob("*.motion"):
        name = motion_file.stem
        motions[name] = Motion(str(motion_file))
    print(f"✅ Загружено {len(motions)} анимаций.")

def start_motion(motion_name):
    """Начинает воспроизведение файла анимации."""
    global robot_state
    # Останавливаем текущую анимацию, если она есть
    if robot_state['current_motion'] and not robot_state['current_motion'].isOver():
        robot_state['current_motion'].stop()
        print("⏹️ Предыдущая анимация остановлена")

    motion = motions.get(motion_name)
    if not motion:
        print(f"❌ Анимация '{motion_name}' не найдена в загруженных.")
        robot_state['current_motion'] = None
        return

    try:
        duration = motion.getDuration()
        print(f"⏱️ Длительность анимации '{motion_name}': {duration:.2f} мс")
        motion.play()
        robot_state['current_motion'] = motion
        print(f"▶️ Воспроизведение анимации: {motion_name}")
    except Exception as e:
        print(f"❌ Ошибка запуска анимации {motion_name}: {e}")
        robot_state['current_motion'] = None

def update_motion():
    """Проверяет и обновляет статус текущей анимации."""
    global robot_state
    if robot_state['current_motion'] and robot_state['current_motion'].isOver():
        print(f"✅ Анимация завершена")
        robot_state['current_motion'] = None

def process_commands():
    """Обрабатывает команды от MCP сервера."""
    # Блокировать команды во время анимации
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
                motors["HeadYaw"].setPosition(yaw)
                motors["HeadPitch"].setPosition(pitch)
                print(f"✅ Голова установлена: yaw={yaw:.2f}, pitch={pitch:.2f}")

        elif action == "set_arm_position":
            if motors_found:
                arm = command.get('arm', 'left')
                shoulder_pitch = command.get('shoulder_pitch', 1.5)
                shoulder_roll = command.get('shoulder_roll', 0.0)

                if arm == 'left':
                    motors["LShoulderPitch"].setPosition(shoulder_pitch)
                    motors["LShoulderRoll"].setPosition(shoulder_roll)
                elif arm == 'right':
                    motors["RShoulderPitch"].setPosition(shoulder_pitch)
                    motors["RShoulderRoll"].setPosition(shoulder_roll)

                print(f"✅ Рука {arm} установлена: pitch={shoulder_pitch:.2f}, roll={shoulder_roll:.2f}")

        elif action == "start_head_scan":
            robot_state['head_scan_active'] = True
            print("✅ Сканирование головой включено")

        elif action == "stop_head_scan":
            robot_state['head_scan_active'] = False
            if motors_found:
                motors["HeadYaw"].setPosition(0.0)
            print("✅ Сканирование головой выключено")

        elif action == "reset_pose":
            set_initial_pose()
            robot_state['head_scan_active'] = False

        elif action == "play_motion":
            motion_name = command.get("motion_name")
            if motion_name:
                start_motion(motion_name)
            else:
                print("❌ Команда 'play_motion' не содержит 'motion_name'")
        elif action == "get_camera_image":
            if camera_found and camera:
                image_path = DATA_DIR / "camera_image.jpg"
                camera.saveImage(str(image_path), 100)
                robot_state['last_image_timestamp'] = time.time()
                print(f"✅ Изображение сохранено в {image_path}")
            else:
                print("❌ Камера не найдена, невозможно получить изображение")

    except json.JSONDecodeError:
        # Ожидаемая ошибка, если файл пуст или некорректен
        pass
    except Exception as e:
        print(f"❌ Ошибка обработки команды: {e}")

def update_status():
    """Обновляет статус для MCP сервера."""
    current_time = time.time()

    # Получаем текущие позиции моторов
    head_position = {"yaw": 0.0, "pitch": 0.0}
    arm_positions = {
        "left_shoulder_pitch": 1.5,
        "right_shoulder_pitch": 1.5,
        "left_shoulder_roll": 0.0,
        "right_shoulder_roll": 0.0
    }

    if motors_found:
        try:
            head_position["yaw"] = motors["HeadYaw"].getTargetPosition()
            head_position["pitch"] = motors["HeadPitch"].getTargetPosition()
            arm_positions["left_shoulder_pitch"] = motors["LShoulderPitch"].getTargetPosition()
            arm_positions["right_shoulder_pitch"] = motors["RShoulderPitch"].getTargetPosition()
            arm_positions["left_shoulder_roll"] = motors["LShoulderRoll"].getTargetPosition()
            arm_positions["right_shoulder_roll"] = motors["RShoulderRoll"].getTargetPosition()
        except Exception as e:
            print(f"❌ Ошибка получения позиций моторов: {e}")

    # Формируем статус
    status_data = {
        "timestamp": current_time,
        "webots_connected": True,
        "head_position": head_position,
        "arm_positions": arm_positions,
        "walking_active": robot_state['walking_active'],
        "head_scan_active": robot_state['head_scan_active'],
        "last_image_timestamp": robot_state.get('last_image_timestamp', 0)
    }

    # Записываем статус в файл
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Ошибка записи статуса: {e}")

# --- Основной цикл ---
if __name__ == "__main__":
    set_initial_pose()
    load_motions()

    print("🚀 Контроллер робота запущен. Ожидание команд...")

    # Основной цикл симуляции
    while robot.step(timestep) != -1:
        process_commands()
        update_status()

    print("🚪 Контроллер робота завершает работу.")
