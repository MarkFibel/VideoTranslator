"""
Скрипт для проверки готовности тестового окружения.
Проверяет установку зависимостей и доступность RabbitMQ.

Использование:
    python src/tests/check_environment.py
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Проверка версии Python."""
    print("🔍 Проверка версии Python...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (требуется >= 3.8)")
        return False


def check_package(package_name):
    """Проверка установки пакета."""
    try:
        __import__(package_name.replace("-", "_"))
        return True
    except ImportError:
        return False


def check_dependencies():
    """Проверка установки необходимых зависимостей."""
    print("\n🔍 Проверка зависимостей...")
    
    required_packages = [
        "pytest",
        "pytest_asyncio",
        "aio_pika",
        "fastapi",
        "jsonrpcserver",
        "pydantic",
        "aiofiles"
    ]
    
    all_ok = True
    for package in required_packages:
        if check_package(package):
            print(f"   ✅ {package}")
        else:
            print(f"   ❌ {package} (не установлен)")
            all_ok = False
    
    return all_ok


def check_rabbitmq():
    """Проверка доступности RabbitMQ."""
    print("\n🔍 Проверка RabbitMQ...")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 5672))
        sock.close()
        
        if result == 0:
            print("   ✅ RabbitMQ доступен на localhost:5672")
            return True
        else:
            print("   ❌ RabbitMQ недоступен на localhost:5672")
            print("      Запустите: docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка проверки RabbitMQ: {e}")
        return False


def check_project_structure():
    """Проверка структуры проекта."""
    print("\n🔍 Проверка структуры проекта...")
    
    required_paths = [
        "src/services/base_service.py",
        "src/services/test_service.py",
        "src/transport/rabbitmq/producer.py",
        "src/transport/rabbitmq/consumer.py",
        "src/transport/json_rpc/dispatcher.py",
        "src/config/rabbitmq_config.py",
        "src/tests/conftest.py",
        "src/tests/test_rabbitmq_integration.py",
        "src/tests/test_rpc_service.py",
        "src/tests/test_rabbitmq_connection.py"
    ]
    
    all_ok = True
    root = Path(__file__).parent.parent.parent
    
    for path_str in required_paths:
        path = root / path_str
        if path.exists():
            print(f"   ✅ {path_str}")
        else:
            print(f"   ❌ {path_str} (не найден)")
            all_ok = False
    
    return all_ok


def check_env_file():
    """Проверка файла конфигурации."""
    print("\n🔍 Проверка конфигурации...")
    
    root = Path(__file__).parent.parent.parent
    env_file = root / ".env"
    
    if env_file.exists():
        print(f"   ✅ .env файл найден")
        return True
    else:
        print(f"   ⚠️  .env файл не найден (будут использованы значения по умолчанию)")
        return True  # Не критично


def check_log_directory():
    """Проверка директории для логов."""
    print("\n🔍 Проверка директории логов...")
    
    root = Path(__file__).parent.parent.parent
    log_dir = root / "var" / "log"
    
    if log_dir.exists():
        print(f"   ✅ Директория логов существует: {log_dir}")
    else:
        print(f"   ⚠️  Директория логов не существует: {log_dir}")
        print(f"      Попытка создания...")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Директория логов создана")
        except Exception as e:
            print(f"   ❌ Ошибка создания директории: {e}")
            return False
    
    return True


def print_summary(checks):
    """Вывод итоговой сводки."""
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 60)
    
    all_passed = all(checks.values())
    
    for check_name, result in checks.items():
        status = "✅ ПРОЙДЕНО" if result else "❌ НЕ ПРОЙДЕНО"
        print(f"{status}: {check_name}")
    
    print("=" * 60)
    
    if all_passed:
        print("✅ Окружение готово для тестирования!")
        print("\nЗапустите тесты:")
        print("  pytest src/tests/ -v")
    else:
        print("❌ Требуются дополнительные действия:")
        if not checks["Зависимости"]:
            print("  1. Установите зависимости: pip install -r requirements.txt")
        if not checks["RabbitMQ"]:
            print("  2. Запустите RabbitMQ: docker run -d --name rabbitmq -p 5672:5672 rabbitmq:3")
        if not checks["Структура проекта"]:
            print("  3. Проверьте целостность файлов проекта")
    
    print()
    return all_passed


def main():
    """Главная функция проверки окружения."""
    print("=" * 60)
    print("🧪 ПРОВЕРКА ТЕСТОВОГО ОКРУЖЕНИЯ")
    print("=" * 60)
    
    checks = {
        "Python версия": check_python_version(),
        "Зависимости": check_dependencies(),
        "RabbitMQ": check_rabbitmq(),
        "Структура проекта": check_project_structure(),
        "Конфигурация": check_env_file(),
        "Директория логов": check_log_directory()
    }
    
    return print_summary(checks)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
