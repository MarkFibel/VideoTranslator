# Быстрый старт тестирования RabbitMQ

## 🚀 Минимальный набор команд

### 1. Установка (один раз)
```powershell
pip install -r requirements.txt
```

### 2. Запуск RabbitMQ (Docker)
```powershell
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 3. Unit тесты (без RabbitMQ)
```powershell
pytest src/tests/test_rpc_service.py -v
```

### 4. Тесты подключения (с RabbitMQ)
```powershell
pytest src/tests/test_rabbitmq_connection.py -v
```

### 5. Интеграционные тесты (нужен воркер)
```powershell
# Терминал 1
python -m src.worker

# Терминал 2
pytest src/tests/test_rabbitmq_integration.py -v
```

## 📊 Все тесты сразу

```powershell
# Запуск воркера в фоне (Windows)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m src.worker"

# Подождать 3 секунды
Start-Sleep -Seconds 3

# Запустить все тесты
pytest src/tests/ -v
```

## 🛠️ Полезные команды

```powershell
# Один конкретный тест
pytest src/tests/test_rabbitmq_integration.py::test_rpc_call_success -v

# С логами
pytest src/tests/ -v -s

# Только failed тесты
pytest --lf -v

# Остановка на первой ошибке
pytest -x

# С покрытием
pytest src/tests/ -v --cov=src
```

## 🐛 Быстрая отладка

```powershell
# Посмотреть логи приложения
Get-Content var/log/app.log -Tail 50

# Посмотреть логи ошибок
Get-Content var/log/error.log -Tail 50

# Проверить RabbitMQ
curl http://localhost:15672

# Остановить RabbitMQ
docker stop rabbitmq

# Удалить RabbitMQ
docker rm rabbitmq
```

## ✅ Чеклист перед коммитом

- [ ] `pytest src/tests/test_rpc_service.py -v` ✓
- [ ] `pytest src/tests/test_rabbitmq_connection.py -v` ✓
- [ ] `pytest src/tests/test_rabbitmq_integration.py -v` ✓
- [ ] Все тесты зеленые
- [ ] Логи без критических ошибок

## 📝 Примечания

- Unit тесты выполняются < 1 секунды
- Connection тесты выполняются ~2-3 секунды
- Integration тесты выполняются ~3-5 секунд
- Полный набор тестов ~6-8 секунд
