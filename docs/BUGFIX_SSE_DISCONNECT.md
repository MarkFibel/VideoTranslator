# Исправление разрыва SSE соединения

## Проблема

При прерывании SSE соединения (обновление страницы, закрытие вкладки, потеря сети) генератор `event_generator()` просто останавливается БЕЗ вызова блока `except`. В результате:

- ❌ `session['pending'] = True` остается установленным
- ❌ Временный файл не удаляется
- ❌ Пользователь не может загрузить новый файл (ошибка "FILE_PROCESSING")

## Решение

Добавлен блок `finally` в `event_generator()`, который выполняется **ВСЕГДА**, независимо от причины завершения:
- ✅ Нормальное завершение
- ✅ Исключение
- ✅ **Разрыв соединения** (главное!)

## Реализация

### Добавлен флаг успешного завершения

```python
completed_successfully = False

async for event in orchestrator.upload_with_progress(file, session):
    # Отслеживаем успешное завершение
    if 'event: complete' in event:
        completed_successfully = True
    
    yield event
```

### Добавлен блок finally

```python
finally:
    # Выполняется ВСЕГДА, даже при разрыве соединения
    if session and not completed_successfully:
        if session.get('pending', False):
            logger.warning(f"SSE connection interrupted. Cleaning up.")
            
            # Очищаем pending - пользователь может повторить попытку
            session['pending'] = False
            
            # Удаляем временный файл только если он не был успешно обработан
            if not session.get('need_download', False) and session.get('last_uploaded_file'):
                file_path = session['last_uploaded_file'].get('file_path', '')
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                session['last_uploaded_file'] = None
```

## Логика очистки

### Случай 1: Успешное завершение
```
completed_successfully = True
→ finally блок ничего не делает
→ pending=False, need_download=True (установлено оркестратором)
```

### Случай 2: Разрыв соединения ДО завершения
```
completed_successfully = False
pending = True
need_download = False
→ finally очищает pending=False
→ удаляет временный файл
→ пользователь может загрузить новый файл
```

### Случай 3: Разрыв соединения ПОСЛЕ обработки (но до получения complete)
```
completed_successfully = False (событие не дошло)
pending = True
need_download = True (успел установиться)
→ finally очищает pending=False
→ НЕ удаляет файл (need_download=True означает успех)
→ пользователь может скачать файл
```

## Тестирование

### Тест 1: Прерывание во время загрузки

```bash
# 1. Загрузите большой файл
# 2. СРАЗУ обновите страницу (F5)
# 3. Подождите 1-2 секунды
# 4. Попробуйте загрузить новый файл
```

**Ожидается:** ✅ Новый файл загружается успешно

### Тест 2: Закрытие вкладки

```bash
# 1. Загрузите файл
# 2. Закройте вкладку
# 3. Откройте страницу снова
# 4. Попробуйте загрузить новый файл
```

**Ожидается:** ✅ Новый файл загружается успешно

### Тест 3: Проверка логов

```bash
# Откройте var/log/app.log
# Найдите строку:
"SSE connection interrupted for file ... Cleaning up session state."
```

## Важные детали реализации

### Почему не очищаем need_download в finally?

```python
# ❌ НЕ делаем session['need_download'] = False
```

**Причина:** Файл мог быть успешно обработан, но событие `complete` не дошло до клиента из-за разрыва соединения. Если мы очистим `need_download`, пользователь потеряет доступ к обработанному файлу.

### Почему используем 'event: complete' для проверки?

```python
if 'event: complete' in event:
    completed_successfully = True
```

**Причина:** SSE события имеют формат:
```
event: complete
data: {"result": {...}}
```

Наличие строки `'event: complete'` гарантирует, что обработка завершилась успешно и событие было отправлено клиенту.

## Дополнительные улучшения

### Можно добавить метрику времени обработки

```python
start_time = asyncio.get_event_loop().time()

finally:
    duration = asyncio.get_event_loop().time() - start_time
    logger.info(f"SSE stream duration: {duration:.2f}s, completed={completed_successfully}")
```

### Можно добавить проверку request.is_disconnected()

```python
async for event in orchestrator.upload_with_progress(file, session):
    if await request.is_disconnected():
        logger.warning("Client disconnected, stopping processing")
        break
    yield event
```

Но это может остановить обработку преждевременно. Текущее решение с `finally` проще и надежнее.
