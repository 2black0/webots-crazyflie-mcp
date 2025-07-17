"""
Контроллер для робота NAO в Webots с интеграцией MCP сервера.

Этот контроллер:
1. Управляет роботом в Webots
2. Запускает MCP сервер в отдельном потоке
3. Обменивается данными с MCP сервером через файлы
4. Валидирует позиции моторов для безопасного управления
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

# --- Диапазоны позиций моторов NAO (в радианах) ---
MOTOR_LIMITS = {
    # Голова
    "HeadYaw": (-2.0857, 2.0857),      # ±119.5°
    "HeadPitch": (-0.6720, 0.5149),    # -38.5° to 29.5°

    # Плечи
    "LShoulderPitch": (-2.0857, 2.0857),  # ±119.5°
    "RShoulderPitch": (-2.0857, 2.0857),  # ±119.5°
    "LShoulderRoll": (-0.3142, 1.3265),   # -18° to 76°
    "RShoulderRoll": (-1.3265, 0.3142),   # -76° to 18°

    # Локти
    "LElbowYaw": (-2.0857, 2.0857),    # ±119.5°
    "RElbowYaw": (-2.0857, 2.0857),    # ±119.5°
    "LElbowRoll": (-1.5446, -0.0349),  # -88.5° to -2°
    "RElbowRoll": (0.0349, 1.5446),    # 2° to 88.5°

    # Запястья
    "LWristYaw": (-1.8238, 1.8238),    # ±104.5°
    "RWristYaw": (-1.8238, 1.8238),    # ±104.5°

    # Бедра
    "LHipYawPitch": (-1.145303, 0.740810),  # -65.62° to 42.44°
    "RHipYawPitch": (-1.145303, 0.740810),  # -65.62° to 42.44°
    "LHipRoll": (-0.379472, 0.790477),      # -21.74° to 45.29°
    "RHipRoll": (-0.790477, 0.379472),      # -45.29° to 21.74°
    "LHipPitch": (-1.773912, 0.484090),     # -101.63° to 27.73°
    "RHipPitch": (-1.773912, 0.484090),     # -101.63° to 27.73°

    # Колени
    "LKneePitch": (-0.092346, 2.112528),    # -5.29° to 121.04°
    "RKneePitch": (-0.092346, 2.112528),    # -5.29° to 121.04°

    # Лодыжки
    "LAnklePitch": (-1.189516, 0.922747),   # -68.15° to 52.86°
    "RAnklePitch": (-1.189516, 0.922747),   # -68.15° to 52.86°
    "LAnkleRoll": (-0.397880, 0.769001),    # -22.79° to 44.06°
    "RAnkleRoll": (-0.769001, 0.397880),    # -44.06° to 22.79°
}

# --- Инициализация робота ---
robot = Robot()
timestep = int(robot.getBasicTimeStep())

# --- Глобальные переменные ---
robot_state = {
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

# --- Инициализация светодиодов ---
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
    print("✅ Все светодиоды найдены")
except Exception as e:
    leds_found = False
    print(f"❌ Ошибка инициализации светодиодов: {e}")


# --- Функции валидации ---
def validate_motor_position(motor_name, position):
    """
    Валидирует позицию мотора согласно его физическим ограничениям.

    Args:
        motor_name (str): Имя мотора
        position (float): Целевая позиция в радианах

    Returns:
        tuple: (validated_position, is_valid, warning_message)
    """
    if motor_name not in MOTOR_LIMITS:
        return position, False, f"Неизвестный мотор: {motor_name}"

    min_pos, max_pos = MOTOR_LIMITS[motor_name]

    if min_pos <= position <= max_pos:
        return position, True, None

    # Ограничиваем позицию допустимыми пределами
    clamped_position = max(min_pos, min(max_pos, position))

    warning = (f"Позиция мотора {motor_name} ({position:.3f} рад = {math.degrees(position):.1f}°) "
              f"выходит за пределы [{min_pos:.3f}, {max_pos:.3f}] рад "
              f"[{math.degrees(min_pos):.1f}°, {math.degrees(max_pos):.1f}°]. "
              f"Ограничена до {clamped_position:.3f} рад ({math.degrees(clamped_position):.1f}°)")

    return clamped_position, False, warning

def validate_motor_positions(positions_dict):
    """
    Валидирует словарь позиций моторов.

    Args:
        positions_dict (dict): Словарь {motor_name: position}

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
    Безопасно устанавливает позицию мотора с валидацией.

    Args:
        motor_name (str): Имя мотора
        position (float): Целевая позиция в радианах

    Returns:
        bool: True если позиция была установлена успешно
    """
    if not motors_found or motor_name not in motors:
        print(f"❌ Мотор {motor_name} не найден")
        return False

    validated_pos, is_valid, warning = validate_motor_position(motor_name, position)

    if warning:
        print(f"⚠️ {warning}")

    try:
        motors[motor_name].setPosition(validated_pos)
        return True
    except Exception as e:
        print(f"❌ Ошибка установки позиции мотора {motor_name}: {e}")
        return False

# --- Функции управления ---
def set_initial_pose():
    """Устанавливает исходную позицию робота с валидацией."""
    if not motors_found:
        return

    # Безопасные начальные позиции
    initial_positions = {
        "HeadYaw": 0.0,
        "HeadPitch": 0.0,
        "LShoulderPitch": 0.0,
        "RShoulderPitch": 0.0,
        "LShoulderRoll": 0.0,
        "RShoulderRoll": 0.0,
        "LElbowYaw": 0.0,
        "RElbowYaw": 0.0,
        "LElbowRoll": -0.5,  # Слегка согнутые локти
        "RElbowRoll": 0.5,   # Слегка согнутые локти
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

    print("✅ Исходная позиция установлена с валидацией")

def load_motions():
    """Загружает все файлы анимации из папки motions."""
    global motions
    motions_dir = ROBOT_DIR / "motions"
    for motion_file in motions_dir.glob("*.motion"):
        name = motion_file.stem
        motions[name] = Motion(str(motion_file))
    print(f"✅ Загружено {len(motions)} анимаций.")

def get_motion_first_pose(motion_path):
    """Читает первую позу из файла .motion с валидацией."""
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

                    # Валидируем позиции из файла анимации
                    validated_pose, warnings = validate_motor_positions(pose_data)

                    if warnings:
                        print(f"⚠️ Предупреждения для анимации {motion_path.name}:")
                        for warning in warnings:
                            print(f"   {warning}")

                    return validated_pose
    except Exception as e:
        print(f"❌ Ошибка чтения первой позы из {motion_path}: {e}")
    return None

def start_motion(motion_name):
    """Плавно переходит в начальную позу и начинает анимацию."""
    global robot_state
    if robot_state['current_motion'] and not robot_state['current_motion'].isOver():
        robot_state['current_motion'].stop()
        print("⏹️ Предыдущая анимация остановлена")

    motion = motions.get(motion_name)
    if not motion:
        print(f"❌ Анимация '{motion_name}' не найдена в загруженных.")
        robot_state['current_motion'] = None
        return

    motion_path = ROBOT_DIR / "motions" / (motion_name + ".motion")
    first_pose = get_motion_first_pose(motion_path)

    if first_pose:
        print("🔄 Плавный переход к первой позе с валидацией")
        transition_duration = 1.0  # Длительность перехода в секундах
        start_time = robot.getTime()
        current_positions = {}

        # Получаем текущие позиции с валидацией
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
        print("✅ Переход к первой позе завершен")

    # --- Воспроизведение основной анимации ---
    try:
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
    """Обрабатывает команды от MCP сервера с валидацией."""
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

                success_yaw = set_motor_position_safe("HeadYaw", yaw)
                success_pitch = set_motor_position_safe("HeadPitch", pitch)

                if success_yaw and success_pitch:
                    print(f"✅ Голова установлена: yaw={yaw:.3f} рад ({math.degrees(yaw):.1f}°), "
                          f"pitch={pitch:.3f} рад ({math.degrees(pitch):.1f}°)")

        elif action == "reset_pose":
            set_initial_pose()

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

        elif action == "set_leds":
            if leds_found:
                color = command.get('color', 0)
                for led_name, led in leds.items():
                    try:
                        led.set(color)
                    except Exception as e:
                        print(f"❌ Ошибка установки цвета для {led_name}: {e}")
                print(f"✅ Установлен цвет светодиодов: {hex(color)}")
            else:
                print("❌ Светодиоды не найдены, невозможно установить цвет")

        elif action == "validate_position":
            # Новая команда для проверки валидности позиции
            motor_name = command.get("motor_name")
            position = command.get("position", 0.0)

            if motor_name:
                validated_pos, is_valid, warning = validate_motor_position(motor_name, position)
                print(f"🔍 Валидация {motor_name}: {position:.3f} рад ({math.degrees(position):.1f}°)")
                if is_valid:
                    print(f"✅ Позиция валидна")
                else:
                    print(f"⚠️ {warning}")
            else:
                print("❌ Команда 'validate_position' не содержит 'motor_name'")

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
            print(f"❌ Ошибка получения позиций моторов: {e}")

    # Формируем статус
    status_data = {
        "timestamp": current_time,
        "webots_connected": True,
        "head_position": head_position,
        "arm_positions": arm_positions,
        "walking_active": robot_state['walking_active'],
        "last_image_timestamp": robot_state.get('last_image_timestamp', 0),
        "motor_limits": {name: {"min": limits[0], "max": limits[1]} for name, limits in MOTOR_LIMITS.items()}
    }

    # Записываем статус в файл
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Ошибка записи статуса: {e}")

# --- Основной цикл ---
if __name__ == "__main__":
    print("🔧 Инициализация с валидацией позиций моторов...")
    print(f"📊 Загружено {len(MOTOR_LIMITS)} диапазонов позиций моторов")

    set_initial_pose()
    load_motions()

    print("🚀 Контроллер робота запущен. Ожидание команд...")

    # Основной цикл симуляции
    while robot.step(timestep) != -1:
        process_commands()
        update_motion()
        update_status()

    print("🚪 Контроллер робота завершает работу.")