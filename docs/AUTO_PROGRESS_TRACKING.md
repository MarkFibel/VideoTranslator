# Автоматический учет прогресса в BaseService

## Обзор

`BaseService` теперь поддерживает автоматический учет прогресса с возможностью вызова `get_current_stage_message()` без параметров. Система автоматически отслеживает текущий этап, подэтапы и рассчитывает прогресс на основе конфигурации этапов.

## Основные возможности

- ✅ **Автоматическое переключение стадий** из YAML конфигурации через `next_stage()`
- ✅ Автоматический расчет прогресса на основе текущего этапа
- ✅ Поддержка подэтапов с детализацией
- ✅ Расчет ETA (Estimated Time of Arrival)
- ✅ Простой вызов без параметров: `yield get_current_stage_message()`

## Быстрый старт

### 1. Автоматическое переключение стадий (РЕКОМЕНДУЕТСЯ)

```python
from src.services.base_service import BaseService

class MyService(BaseService):
    async def execute_stream(self, data: dict):
        # Начать отслеживание времени
        self._start_tracking()
        
        # Автоматически перейти к первому этапу из YAML конфигурации
        self.next_stage()
        yield self.get_current_stage_message()
        
        # ... ваша логика обработки первого этапа ...
        
        # Автоматически перейти к следующему этапу
        self.next_stage()
        yield self.get_current_stage_message()
        
        # ... ваша логика обработки второго этапа ...
        
        # Финал
        yield self.create_success_message()
```

### 2. Ручное указание этапов (альтернативный способ)

```python
from src.services.base_service import BaseService

class MyService(BaseService):
    async def execute_stream(self, data: dict):
        # Начать отслеживание времени
        self._start_tracking()
        
        # Вручную установить этап по ID
        self.set_stage("processing")
        
        # Получить и отправить сообщение о прогрессе
        yield self.get_current_stage_message()
        
        # ... ваша логика ...
        
        # Финал
        yield self.create_success_message()
```

### 3. Автоматическое переключение с подэтапами

```python
async def execute_stream(self, data: dict):
    self._start_tracking()
    
    # Автоматически перейти к следующему этапу с указанием 10 подэтапов
    self.next_stage(total_substeps=10)
    
    for i in range(10):
        # Обработка кадра
        process_frame(i)
        
        # Автоматическое увеличение подэтапа
        self.increment_substep()
        
        # Отправка прогресса с ETA
        yield self.get_current_stage_message(include_eta=True)
```

### 4. Ручная установка подэтапа

```python
# Если вы знаете точный номер подэтапа
self.next_stage(total_substeps=5)

for i, chunk in enumerate(text_chunks):
    process_chunk(chunk)
    
    # Установить конкретный подэтап
    self.set_substep(i + 1)
    
    yield self.get_current_stage_message()
```

## API методов

### Управление этапами

#### `next_stage(total_substeps: int = 0) -> bool` ⭐ РЕКОМЕНДУЕТСЯ
Автоматически перейти к следующему этапу из YAML конфигурации.

**Параметры:**
- `total_substeps` - Общее количество подэтапов для следующего этапа (опционально)

**Возвращает:** `True` если переход выполнен, `False` если это был последний этап.

**Как работает:**
- При первом вызове переходит к первому этапу из конфигурации
- При последующих вызовах автоматически переходит к следующему этапу
- Не требует знания ID этапов - все берется из YAML

**Пример:**
```python
# Переход к первому этапу
self.next_stage()  # Автоматически берет первый этап из YAML

# Переход к следующему этапу с подэтапами
self.next_stage(total_substeps=100)

# Проверка успешности перехода
if self.next_stage():
    yield self.get_current_stage_message()
else:
    # Достигнут последний этап
    yield self.create_success_message()
```

#### `start_first_stage(total_substeps: int = 0)`
Явно начать с первого этапа из конфигурации. Эквивалентно первому вызову `next_stage()`.

**Параметры:**
- `total_substeps` - Общее количество подэтапов для первого этапа

**Пример:**
```python
self._start_tracking()
self.start_first_stage(total_substeps=5)
yield self.get_current_stage_message()
```

#### `set_stage(stage_id: str, total_substeps: int = 0)`
Вручную установить конкретный этап обработки по ID.

**Параметры:**
- `stage_id` - ID этапа из YAML конфигурации
- `total_substeps` - Общее количество подэтапов (опционально)

**Когда использовать:**
- Когда нужно пропустить этапы
- Для условного выполнения этапов
- Для отладки конкретного этапа

**Пример:**
```python
self.set_stage("video_loading")  # Без подэтапов
self.set_stage("frame_extraction", total_substeps=100)  # С подэтапами
```

#### `increment_substep()`
Увеличить счетчик текущего подэтапа на 1.

