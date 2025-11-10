# Тесты RabbitMQ для VideoTranslator

Комплект тестов для проверки работы RabbitMQ RPC системы в проекте VideoTranslator.

## Структура тестов

```
src/tests/
├── __init__.py                      # Инициализация пакета тестов
├── conftest.py                      # Общие фикстуры для всех тестов
├── test_rabbitmq_integration.py     # Интеграционные тесты (Producer + Consumer + Service)
├── test_rabbitmq_connection.py      # Тесты транспортного уровня (ConnectionManager, Producer)
└── test_rpc_service.py              # Unit тесты сервисов (без RabbitMQ)
```

## Типы тестов

### 1. Unit тесты (`test_rpc_service.py`)
Тестируют отдельные компоненты изолированно:
- ✅ TestService - логика обработки данных
- ✅ ServiceLoader - обнаружение и регистрация сервисов
- ✅ JSONRPCDispatcher - обработка JSON-RPC запросов
- ✅ BaseService - базовая функциональность сервисов

**Не требуют RabbitMQ** - можно запускать без поднятого воркера.

### 2. Тесты подключения (`test_rabbitmq_connection.py`)
Тестируют транспортный уровень:
- ✅ ConnectionManager - подключение к RabbitMQ
- ✅ RPCProducer - отправка сообщений
- ✅ Конфигурация RabbitMQ
- ✅ Переподключение и устойчивость

**Требуют работающий RabbitMQ**, но не требуют воркера.

### 3. Интеграционные тесты (`test_rabbitmq_integration.py`)
Тестируют полный цикл работы системы:
- ✅ Успешные RPC вызовы
- ✅ Обработка различных типов данных
- ✅ Обработка ошибок (несуществующие методы)
- ✅ Множественные последовательные вызовы
- ✅ Параллельные вызовы
- ✅ Обработка таймаутов
- ✅ Передача больших данных
- ✅ Стабильность соединения

**Требуют работающий RabbitMQ И запущенный воркер**.

## Установка зависимостей

```powershell
# Установка всех зависимостей (включая pytest)
pip install -r requirements.txt

# Или только тестовые зависимости
pip install pytest pytest-asyncio
```

## Запуск RabbitMQ

Перед запуском интеграционных тестов убедитесь, что RabbitMQ запущен:

```powershell
# Docker (рекомендуется)
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Или используйте установленный RabbitMQ
# Windows: запустите RabbitMQ из Services или
rabbitmq-server

# Проверка доступности
# Откройте http://localhost:15672 (логин: guest, пароль: guest)
```

## Запуск тестов

### Все тесты сразу

```powershell
# Запустить все тесты
pytest src/tests/ -v

# С выводом логов в консоль
pytest src/tests/ -v -s

# С покрытием кода
pytest src/tests/ -v --cov=src --cov-report=html
```

### Unit тесты (без RabbitMQ)

```powershell
# Только unit тесты сервисов
pytest src/tests/test_rpc_service.py -v

# Конкретный тестовый класс
pytest src/tests/test_rpc_service.py::TestServiceUnit -v

# Конкретный тест
pytest src/tests/test_rpc_service.py::TestServiceUnit::test_service_initialization -v
```

### Тесты подключения (требуют RabbitMQ)

```powershell
# Все тесты подключения
pytest src/tests/test_rabbitmq_connection.py -v

# Только тесты ConnectionManager
pytest src/tests/test_rabbitmq_connection.py::TestConnectionManager -v
```

### Интеграционные тесты (требуют RabbitMQ + воркер)

**Важно:** Запустите воркер в отдельном терминале ДО запуска интеграционных тестов!

```powershell
# Терминал 1: Запуск воркера
python -m src.worker

# Терминал 2: Запуск интеграционных тестов
pytest src/tests/test_rabbitmq_integration.py -v

# Конкретный интеграционный тест
pytest src/tests/test_rabbitmq_integration.py::test_rpc_call_success -v

# Тест с выводом логов (для отладки)
pytest src/tests/test_rabbitmq_integration.py::test_rpc_call_success -v -s
```

## Пошаговая инструкция для полного тестирования

### Шаг 1: Установка зависимостей
```powershell
pip install -r requirements.txt
```

### Шаг 2: Запуск RabbitMQ
```powershell
# Docker
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Проверка
curl http://localhost:15672
```

### Шаг 3: Запуск unit тестов
```powershell
# Эти тесты не требуют RabbitMQ или воркера
pytest src/tests/test_rpc_service.py -v
```

### Шаг 4: Запуск тестов подключения
```powershell
# Требуют только RabbitMQ
pytest src/tests/test_rabbitmq_connection.py -v
```

### Шаг 5: Запуск воркера
```powershell
# Новый терминал - оставьте его работать
python -m src.worker
```

