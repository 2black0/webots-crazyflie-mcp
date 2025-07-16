import threading
import time
import os

# Импортируем сам сервер и КОНКРЕТНЫЕ функции, которые будем вызывать
from webots_mcp_server import mcp, COMMANDS_FILE, STATUS_FILE, \
    get_robot_status, set_head_position, reset_robot_pose

def run_server():
    """Функция для запуска MCP сервера в потоке."""
    print("[СЕРВЕР] Запуск MCP сервера...")
    mcp.run()

def run_test_commands():
    """Отправляет тестовые команды на сервер."""
    print("[КЛИЕНТ] Ожидание запуска сервера (2 секунды)...")
    time.sleep(2)

    # Вызываем функции напрямую, а не через mcp.tools
    print("\n[КЛИЕНТ] 1. Запрос статуса робота...")
    status_result = get_robot_status()
    print(f"[КЛИЕНТ] Ответ сервера: {status_result}")
    # Эта команда не создает command.json, поэтому файл еще не существует

    print("\n[КЛИЕНТ] 2. Установка позиции головы (yaw=0.5, pitch=-0.2)...")
    head_result = set_head_position(yaw=0.5, pitch=-0.2)
    print(f"[КЛИЕНТ] Ответ сервера: {head_result}")
    # Теперь файл должен быть создан
    print(f"[КЛИЕНТ] Файл {COMMANDS_FILE.name} существует: {COMMANDS_FILE.exists()}")

    print("\n[КЛИЕНТ] 3. Сброс позиции робота...")
    reset_result = reset_robot_pose()
    print(f"[КЛИЕНТ] Ответ сервера: {reset_result}")

    print("\n[КЛИЕНТ] Тестирование завершено.")


if __name__ == "__main__":
    # Запускаем сервер в фоновом потоке
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Запускаем тестовые команды
    run_test_commands()

    time.sleep(1)