**Пример:**
```python
self.set_stage("processing", total_substeps=10)
for item in items:
    process(item)
    self.increment_substep()
    yield self.get_current_stage_message()
```

#### `set_substep(substep: int)`
Установить конкретный номер подэтапа.

**Пример:**
```python
self.set_stage("processing", total_substeps=10)
self.set_substep(5)  # Перейти сразу к 5-му подэтапу
```

### Получение информации о прогрессе

#### `get_current_progress() -> int`
Получить текущий процент выполнения (0-100).

**Возвращает:** Процент выполнения на основе текущего этапа и подэтапов.

**Пример:**
```python
progress = self.get_current_progress()
print(f"Текущий прогресс: {progress}%")
```

#### `get_current_stage_message(include_eta: bool = False) -> dict`
**Главный метод** - получить полное сообщение о текущем прогрессе.

**Параметры:**
- `include_eta` - Включить расчет оставшегося времени (по умолчанию False)

**Возвращает:** Словарь с форматированным сообщением о прогрессе.

**Формат ответа:**
```python
{
    "progress": 45,
    "stage": "frame_extraction",
    "status": "processing",
    "timestamp": "2025-11-11T10:30:00.000Z",
    "details": {
        "current_step": 5,
        "total_steps": 10,
        "eta_seconds": 15  # Если include_eta=True
    }
}
```

**Пример:**
```python
# Без ETA
yield self.get_current_stage_message()

# С ETA
yield self.get_current_stage_message(include_eta=True)
```

## Примеры использования

### Пример 1: Простая последовательность этапов (АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ) ⭐

```python
class SimpleService(BaseService):
    async def execute_stream(self, data: dict):
        self._start_tracking()
        
        # Просто вызываем next_stage() для каждого этапа
        # Все этапы автоматически берутся из YAML конфигурации
        
        # Этап 1: loading
        self.next_stage()
        yield self.get_current_stage_message()
        await do_loading()
        
        # Этап 2: processing
        self.next_stage()
        yield self.get_current_stage_message()
        await do_processing()
        
        # Этап 3: saving
        self.next_stage()
        yield self.get_current_stage_message()
        await do_saving()
        
        yield self.create_success_message()
```

### Пример 1.1: То же самое с ручным указанием этапов

```python
class SimpleService(BaseService):
    async def execute_stream(self, data: dict):
        self._start_tracking()
        
        stages = ["loading", "processing", "saving"]
        
        for stage in stages:
            self.set_stage(stage)  # Ручное указание ID
            yield self.get_current_stage_message()
            
            # Ваша логика обработки
            await do_work(stage)
        
        yield self.create_success_message()
```

### Пример 2: Обработка коллекции элементов (с автопереключением)

```python
class BatchService(BaseService):
    async def execute_stream(self, data: dict):
        self._start_tracking()
        
        items = data.get("items", [])
        
        # Автоматически переходим к следующему этапу с подэтапами
        self.next_stage(total_substeps=len(items))
        
        for i, item in enumerate(items):
            # Обработка элемента
            result = await process_item(item)
            
            # Обновление прогресса
            self.increment_substep()
            yield self.get_current_stage_message(include_eta=True)
        
        yield self.create_success_message(result={"processed": len(items)})
```

### Пример 3: Многоэтапная обработка с подэтапами (АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ) ⭐

```python
class VideoTranslationService(BaseService):
    async def execute_stream(self, data: dict):
        self._start_tracking()
        
        try:
            # Этап 1: Загрузка (автоматически берется из YAML)
            self.next_stage()
            yield self.get_current_stage_message()
            video = await load_video(data["video_path"])
            
            # Этап 2: Извлечение кадров (автоматический переход)
            frames = extract_frames(video)
            self.next_stage(total_substeps=len(frames))
            
            for frame in frames:
                await process_frame(frame)
                self.increment_substep()
                yield self.get_current_stage_message(include_eta=True)
            
            # Этап 3: Распознавание текста (автоматический переход)
            self.next_stage(total_substeps=len(frames))
            
            for i, frame in enumerate(frames):
                text = await recognize_text(frame)
                self.set_substep(i + 1)
                yield self.get_current_stage_message(include_eta=True)
            
            # Этап 4: Перевод (автоматический переход)
            self.next_stage()
            yield self.get_current_stage_message()
            translated = await translate_text(text)
            
            # Этап 5: Финализация (автоматический переход)
            self.next_stage()
            yield self.get_current_stage_message()
            output = await assemble_video(frames, translated)
            
            # Успех
            yield self.create_success_message(
                result={"output_file": output}
            )
            
        except Exception as e:
            yield self.create_error_message(
                error_code="TRANSLATION_FAILED",
                error_message=str(e),
                stage_failed=self._current_stage_id or "unknown"
            )
```