### Шаг 6: Запуск интеграционных тестов
```powershell
# В другом терминале
pytest src/tests/test_rabbitmq_integration.py -v
```

### Шаг 7: Запуск всех тестов
```powershell
# После успешного прохождения предыдущих шагов
pytest src/tests/ -v
```

## Примеры вывода

### Успешный запуск unit тестов
```
src/tests/test_rpc_service.py::TestServiceUnit::test_service_initialization PASSED
src/tests/test_rpc_service.py::TestServiceUnit::test_service_name PASSED
src/tests/test_rpc_service.py::TestServiceUnit::test_service_execute_with_message PASSED
...
======================== 25 passed in 0.15s ========================
```

### Успешный запуск интеграционных тестов
```
src/tests/test_rabbitmq_integration.py::test_rpc_call_success PASSED
src/tests/test_rabbitmq_integration.py::test_rpc_call_with_different_data PASSED
src/tests/test_rabbitmq_integration.py::test_rpc_multiple_sequential_calls PASSED
...
======================== 11 passed in 3.42s ========================
```

## Отладка тестов

### Просмотр логов во время тестов
```powershell
# Логи в консоль
pytest src/tests/test_rabbitmq_integration.py -v -s

# Логи с указанием уровня
pytest src/tests/test_rabbitmq_integration.py -v -s --log-cli-level=DEBUG
```

### Запуск конкретного теста с отладкой
```powershell
# С выводом всех деталей
pytest src/tests/test_rabbitmq_integration.py::test_rpc_call_success -v -s --log-cli-level=INFO
```

### Остановка на первой ошибке
```powershell
# Остановить выполнение при первом падении теста
pytest src/tests/ -v -x
```

### Запуск упавших тестов
```powershell
# Перезапустить только те тесты, которые упали в прошлый раз
pytest --lf -v
```

## Проверка покрытия кода

```powershell
# Установка pytest-cov (если еще не установлен)
pip install pytest-cov

# Запуск с покрытием
pytest src/tests/ -v --cov=src --cov-report=term-missing

# Генерация HTML отчета
pytest src/tests/ -v --cov=src --cov-report=html

# Просмотр отчета (откроется в браузере)
start htmlcov/index.html
```

## Непрерывная интеграция (CI)

Для CI/CD рекомендуется следующая последовательность:

```yaml
# Пример для GitHub Actions
- name: Start RabbitMQ
  run: docker run -d --name rabbitmq -p 5672:5672 rabbitmq:3

- name: Wait for RabbitMQ
  run: timeout 60 bash -c 'until nc -z localhost 5672; do sleep 1; done'

- name: Run unit tests
  run: pytest src/tests/test_rpc_service.py -v

- name: Run connection tests
  run: pytest src/tests/test_rabbitmq_connection.py -v

- name: Start worker
  run: python -m src.worker &

- name: Wait for worker
  run: sleep 5

- name: Run integration tests
  run: pytest src/tests/test_rabbitmq_integration.py -v
```

## Что делать если тесты падают?

### Проблема: "Connection refused"
```
Решение:
1. Проверьте, что RabbitMQ запущен: docker ps | grep rabbitmq
2. Проверьте порт: curl http://localhost:15672
3. Проверьте настройки в .env файле
```

### Проблема: "Timeout waiting for response"
```
Решение:
1. Убедитесь, что воркер запущен: python -m src.worker
2. Проверьте логи воркера в var/log/app.log
3. Увеличьте таймаут в тесте (для медленных систем)
```

### Проблема: "Method not found"
```
Решение:
1. Проверьте, что сервис зарегистрирован (логи воркера при старте)
2. Убедитесь, что сервис наследует BaseService
3. Проверьте имя файла: должно заканчиваться на _service.py
```

## Добавление новых тестов

### Шаблон unit теста для нового сервиса:

```python
import pytest
from src.services.my_new_service import MyNewService

class TestMyNewService:
    def test_service_initialization(self):
        service = MyNewService()
        assert service is not None
    
    def test_service_execute(self):
        service = MyNewService()
        result = service.execute({"data": "test"})
        assert result["status"] == "success"
```

### Шаблон интеграционного теста:

```python
import pytest

@pytest.mark.asyncio
async def test_my_new_service_via_rpc(rpc_consumer, rpc_producer):
    result = await rpc_producer.call(
        method="my_new.execute",
        params={"data": {"test": "value"}},
        timeout=10.0
    )
    assert result["status"] == "success"
```

## Полезные ссылки

- [Pytest документация](https://docs.pytest.org/)
- [Pytest-asyncio документация](https://pytest-asyncio.readthedocs.io/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/tutorials/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

## Контакты и поддержка

При возникновении проблем с тестами:
1. Проверьте логи в `var/log/app.log` и `var/log/error.log`
2. Запустите тесты с флагом `-v -s` для детального вывода
3. Проверьте документацию в `docs/ARCHITECTURE.md`
