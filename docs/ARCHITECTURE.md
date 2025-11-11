# Архитектура VideoTranslator Backend

## Общий Обзор

VideoTranslator - это микросервисная система для обработки и перевода видео, построенная на FastAPI с асинхронной обработкой через RabbitMQ и JSON-RPC.

## Архитектурные Слои

### 1. API Слой (HTTP)

**Компоненты:**

- FastAPI приложение (`src/app.py`)
- HTTP роутеры (`src/routers/`)
- Схемы валидации (`src/schemas/`)
- Управление сессиями

**Ответственность:**

- Прием HTTP запросов от клиентов
- Валидация входящих данных
- Статическая раздача файлов
- Отправка задач в RabbitMQ
- Возврат ответов клиенту

### 2. Транспортный Слой (RabbitMQ + JSON-RPC)

**Компоненты:**

- RPC Producer (`src/transport/rabbitmq/producer.py`)
- RPC Consumer (`src/transport/rabbitmq/consumer.py`)
- Connection Manager (`src/transport/rabbitmq/connection.py`)
- JSON-RPC Dispatcher (`src/transport/json_rpc/dispatcher.py`)
- Service Loader (`src/transport/json_rpc/service_loader.py`)

**Ответственность:**

- Управление соединениями с RabbitMQ
- Отправка RPC запросов (Producer)
- Прием RPC запросов (Consumer)
- Маршрутизация запросов к сервисам
- Возврат результатов выполнения

### 3. Сервисный Слой (Business Logic)

**Компоненты:**

- Base Service (`src/services/base_service.py`)
- Test Service (`src/services/test_service.py`)
- ML Service (`src/services/ml_service/`)

**Ответственность:**

- Выполнение бизнес-логики
- Обработка данных
- Работа с ML моделями
- Автоматическая загрузка конфигурации

### 4. Конфигурационный Слой

**Компоненты:**

- App Config (`src/config/app_config.py`)
- Logging Config (`src/config/logging_config.py`)
- RabbitMQ Config (`src/config/rabbitmq_config.py`)
- Service Configs (`src/config/services/`)

**Ответственность:**

- Управление настройками приложения
- Загрузка переменных окружения
- Конфигурация логирования
- Настройки сервисов

## Поток Данных

### 1. Загрузка Файла (Upload Flow)

```
[Клиент] 
   ↓ HTTP POST /files/upload
[API Server - file_router.py]
   ↓ Валидация файла
   ↓ Сохранение в сессию
   ↓ Формирование RPC запроса
[RPC Producer]
   ↓ Отправка в RabbitMQ очередь
   ↓ Ожидание ответа (Direct Reply-to)
[RabbitMQ - rpc_queue]
   ↓ Доставка сообщения
[RPC Consumer - worker]
   ↓ Получение сообщения
[JSON-RPC Dispatcher]
   ↓ Парсинг JSON-RPC
   ↓ Поиск метода
[Service Loader]
   ↓ Находит нужный сервис
[Service.execute()]
   ↓ Выполнение бизнес-логики
   ↓ Возврат результата
[JSON-RPC Dispatcher]
   ↓ Формирование ответа
[RPC Consumer]
   ↓ Отправка в reply_to очередь
[RPC Producer]
   ↓ Получение ответа
[API Server]
   ↓ Формирование HTTP ответа
[Клиент]
   ↓ Получение результата
```

### 2. RPC Взаимодействие (Detailed)

**Producer Side (API Server):**

```python
# 1. Создание продюсера
producer = RPCProducer()
await producer.connect()

# 2. Формирование запроса
request = {
    "jsonrpc": "2.0",
    "method": "ml.execute",
    "params": {"video_path": "/path/to/video.mp4"},
    "id": "unique-correlation-id"
}

# 3. Отправка и ожидание
result = await producer.call(
    method="ml.execute",
    params={"video_path": "/path/to/video.mp4"},
    timeout=30.0
)
```

**Consumer Side (Worker):**