**Преимущества автоматического переключения:**
- ✅ Не нужно помнить ID этапов - все из YAML
- ✅ Легко изменить порядок этапов - просто отредактировать YAML
- ✅ Меньше ошибок - невозможно указать несуществующий этап
- ✅ Код более читаемый и поддерживаемый

### Пример 4: Условная обработка этапов

```python
class AdaptiveService(BaseService):
    async def execute_stream(self, data: dict):
        self._start_tracking()
        
        # Этап 1: Анализ (автоматический переход)
        self.next_stage()
        yield self.get_current_stage_message()
        needs_preprocessing = await analyze_input(data)
        
        # Этап 2: Предобработка (условно)
        if needs_preprocessing:
            self.next_stage(total_substeps=3)
            
            for step in range(3):
                await preprocess_step(step)
                self.increment_substep()
                yield self.get_current_stage_message()
        else:
            # Пропускаем этап предобработки
            self.next_stage()
        
        # Этап 3: Основная обработка (автоматический переход)
        self.next_stage()
        yield self.get_current_stage_message()
        result = await main_process(data)
        
        yield self.create_success_message(result=result)
```

### Пример 5: Использование в цикле

```python
class MultiStageService(BaseService):
    async def execute_stream(self, data: dict):
        self._start_tracking()
        
        # Все этапы берутся из YAML автоматически
        while self.next_stage():
            # Отправляем начало этапа
            yield self.get_current_stage_message()
            
            # Выполняем логику для текущего этапа
            await self._process_current_stage(data)
        
        yield self.create_success_message()
    
    async def _process_current_stage(self, data: dict):
        """Обработка текущего этапа."""
        stage_id = self._current_stage_id
        
        if stage_id == "loading":
            await self._do_loading(data)
        elif stage_id == "processing":
            await self._do_processing(data)
        elif stage_id == "saving":
            await self._do_saving(data)
```

## Внутреннее устройство

### Расчет прогресса

Прогресс рассчитывается на основе:
1. **Базового прогресса этапа** из YAML конфигурации
2. **Текущего подэтапа** (если используются)

Формула для этапов с подэтапами:
```
progress = base_progress + (substep / total_substeps) * progress_range
```

Где `progress_range` - разница между текущим и следующим этапом.

### Расчет ETA

ETA рассчитывается на основе:
- Прошедшего времени (`elapsed_time`)
- Текущего прогресса (`current_progress`)

Формула:
```
eta = (elapsed_time / current_progress) * (100 - current_progress)
```

### Состояние сервиса

Внутренние переменные:
```python
self._current_stage_id: str         # ID текущего этапа
self._current_stage_index: int      # Индекс в списке этапов (-1 = не начат)
self._current_substep: int          # Номер текущего подэтапа
self._current_total_substeps: int   # Общее количество подэтапов
self._start_time: float             # Время начала обработки
```

## Конфигурация этапов

Этапы определяются в YAML файлах в `src/config/services/stages/`:

```yaml
# video_processing_stages.yaml
stages:
  - id: video_loading
    name: "Загрузка видео"
    progress: 0

  - id: frame_extraction
    name: "Извлечение кадров"
    progress: 10

  - id: text_recognition
    name: "Распознавание текста"
    progress: 40

  - id: text_translation
    name: "Перевод текста"
    progress: 70

  - id: audio_generation
    name: "Генерация аудио"
    progress: 85

  - id: final_assembly
    name: "Финальная сборка"
    progress: 95
```

## Best Practices

### ✅ Рекомендуется

1. **Используйте `next_stage()` вместо `set_stage()`** для последовательной обработки
   ```python
   # ✅ ХОРОШО: автоматическое переключение
   self.next_stage()
   yield self.get_current_stage_message()
   
   # ❌ ПЛОХО: ручное указание (требует знания ID)
   self.set_stage("video_loading")
   yield self.get_current_stage_message()
   ```

2. **Всегда вызывайте `_start_tracking()`** в начале `execute_stream()`
   ```python
   async def execute_stream(self, data: dict):
       self._start_tracking()  # Важно для расчета ETA!
       # ...
   ```

3. **Используйте подэтапы для длительных операций**
   ```python
   self.next_stage(total_substeps=len(items))
   for item in items:
       process(item)
       self.increment_substep()
       yield self.get_current_stage_message(include_eta=True)
   ```

4. **Отправляйте ETA для долгих операций**
   ```python
   yield self.get_current_stage_message(include_eta=True)
   ```

5. **Обрабатывайте ошибки с контекстом**
   ```python
   except Exception as e:
       yield self.create_error_message(
           error_code="PROCESSING_FAILED",
           error_message=str(e),
           stage_failed=self._current_stage_id or "unknown"
       )
   ```

