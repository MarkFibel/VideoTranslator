# Docker Configuration for VideoTranslator

## RabbitMQ Setup

### Quick Start

**Запуск RabbitMQ через docker-compose (рекомендуется):**

```powershell
# Из корневой директории проекта
docker-compose -f docker/docker-compose.yml up -d

# Проверка статуса
docker-compose -f docker/docker-compose.yml ps

# Просмотр логов
docker-compose -f docker/docker-compose.yml logs -f rabbitmq

# Остановка
docker-compose -f docker/docker-compose.yml down
```

**Запуск через кастомный Dockerfile:**

```powershell
# Сборка образа
docker build -f docker/Dockerfile.rabbitmq -t videotranslator-rabbitmq .

# Запуск контейнера
docker run -d `
  --name videotranslator_rabbitmq `
  -p 5672:5672 `
  -p 15672:15672 `
  -e RABBITMQ_DEFAULT_USER=guest `
  -e RABBITMQ_DEFAULT_PASS=guest `
  videotranslator-rabbitmq
```

### Доступ к Management UI

После запуска контейнера откройте в браузере:
- URL: http://localhost:15672
- Username: `guest`
- Password: `guest`

### Настройки подключения

Убедитесь, что в `.env` файле указаны правильные параметры:

```env
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASS=guest
RABBITMQ_VHOST=/
```

### Структура файлов

```
docker/
├── docker-compose.yml       # Основная конфигурация для docker-compose
├── Dockerfile.rabbitmq      # Кастомный Dockerfile для RabbitMQ
├── README.md                # Эта документация
└── rabbitmq/
    ├── rabbitmq.conf        # Конфигурация RabbitMQ
    └── definitions.json     # Предопределенные очереди, пользователи и т.д.
```

### Полезные команды

```powershell
# Проверка здоровья контейнера
docker exec videotranslator_rabbitmq rabbitmq-diagnostics ping

# Список очередей
docker exec videotranslator_rabbitmq rabbitmqctl list_queues

# Список подключений
docker exec videotranslator_rabbitmq rabbitmqctl list_connections

# Перезапуск контейнера
docker restart videotranslator_rabbitmq

# Удаление контейнера и данных
docker-compose -f docker/docker-compose.yml down -v
```

### Production настройки

Для production окружения рекомендуется:

1. **Изменить credentials:**
   ```yaml
   environment:
     RABBITMQ_DEFAULT_USER: admin
     RABBITMQ_DEFAULT_PASS: <strong_password>
   ```

2. **Использовать отдельный volume для данных:**
   ```yaml
   volumes:
     - /path/to/persistent/storage:/var/lib/rabbitmq
   ```

3. **Настроить SSL/TLS** (добавить в `rabbitmq.conf`):
   ```
   listeners.ssl.default = 5671
   ssl_options.cacertfile = /etc/rabbitmq/ca_certificate.pem
   ssl_options.certfile = /etc/rabbitmq/server_certificate.pem
   ssl_options.keyfile = /etc/rabbitmq/server_key.pem
   ssl_options.verify = verify_peer
   ssl_options.fail_if_no_peer_cert = true
   ```

4. **Настроить мониторинг** через Prometheus exporter

### Troubleshooting

**Контейнер не запускается:**
```powershell
docker logs videotranslator_rabbitmq
```

**Порты заняты:**
```powershell
# Найти процесс, использующий порт 5672 или 15672
netstat -ano | findstr :5672
netstat -ano | findstr :15672

# Остановить процесс или изменить порты в docker-compose.yml
```

**Проблемы с подключением из приложения:**
1. Проверьте, что контейнер запущен: `docker ps`
2. Проверьте логи: `docker logs videotranslator_rabbitmq`
3. Убедитесь, что `.env` файл содержит правильные параметры
4. Проверьте доступность через telnet: `telnet localhost 5672`

### Интеграция с приложением

После запуска RabbitMQ:

1. **Запустите worker:**
   ```powershell
   python -m src.worker
   ```

2. **Запустите FastAPI приложение:**
   ```powershell
   uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Проверьте подключение:**
   ```powershell
   python test_rabbitmq.py
   ```

### Мониторинг

В Management UI (http://localhost:15672) доступны:
- Обзор системы и метрик
- Список очередей и их состояние
- Активные подключения и каналы
- Графики производительности
- Экспорт/импорт конфигурации

### Backup и восстановление

**Экспорт конфигурации:**
```powershell
docker exec videotranslator_rabbitmq rabbitmqadmin export definitions.json
```

**Импорт конфигурации:**
```powershell
docker exec videotranslator_rabbitmq rabbitmqadmin import definitions.json
```