```python
# 1. Получение сообщения из очереди
message = await queue.consume()

# 2. Передача в диспетчер
response = dispatcher.handle_request(message.body)

# 3. Диспетчер вызывает сервис
service = services["ml"]
result = service.execute(params)

# 4. Отправка ответа
await channel.basic_publish(
    message=response,
    routing_key=message.reply_to,
    correlation_id=message.correlation_id
)
```

## Паттерны Проектирования

### 1. Factory Pattern

**Использование:** Создание FastAPI приложения

```python
def get_application() -> FastAPI:
    """Фабрика для создания сконфигурированного приложения"""
    app = FastAPI(...)
    app.include_router(get_apps_router())
    app.mount("/static", StaticFiles(directory="public"))
    return app
```

### 2. Service Auto-Discovery Pattern

**Использование:** Автоматическая регистрация сервисов

```python
class ServiceLoader:
    def discover_services(self):
        # Рекурсивно ищет *_service.py файлы
        # Находит классы наследники BaseService
        # Инстанцирует и регистрирует их
```

### 3. Direct Reply-to Pattern (RabbitMQ)

**Использование:** Эффективный RPC без временных очередей

```python
# Producer создает эксклюзивную очередь один раз
callback_queue = await channel.declare_queue('', exclusive=True)

# Для каждого запроса использует эту очередь
message.reply_to = callback_queue.name
message.correlation_id = unique_id
```

### 4. Dependency Injection

**Использование:** Внедрение зависимостей в роутеры

```python
@router.post("/upload")
async def upload_file(
    file: UploadFile,
    session: SessionDict = Depends(get_session)
):
    # session автоматически инжектится
```

### 5. Template Method Pattern

**Использование:** BaseService определяет скелет

```python
class BaseService:
    def get_config(self):
        # Общая логика загрузки конфигурации
        pass
    
    def execute(self, data: dict):
        # Должен быть реализован в подклассах
        raise NotImplementedError()
```

## Масштабирование

### Горизонтальное Масштабирование

**Workers:**

```bash
# Запустите несколько экземпляров воркеров
python -m src.worker  # Terminal 1
python -m src.worker  # Terminal 2
python -m src.worker  # Terminal 3
```

RabbitMQ автоматически распределит задачи между воркерами (round-robin).

**API Servers:**

```bash
# За load balancer (nginx/traefik)
uvicorn src.app:app --port 8001
uvicorn src.app:app --port 8002
uvicorn src.app:app --port 8003
```

### Вертикальное Масштабирование

- Увеличение ресурсов сервера (CPU, RAM)
- Настройка количества uvicorn workers
- Оптимизация размера пула соединений RabbitMQ

## Безопасность

### Текущие Меры

- Валидация размера файлов (MAX_FILE_SIZE)
- Структурированная обработка ошибок
- Логирование всех операций
- Изоляция сессий пользователей

### Планируемые Улучшения

- JWT аутентификация
- Rate limiting
- CORS конфигурация
- Шифрование данных в transit
- Валидация типов файлов (MIME)

## Мониторинг и Логирование

### Система Логирования

**Уровни:**

- Console: DEBUG (разработка), INFO (продакшн)
- File (app.log): INFO и выше
- File (error.log): ERROR и выше

**Ротация:**

- Максимум 5 файлов
- Размер файла: 10MB
- Автоматическая ротация при превышении

### Структура Логов

```js
2025-10-21 12:00:00,123 - src.worker - INFO - [worker.py:45] - Starting RabbitMQ Worker
2025-10-21 12:00:01,456 - src.transport.rabbitmq.consumer - INFO - [consumer.py:67] - Received RPC request. Correlation ID: abc-123
```

## Обработка Ошибок

### Типы Ошибок

1. **HTTP Errors** - HTTPException с статус кодами
2. **RPC Errors** - ServiceExecutionError для ошибок сервисов
3. **Validation Errors** - Pydantic ValidationError
4. **Connection Errors** - RabbitMQ connection failures