6. **Определяйте все этапы в YAML конфигурации**
   ```yaml
   # src/config/services/stages/my_service_stages.yaml
   stages:
     - id: loading
       progress: 0
     - id: processing
       progress: 50
     - id: saving
       progress: 90
   ```

### ❌ Не рекомендуется

1. **Не используйте `set_stage()` для последовательных этапов**
   ```python
   # ❌ ПЛОХО: требует знания всех ID этапов
   self.set_stage("video_loading")
   # ...
   self.set_stage("frame_extraction")
   # ...
   self.set_stage("text_recognition")
   
   # ✅ ХОРОШО: автоматическое переключение
   self.next_stage()
   # ...
   self.next_stage()
   # ...
   self.next_stage()
   ```

2. **Не забывайте устанавливать/переключать этапы**
   ```python
   # ❌ ПЛОХО: забыли вызвать next_stage() или set_stage()
   yield self.get_current_stage_message()  # Вернет stage="initializing"
   ```

3. **Не используйте подэтапы без total_substeps**
   ```python
   # ❌ ПЛОХО: increment_substep() не будет работать
   self.next_stage()  # total_substeps=0 по умолчанию
   self.increment_substep()  # Ничего не произойдет
   
   # ✅ ХОРОШО: указываем количество подэтапов
   self.next_stage(total_substeps=10)
   self.increment_substep()  # Работает корректно
   ```

4. **Не создавайте много мелких этапов вместо подэтапов**
   ```python
   # ❌ ПЛОХО: 100 этапов в YAML
   for i in range(100):
       self.set_stage(f"step_{i}")
   
   # ✅ ХОРОШО: один этап со 100 подэтапами
   self.next_stage(total_substeps=100)
   for i in range(100):
       self.increment_substep()
   ```

5. **Не смешивайте `next_stage()` и `set_stage()` без необходимости**
   ```python
   # ❌ ПЛОХО: непредсказуемое поведение
   self.next_stage()
   # ...
   self.set_stage("some_random_stage")  # Сбивает индекс
   # ...
   self.next_stage()  # Может перейти не к тому этапу
   
   # ✅ ХОРОШО: используйте один подход
   self.next_stage()
   # ...
   self.next_stage()
   # ...
   self.next_stage()
   ```

## Интеграция с существующим кодом

### Миграция на автоматическое переключение стадий

#### До (ручное создание сообщений):
```python
async def execute_stream(self, data: dict):
    yield self.create_progress_message(
        progress=10,
        stage="loading",
        status="processing"
    )
    # ...
    yield self.create_progress_message(
        progress=50,
        stage="processing",
        status="processing",
        details={"current_step": 5, "total_steps": 10}
    )
```

#### Шаг 1 (переход на автоматический учет прогресса):
```python
async def execute_stream(self, data: dict):
    self._start_tracking()
    
    self.set_stage("loading")
    yield self.get_current_stage_message()
    
    # ...
    
    self.set_stage("processing", total_substeps=10)
    for i in range(10):
        self.increment_substep()
        yield self.get_current_stage_message(include_eta=True)
```

#### Шаг 2 (переход на автоматическое переключение) ⭐:
```python
async def execute_stream(self, data: dict):
    self._start_tracking()
    
    # Автоматическое переключение - не нужно знать ID этапов
    self.next_stage()
    yield self.get_current_stage_message()
    
    # ...
    
    self.next_stage(total_substeps=10)
    for i in range(10):
        self.increment_substep()
        yield self.get_current_stage_message(include_eta=True)
```

### Сравнение подходов

| Характеристика | Ручное создание | `set_stage()` | `next_stage()` ⭐ |
|---------------|----------------|---------------|------------------|
| Автоматический прогресс | ❌ | ✅ | ✅ |
| Нужно знать ID этапов | ✅ | ✅ | ❌ |
| Автоматический ETA | ❌ | ✅ | ✅ |
| Этапы из YAML | ❌ | ✅ | ✅ |
| Автопереключение | ❌ | ❌ | ✅ |
| Простота кода | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Поддерживаемость | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## Тестирование

Запустите пример для проверки:

```powershell
python example_auto_progress_service.py
```

Ожидаемый вывод:
```
=== Демонстрация автоматического учета прогресса ===

[  0%] video_loading
[ 10%] frame_extraction (1/10) | ETA: 2s
[ 13%] frame_extraction (2/10) | ETA: 2s
...
[100%] complete

✓ ЗАВЕРШЕНО: {'output_file': 'translated_video.mp4', 'duration': 6.5}
```

## Дополнительные ресурсы

- [ServiceStageDefinition](../src/services/service_stages.py) - Определение этапов
- [stage_config_loader.py](../src/services/stage_config_loader.py) - Загрузка конфигураций
- [Примеры конфигураций](../src/config/services/stages/) - YAML файлы этапов
