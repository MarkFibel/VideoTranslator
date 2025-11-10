"""
Скрипт для тестирования JSON-RPC диспетчера.
Демонстрирует работу автообнаружения сервисов и обработки RPC запросов.
"""

import json
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.transport.json_rpc.dispatcher import JSONRPCDispatcher

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_dispatcher():
    """Тестирует работу JSON-RPC диспетчера"""
    
    print("=" * 80)
    print("JSON-RPC Dispatcher Test")
    print("=" * 80)
    
    # Инициализация диспетчера
    print("\n[1] Initializing dispatcher...")
    dispatcher = JSONRPCDispatcher()
    
    # Получение списка зарегистрированных методов
    print("\n[2] Registered RPC methods:")
    methods = dispatcher.get_registered_methods()
    for method in methods:
        print(f"  - {method}")
    
    if not methods:
        print("  No methods registered!")
        return
    
    # Тест 1: Успешный вызов
    print("\n[3] Test 1: Valid RPC request")
    request_1 = {
        "jsonrpc": "2.0",
        "method": "test.execute",
        "params": {
            "data": {
                "message": "Hello from test script!",
                "timestamp": "2025-10-20T12:00:00"
            }
        },
        "id": 1
    }
    
    print(f"Request: {json.dumps(request_1, indent=2)}")
    
    try:
        response_1 = dispatcher.handle_request(json.dumps(request_1))
        print(f"Response: {response_1}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Тест 2: Вызов с другими данными
    print("\n[4] Test 2: Another valid request")
    request_2 = {
        "jsonrpc": "2.0",
        "method": "test.execute",
        "params": {
            "data": {
                "message": "Testing JSON-RPC implementation",
                "test_id": 42
            }
        },
        "id": 2
    }
    
    print(f"Request: {json.dumps(request_2, indent=2)}")
    
    try:
        response_2 = dispatcher.handle_request(json.dumps(request_2))
        print(f"Response: {response_2}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Тест 3: Вызов несуществующего метода
    print("\n[5] Test 3: Invalid method request")
    request_3 = {
        "jsonrpc": "2.0",
        "method": "nonexistent.execute",
        "params": {
            "data": {}
        },
        "id": 3
    }
    
    print(f"Request: {json.dumps(request_3, indent=2)}")
    
    try:
        response_3 = dispatcher.handle_request(json.dumps(request_3))
        print(f"Response: {response_3}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Тест 4: Некорректный JSON
    print("\n[6] Test 4: Invalid JSON request")
    request_4 = "{ invalid json }"
    
    print(f"Request: {request_4}")
    
    try:
        response_4 = dispatcher.handle_request(request_4)
        print(f"Response: {response_4}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 80)
    print("Tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_dispatcher()