### Стратегия Восстановления

- **RabbitMQ:** Автоматическое переподключение
- **RPC Timeout:** Настраиваемый timeout с fallback
- **Session Cleanup:** Автоматическая очистка при ошибках

## Конфигурация Окружения

### Обязательные Переменные (.env)

```env
# Application
PROJECT_NAME=VideoTranslator
VERSION=1.0.0
DEBUG=true
LOG_LEVEL=INFO

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_RPC_QUEUE=rpc_queue

# Files
MAX_FILE_SIZE=10485760  # 10MB in bytes
```

## Тестирование

### Текущий Подход

- Ручное тестирование через FastAPI Swagger UI
- Скрипты `test_rabbitmq.py` и `test_rpc.py`
- Проверка логов для диагностики

### Планируемое

- Unit тесты (pytest)
- Integration тесты (RabbitMQ + Services)
- E2E тесты (API → Worker → Response)
- Coverage отчеты

## Диаграмма Компонентов

```js
┌─────────────────────────────────────────────────────────────┐
│                     Client (Browser/API)                    │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────┐      │
│  │  Routers   │  │  Schemas    │  │  Session Store   │      │
│  └────────────┘  └─────────────┘  └──────────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │ RPC Call
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     RPC Producer                            │
│         (Direct Reply-to, Correlation ID)                   │
└────────────────────────┬────────────────────────────────────┘
                         │ AMQP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      RabbitMQ Broker                        │
│                    Queue: rpc_queue                         │
└────────────────────────┬────────────────────────────────────┘
                         │ Consume
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     RPC Consumer (Worker)                   │
│  ┌──────────────────────────────────────────────────┐       │
│  │           JSON-RPC Dispatcher                    │       │
│  │  ┌─────────────────────────────────────────┐     │       │
│  │  │       Service Loader                    │     │       │
│  │  │  • Auto-discovery                       │     │       │
│  │  │  • Config management                    │     │       │
│  │  └─────────────────────────────────────────┘     │       │
│  └──────────────────────┬───────────────────────────┘       │
│                         │ Route to Service                  │
│                         ▼                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐         │
│  │ TestService │  │  ML Service  │  │   Future    │         │
│  │  .execute() │  │  .execute()  │  │  Services   │         │
│  └─────────────┘  └──────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Расширение Системы

### Добавление Нового Сервиса

1. **Создать файл сервиса:**

```python
# src/services/video_processing_service.py
from .base_service import BaseService

class VideoProcessingService(BaseService):
    def execute(self, data: dict) -> dict:
        # Ваша логика
        return {"status": "success"}
```

2. **Конфигурация создастся автоматически:**

```python
# src/config/services/video_processing_config.py (auto-created)
RPC_ENABLED = False  # Установите True для активации
```

3. **Активировать сервис:**

```python
# src/config/services/video_processing_config.py
RPC_ENABLED = True
```

4. **Сервис автоматически зарегистрируется** при следующем запуске воркера

### Добавление Нового Endpoint

1. **Создать роутер:**

```python
# src/routers/new_router.py
from fastapi import APIRouter

router = APIRouter(prefix="/new", tags=["new"])

@router.get("/test")
async def test_endpoint():
    return {"message": "Hello"}
```

2. **Зарегистрировать роутер:**

```python
# src/routes.py
from src.routers import new_router

def get_apps_router() -> APIRouter:
    router = APIRouter()
    router.include_router(new_router.router)
    return router
```

## Заключение

Архитектура VideoTranslator построена на принципах:

- **Модульность** - легко добавлять новые компоненты
- **Масштабируемость** - горизонтальное масштабирование воркеров
- **Асинхронность** - эффективная работа с I/O
- **Надежность** - обработка ошибок и переподключения
- **Автоматизация** - auto-discovery сервисов и конфигураций

Эти принципы позволяют системе эффективно обрабатывать видео в фоновом режиме, оставаясь отзывчивой для пользователей.
