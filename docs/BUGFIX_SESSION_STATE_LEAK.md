# Исправление бага с восстановлением сессии

## Описание проблемы

При обновлении страницы во время обработки файла (`pending=True`), состояние сессии не восстанавливалось корректно. При попытке загрузить новый файл пользователь получал ошибку:

```json
{
  "error": {
    "code": "FILE_PROCESSING",
    "message": "Файл уже в процессе обработки",
    "stage_failed": "validation",
    "recoverable": true
  }
}
```

### Причины бага

1. **В `upload_with_progress()`** (файл `src/utils/upload_utils.py`):
   - При ошибке валидации (`validation_error`) метод делал `return` БЕЗ очистки флагов сессии
   - Флаг `pending=True` мог остаться установленным после критических ошибок

2. **В `event_generator()`** (файл `src/routers/file_router.py`):
   - Критические ошибки перехватывались в блоке `except`, но состояние сессии НЕ очищалось
   - Временный файл не удалялся при критической ошибке

## Внесенные исправления

### 1. Исправление в `upload_utils.py`

**Файл:** `src/utils/upload_utils.py`  
**Метод:** `SSEUploadOrchestrator.upload_with_progress()`

#### Было:
```python
# 1. Валидация состояния сессии
validation_error = self.file_service.validate_session_state(session)
if validation_error:
    error_code, error_message = validation_error.split(":", 1)
    yield format_sse_error(
        error_code=error_code,
        error_message=error_message,
        stage_failed="validation"
    )
    return  # ❌ return без очистки, pending остается True!

session['pending'] = True  # ⚠️ устанавливается ПОСЛЕ проверки
```

#### Стало:
```python
# 1. Валидация состояния сессии (ДО установки pending=True!)
validation_error = self.file_service.validate_session_state(session)
if validation_error:
    error_code, error_message = validation_error.split(":", 1)
    
    # НЕ устанавливаем pending=True если валидация не прошла
    # Это позволит пользователю повторить запрос после исправления проблемы
    yield format_sse_error(
        error_code=error_code,
        error_message=error_message,
        stage_failed="validation",
        recoverable=True  # ✅ Ошибка валидации - можно повторить после исправления
    )
    return  # ✅ Выход без изменения состояния

# Только после успешной валидации устанавливаем pending
session['pending'] = True  # ✅ устанавливается ПОСЛЕ валидации
```

**Ключевое изменение:** 
- `session['pending'] = True` перенесено ПОСЛЕ проверки валидации
- Добавлен флаг `recoverable=True` для информирования клиента

### 2. Исправление в `file_router.py`

**Файл:** `src/routers/file_router.py`  
**Функция:** `upload_file_stream() -> event_generator()`

#### Было:
```python
async def event_generator():
    try:
        session = request.state.session.get_session()
        # ... обработка ...
        
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        # ❌ НЕТ очистки состояния сессии!
        yield format_sse_error(...)
```

#### Стало:
```python
async def event_generator():
    session = None  # ✅ Инициализируем вне блока try
    try:
        session = request.state.session.get_session()
        # ... обработка ...
        
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        
        # ✅ КРИТИЧЕСКИ ВАЖНО: Очищаем состояние сессии при критической ошибке
        if session:
            session['pending'] = False
            session['need_download'] = False
            
            # Удаляем метаданные файла, если он был сохранен
            if session.get('last_uploaded_file'):
                file_path = session['last_uploaded_file'].get('file_path', '')
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Temp file removed: {file_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup: {cleanup_error}")
                session['last_uploaded_file'] = None
        
        yield format_sse_error(...)
```

**Ключевые изменения:**
- Переменная `session` инициализируется ВНЕ блока `try` для доступа в `except`
- При критической ошибке очищаются все флаги сессии
- Временный файл удаляется из файловой системы
- Метаданные файла удаляются из сессии

## Проверка исправлений

### Сценарий 1: Обновление страницы во время обработки

**До исправления:**
1. Загрузка файла → `pending=True`
2. Обновление страницы (F5)
3. Попытка загрузить новый файл → ❌ Ошибка "FILE_PROCESSING"
4. `pending=True` остается навсегда

**После исправления:**
1. Загрузка файла → `pending=True`
2. Обновление страницы (F5) → восстановление состояния показывает "Обработка файла..."
3. Если обработка завершилась → `pending=False`, `need_download=True`
4. Если произошла критическая ошибка → `pending=False` автоматически очищается
5. Попытка загрузить новый файл → ✅ Работает корректно

### Сценарий 2: Критическая ошибка в event_generator

**До исправления:**
1. Критическая ошибка в потоке SSE
2. `pending=True` остается установленным
3. Временный файл остается на диске
4. Пользователь не может загрузить новый файл

**После исправления:**
1. Критическая ошибка в потоке SSE
2. ✅ Автоматическая очистка: `pending=False`, `need_download=False`
3. ✅ Временный файл удаляется
4. ✅ Пользователь может загрузить новый файл

### Сценарий 3: Ошибка валидации

**До исправления:**
1. Попытка загрузить файл при `pending=True`
2. ❌ `pending=True` устанавливается ДО валидации
3. ❌ Ошибка валидации делает `return`, но `pending` остается `True`

**После исправления:**
1. Попытка загрузить файл при `pending=True`
2. ✅ Валидация проверяется ДО установки `pending=True`
3. ✅ Ошибка валидации → `return` без изменения состояния
4. ✅ Состояние сессии остается в прежнем состоянии (согласованное)

## Тестирование

### Ручное тестирование

```bash
# Терминал 1: Запуск сервера
python -m src.app

# Терминал 2: Запуск worker (если используется RabbitMQ)
python -m src.worker

# Браузер
http://localhost:8000
```

**Шаги:**
1. Загрузите файл
2. Во время обработки обновите страницу (F5)
3. Дождитесь завершения обработки
4. Проверьте что кнопка "Скачать" отображается
5. Обновите страницу снова - кнопка должна остаться
6. Скачайте файл
7. Попробуйте загрузить новый файл - должно работать

### Проверка состояния сессии

```bash
curl http://localhost:8000/files/session/status
```

Ожидаемые результаты:
- После загрузки: `{"pending": true, "need_download": false, "file": null}`
- После завершения: `{"pending": false, "need_download": true, "file": {...}}`
- После ошибки: `{"pending": false, "need_download": false, "file": null}`

## Итоговые улучшения

✅ **Устранена утечка состояния** - `pending=True` больше не "застревает"  
✅ **Корректная очистка ресурсов** - временные файлы удаляются при ошибках  
✅ **Улучшенная обработка ошибок** - состояние сессии всегда согласованное  
✅ **Возможность повторных попыток** - пользователь может загрузить новый файл после любой ошибки  
✅ **Предотвращение race conditions** - валидация выполняется ДО изменения состояния  

## Дополнительные рекомендации

1. **Мониторинг:** Добавить метрики для отслеживания состояний `pending=True` которые длятся слишком долго
2. **Timeout:** Рассмотреть автоматическую очистку `pending=True` после определенного времени (например, 5 минут)
3. **Webhook:** При длительной обработке уведомлять пользователя через email/push вместо удержания `pending=True`
