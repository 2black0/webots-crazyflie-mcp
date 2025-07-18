import asyncio
import json
import os
import sys
from typing import Any, Dict, List

# Добавляем путь к библиотеке MCP в системный путь
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'libraries')))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("[ERROR] MCP SDK not found.")
    print('Please make sure the mcp library is in the "libraries" folder')
    sys.exit(1)


class WebotsClient:
    """
    Webots MCP Client - адаптация успешного паттерна из Algolia клиента
    """

    def __init__(self):
        self.session = None
        self.tools = []
        self._mcp_process = None
        self._client_session = None

    async def __aenter__(self):
        """Асинхронный вход в контекстный менеджер."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["webots_mcp_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        try:
            print("[INFO] Starting Webots MCP server...")
            self._mcp_process = stdio_client(server_params)
            read, write = await self._mcp_process.__aenter__()

            self._client_session = ClientSession(read, write)
            self.session = await self._client_session.__aenter__()

            self.tools = (await self.session.list_tools()).tools
            print(
                f"[INFO] Webots MCP Client started successfully. Available tools: {[tool.name for tool in self.tools]}")

            return self

        except FileNotFoundError:
            print(f"[FATAL] Could not find '{sys.executable}' or 'webots_mcp_server.py'.")
            await self.__aexit__(None, None, None)
            sys.exit(1)
        except Exception as e:
            print(f"[FATAL] Failed to start MCP server: {e}")
            await self.__aexit__(None, None, None)
            sys.exit(1)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        if self._client_session:
            await self._client_session.__aexit__(exc_type, exc_val, exc_tb)
        if self._mcp_process:
            await self._mcp_process.__aexit__(exc_type, exc_val, exc_tb)
        print("[INFO] Connection to Webots MCP server closed.")

    async def call_tool(self, tool_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Универсальный метод для вызова любого инструмента.
        """
        if not self.session:
            return {"status": "error", "message": "Client is not running."}

        try:
            print(f"[INFO] Calling tool: {tool_name} with parameters: {parameters}")
            result = await self.session.call_tool(tool_name, arguments=parameters or {})

            if result and hasattr(result, 'content') and result.content:
                content_text = result.content[0].text
                try:
                    parsed_data = json.loads(content_text)
                    return {"status": "success", "data": parsed_data}
                except json.JSONDecodeError:
                    return {"status": "success", "data": content_text}
            elif result and result.tool_error:
                return {"status": "error", "message": f"Tool error: {result.tool_error}"}
            else:
                return {"status": "success", "data": "Tool call successful with no content returned."}

        except Exception as e:
            return {"status": "error", "message": f"Error calling tool '{tool_name}': {e}"}

    async def get_robot_status(self) -> Dict[str, Any]:
        """
        Получает статус робота через MCP инструмент.
        """
        return await self.call_tool('get_robot_status')


async def run_test():
    """
    Основная функция тестирования с использованием контекстного менеджера.
    """
    print("\n=== Webots MCP Test Client ===")
    print("Testing robot status retrieval...")

    try:
        async with WebotsClient() as client:
            # Тест 1: Получение статуса робота
            print("\n[TEST 1] Getting robot status...")
            status_result = await client.get_robot_status()

            if status_result.get('status') == 'success':
                print("\n--- [SUCCESS] Robot Status ---")
                print(json.dumps(status_result.get('data', {}), indent=2, ensure_ascii=False))
                print("-----------------------------")

                data = status_result.get('data', {})
                if 'robot_position' in data:
                    pos = data['robot_position']
                    print(f"[SUCCESS] Robot coordinates: x={pos.get('x')}, y={pos.get('y')}, z={pos.get('z')}")
                else:
                    print("[WARNING] 'robot_position' not found in status")
            else:
                print(f"[ERROR] Failed to get robot status: {status_result.get('message')}")

            # Тест 2: Список доступных инструментов
            tool_names = [tool.name for tool in client.tools]
            print(f"\n[TEST 2] Available tools: {tool_names}")
            print("[INFO] Other tools are not tested automatically as they might require parameters.")
            print("[INFO] Use interactive mode (-i) to test them manually.")

    except Exception as e:
        print(f"[CRITICAL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()


async def interactive_mode():
    """
    Интерактивный режим для тестирования различных команд с параметрами.
    """
    print("\n=== Interactive Webots MCP Test ===")
    print("Enter tool name, or 'exit' to quit.")
    print("You will be prompted for parameters in JSON format.")

    try:
        async with WebotsClient() as client:
            tool_names = [tool.name for tool in client.tools]
            print(f"\nAvailable tools: {tool_names}")

            while True:
                try:
                    tool_name = await asyncio.to_thread(input, "\nTool name > ")
                    if tool_name.lower() == 'exit':
                        break
                    if tool_name not in tool_names:
                        print(f"[ERROR] Tool '{tool_name}' not found. Available: {tool_names}")
                        continue

                    params_str = await asyncio.to_thread(input,
                                                         "Parameters (JSON, e.g., {\"key\": \"value\"}) or press Enter for none > ")
                    params = {}
                    if params_str:
                        try:
                            params = json.loads(params_str)
                        except json.JSONDecodeError as e:
                            print(f"[ERROR] Invalid JSON: {e}")
                            continue

                    result = await client.call_tool(tool_name, params)

                    print("\n--- Result ---")
                    if result.get('status') == 'success':
                        print(json.dumps(result.get('data', {}), indent=2, ensure_ascii=False))
                    else:
                        print(f"[ERROR] {result.get('message')}")
                    print("--------------")

                except (KeyboardInterrupt, EOFError):
                    break
                except Exception as e:
                    print(f"\n[ERROR] An unexpected error occurred: {e}")
                    continue

    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print("\n[INFO] Exiting interactive mode...")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Webots MCP Test Client')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run in interactive mode')
    args = parser.parse_args()

    try:
        if args.interactive:
            asyncio.run(interactive_mode())
        else:
            asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n[INFO] Test interrupted by user.")