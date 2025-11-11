# RabbitMQ Message Example для TestService

Этот документ описывает формат сообщений RabbitMQ для взаимодействия с `TestService` через JSON-RPC протокол.

## Архитектура взаимодействия

```js
API Server (RPCProducer)  →  RabbitMQ Queue  →  Worker (RPCConsumer)  →  TestService
                          ←                   ←                       ←
```

1. **API Server** отправляет JSON-RPC запрос в очередь `rpc_queue`
2. **Worker** получает запрос и передает в `JSONRPCDispatcher`
3. **Dispatcher** вызывает метод `test.execute` у `TestService`
4. **Результат** возвращается обратно через Direct Reply-to pattern

## Формат JSON-RPC сообщения

### Базовая структура запроса

```json
{
  "jsonrpc": "2.0",
  "method": "test.execute",
  "params": {
    "data": {
      "message": "Hello from RabbitMQ!"
    }
  },
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Поля запроса

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| `jsonrpc` | string | Да | Версия протокола (всегда "2.0") |
| `method` | string | Да | Имя метода в формате `{service}.{method}` |
| `params` | object | Да | Параметры метода |
| `params.data` | object | Да | Данные для обработки сервисом |
| `id` | string/number | Да | Уникальный идентификатор запроса (correlation_id) |

### Примеры запросов

#### Пример 1: Простое сообщение

```json
{
  "jsonrpc": "2.0",
  "method": "test.execute",
  "params": {
    "data": {
      "message": "Hello from RabbitMQ!"
    }
  },
  "id": 1
}
```

**Ответ:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "message": "Test service received: Hello from RabbitMQ!",
    "echo": {
      "message": "Hello from RabbitMQ!"
    },
    "service": "TestService"
  },
  "id": 1
}
```

#### Пример 2: Сообщение с метаданными

```json
{
  "jsonrpc": "2.0",
  "method": "test.execute",
  "params": {
    "data": {
      "message": "Processing video file",
      "timestamp": "2025-10-27T12:30:00Z",
      "user_id": "user_12345",
      "file_name": "video.mp4"
    }
  },
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Ответ:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "message": "Test service received: Processing video file",
    "echo": {
      "message": "Processing video file",
      "timestamp": "2025-10-27T12:30:00Z",
      "user_id": "user_12345",
      "file_name": "video.mp4"
    },
    "service": "TestService"
  },
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Пример 3: Пустое сообщение

```json
{
  "jsonrpc": "2.0",
  "method": "test.execute",
  "params": {
    "data": {}
  },
  "id": 2
}
```

**Ответ:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "message": "Test service received: No message provided",
    "echo": {},
    "service": "TestService"
  },
  "id": 2
}
```

## Формат ответа при ошибке

Если метод не найден или произошла ошибка:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": {
      "method": "nonexistent.execute"
    }
  },
  "id": 3
}
```

### Коды ошибок JSON-RPC

| Код | Значение | Описание |
|-----|----------|----------|
| -32700 | Parse error | Невалидный JSON |
| -32600 | Invalid Request | Запрос не соответствует спецификации JSON-RPC |
| -32601 | Method not found | Метод не существует |
| -32602 | Invalid params | Неверные параметры метода |
| -32603 | Internal error | Внутренняя ошибка сервера |

## Использование RPCProducer в коде

### Python (Async)

```python
from src.transport.rabbitmq.producer import RPCProducer

async def call_test_service():
    producer = RPCProducer()
    await producer.connect()
    
    try:
        result = await producer.call(
            method="test.execute",
            params={
                "data": {
                    "message": "Hello from Python!",
                    "timestamp": "2025-10-27T12:00:00Z"
                }
            },
            timeout=10.0
        )
        print(f"Result: {result}")
    finally:
        await producer.close()
```

### Свойства RabbitMQ сообщения

При отправке через `aio-pika`, сообщение имеет следующие свойства:

```python
Message(
    body=json.dumps(request_body).encode(),  # Тело сообщения в байтах
    correlation_id="550e8400-e29b-41d4-a716-446655440000",  # ID для связи запрос-ответ
    reply_to="amq.gen-unique-queue-name",  # Очередь для ответа
    content_type="application/json"  # Тип контента
)
```

#### Важные свойства

- **correlation_id**: Уникальный UUID, связывающий запрос и ответ
- **reply_to**: Имя временной очереди для получения ответа (Direct Reply-to pattern)
- **content_type**: Всегда `application/json` для JSON-RPC
- **routing_key**: Имя очереди RPC (по умолчанию `rpc_queue`)

## Тестирование

### Запуск тестов

1. **Запустите воркер** (в отдельном терминале):

```powershell
python -m src.worker
```

2. **Запустите тест RabbitMQ**:

```powershell
python test_rabbitmq.py
```

### Ожидаемый вывод

```js
============================================================
RabbitMQ RPC Producer Test
============================================================
Connecting to RabbitMQ at localhost:5672
Initializing RPC producer...
============================================================
Producer connected and ready to send requests
============================================================

============================================================
Test 1: Calling 'test.execute' method
============================================================
✓ Test 1 PASSED
  Result: {
    'status': 'success', 
    'message': 'Test service received: Hello from RabbitMQ!',
    'echo': {'message': 'Hello from RabbitMQ!'}, 
    'service': 'TestService'
  }
```

## Мониторинг сообщений

### Просмотр логов воркера

```powershell
Get-Content var/log/app.log -Tail 50 -Wait
```

### Проверка очереди RabbitMQ

Если у вас установлен RabbitMQ Management Plugin:

- URL: <http://localhost:15672>
- Логин: guest / Пароль: guest
- Очередь: `rpc_queue`

## Конфигурация

### Настройки RabbitMQ (`src/config/rabbitmq_config.py`)

```python
RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
RABBITMQ_USER = "guest"
RABBITMQ_PASSWORD = "guest"
RABBITMQ_RPC_QUEUE = "rpc_queue"
```

### Переменные окружения (`.env`)

```env
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_RPC_QUEUE=rpc_queue
```

## Расширение для других сервисов

Чтобы создать новый сервис с такой же структурой сообщений:

1. **Создайте класс сервиса**:

```python
from src.services.base_service import BaseService

class VideoProcessingService(BaseService):
    def execute(self, data: dict) -> dict:
        # Ваша логика обработки
        return {"status": "success", "result": "processed"}
```

2. **Сохраните в** `src/services/video_processing_service.py`

3. **Вызывайте через RPC**:

```python
result = await producer.call(
    method="video_processing.execute",  # Имя автоматически генерируется
    params={"data": {"video_path": "/path/to/video.mp4"}},
    timeout=60.0
)
```

## Troubleshooting

### Ошибка: "Producer not connected"

**Решение**: Вызовите `await producer.connect()` перед `producer.call()`

### Ошибка: "RPC request timeout"

**Решение**:

- Проверьте, что воркер запущен: `python -m src.worker`
- Увеличьте timeout в параметре `call(timeout=60.0)`

### Ошибка: "Method not found"

**Решение**:

- Проверьте имя метода (формат: `{service_name}.execute`)
- Убедитесь, что файл сервиса заканчивается на `_service.py`
- Перезапустите воркер для переобнаружения сервисов

### Ошибка подключения к RabbitMQ

**Решение**:

- Убедитесь, что RabbitMQ запущен
- Проверьте настройки в `.env` или `rabbitmq_config.py`
- Проверьте доступность порта 5672

## Дополнительные ресурсы

- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [RabbitMQ Direct Reply-to](https://www.rabbitmq.com/direct-reply-to.html)
- [aio-pika Documentation](https://aio-pika.readthedocs.io/)
