// static/js/controllers/fileController.js
const { Controller } = Stimulus;

/**
 * File Controller
 * 
 * Управляет загрузкой и валидацией файлов:
 * - Валидация типа, размера файла
 * - Отображение информации о выбранном файле
 * - Прогресс-бар загрузки
 * - Очистка выбранного файла
 */
export default class extends Controller {
    static targets = [
        "container",
        "input",
        "dropzone",
        "fileInfo",
        "fileName",
        "fileDetails",
        "fileIcon",
        "error",
        "progress",
        "progressBar",
        "progressPercent",  // Новый target для текста процента
        "progressStage"     // Новый target для текста этапа
    ];

    static values = {
        maxSize: Number,           // Максимальный размер файла в байтах
        minSize: Number,           // Минимальный размер файла в байтах
        acceptedTypes: Array,      // Массив допустимых MIME-типов
        maxDuration: Number,       // Максимальная длительность видео (секунды)
        minDuration: Number,       // Минимальная длительность видео (секунды)
        maxWidth: Number,          // Максимальная ширина видео
        maxHeight: Number,         // Максимальная высота видео
        minWidth: Number,          // Минимальная ширина видео
        minHeight: Number          // Минимальная высота видео
    };

    connect() {
        console.log('FileController connected');

        // Устанавливаем обработчики для drag & drop
        this.setupDragAndDrop();

        // Слушаем события прогресса от formController
        this.boundUpdateProgress = this.updateProgress.bind(this);
        this.element.addEventListener('progress:update', this.boundUpdateProgress);
        console.log('[FileController] Added progress:update listener');

        // Уведомляем формController о готовности
        this.dispatchReadyEvent();
    }

    disconnect() {
        // Очищаем обработчики
        this.removeDragAndDrop();

        // Удаляем слушатель прогресса
        if (this.boundUpdateProgress) {
            this.element.removeEventListener('progress:update', this.boundUpdateProgress);
        }
    }

    /**
     * Настройка drag & drop функционала
     */
    setupDragAndDrop() {
        if (!this.hasDropzoneTarget) return;

        this.boundHandleDragOver = this.handleDragOver.bind(this);
        this.boundHandleDragLeave = this.handleDragLeave.bind(this);
        this.boundHandleDrop = this.handleDrop.bind(this);

        this.dropzoneTarget.addEventListener('dragover', this.boundHandleDragOver);
        this.dropzoneTarget.addEventListener('dragleave', this.boundHandleDragLeave);
        this.dropzoneTarget.addEventListener('drop', this.boundHandleDrop);
    }

    /**
     * Удаление обработчиков drag & drop
     */
    removeDragAndDrop() {
        if (!this.hasDropzoneTarget) return;

        this.dropzoneTarget.removeEventListener('dragover', this.boundHandleDragOver);
        this.dropzoneTarget.removeEventListener('dragleave', this.boundHandleDragLeave);
        this.dropzoneTarget.removeEventListener('drop', this.boundHandleDrop);
    }

    /**
     * Обработчик dragover
     */
    handleDragOver(event) {
        event.preventDefault();
        event.stopPropagation();
        this.dropzoneTarget.classList.add('dragover');
    }

    /**
     * Обработчик dragleave
     */
    handleDragLeave(event) {
        event.preventDefault();
        event.stopPropagation();
        this.dropzoneTarget.classList.remove('dragover');
    }

    /**
     * Обработчик drop
     */
    handleDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        this.dropzoneTarget.classList.remove('dragover');

        const files = event.dataTransfer.files;
        if (files.length > 0) {
            // Программно устанавливаем файл в input
            this.inputTarget.files = files;
            // Триггерим событие change
            this.inputTarget.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    /**
     * Обработчик изменения файла
     * @param {Event} event
     */
    async validateFile(event) {
        const file = this.inputTarget.files[0];

        if (!file) {
            this.clearFile();
            return;
        }

        // Очищаем предыдущие ошибки
        this.hideError();

        try {
            // Валидация размера файла
            if (this.hasMaxSizeValue && file.size > this.maxSizeValue) {
                throw new Error(`Размер файла превышает максимально допустимый (${this.formatFileSize(this.maxSizeValue)})`);
            }

            if (this.hasMinSizeValue && file.size < this.minSizeValue) {
                throw new Error(`Размер файла меньше минимально допустимого (${this.formatFileSize(this.minSizeValue)})`);
            }

            // Валидация типа файла
            if (this.hasAcceptedTypesValue && this.acceptedTypesValue.length > 0) {
                if (!this.acceptedTypesValue.includes(file.type)) {
                    throw new Error(`Недопустимый тип файла. Разрешены: ${this.acceptedTypesValue.join(', ')}`);
                }
            }

            // Если это видео или изображение - дополнительная валидация
            if (file.type.startsWith('video/') || file.type.startsWith('image/')) {
                await this.validateMediaFile(file);
            }

            // Показываем информацию о файле
            this.showFileInfo(file);

        } catch (error) {
            console.error('File validation error:', error);
            this.showError(error.message);
            this.inputTarget.value = '';
        }
    }

    /**
     * Валидация медиа-файлов (видео/изображение)
     * @param {File} file
     */
    async validateMediaFile(file) {
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(file);

            if (file.type.startsWith('video/')) {
                const video = document.createElement('video');
                video.preload = 'metadata';

                video.onloadedmetadata = () => {
                    URL.revokeObjectURL(url);

                    // Проверка длительности
                    if (this.hasMaxDurationValue && video.duration > this.maxDurationValue) {
                        reject(new Error(`Длительность видео превышает ${this.maxDurationValue} секунд`));
                        return;
                    }

                    if (this.hasMinDurationValue && video.duration < this.minDurationValue) {
                        reject(new Error(`Длительность видео меньше ${this.minDurationValue} секунд`));
                        return;
                    }

                    // Проверка разрешения
                    if (this.hasMaxWidthValue && video.videoWidth > this.maxWidthValue) {
                        reject(new Error(`Ширина видео превышает ${this.maxWidthValue}px`));
                        return;
                    }

                    if (this.hasMaxHeightValue && video.videoHeight > this.maxHeightValue) {
                        reject(new Error(`Высота видео превышает ${this.maxHeightValue}px`));
                        return;
                    }

                    if (this.hasMinWidthValue && video.videoWidth < this.minWidthValue) {
                        reject(new Error(`Ширина видео меньше ${this.minWidthValue}px`));
                        return;
                    }

                    if (this.hasMinHeightValue && video.videoHeight < this.minHeightValue) {
                        reject(new Error(`Высота видео меньше ${this.minHeightValue}px`));
                        return;
                    }

                    resolve();
                };

                video.onerror = () => {
                    URL.revokeObjectURL(url);
                    reject(new Error('Не удалось прочитать видео файл'));
                };

                video.src = url;
            } else {
                resolve();
            }
        });
    }

    /**
     * Отображение информации о файле
     * @param {File} file
     */
    showFileInfo(file) {
        // Устанавливаем имя файла
        if (this.hasFileNameTarget) {
            this.fileNameTarget.textContent = file.name;
        }

        // Устанавливаем детали файла
        if (this.hasFileDetailsTarget) {
            const details = [
                this.formatFileSize(file.size),
                file.type || 'Неизвестный тип'
            ];
            this.fileDetailsTarget.textContent = details.join(' • ');
        }

        // Обновляем иконку файла
        if (this.hasFileIconTarget) {
            this.updateFileIcon(file.type);
        }

        // Плавная анимация перехода
        // 1. Скрываем дропзону
        if (this.hasDropzoneTarget) {
            this.dropzoneTarget.classList.add('hidden');
        }

        // 2. Небольшая задержка, затем показываем информацию о файле
        setTimeout(() => {
            this.fileInfoTarget.classList.remove('d-none');
            // Триггерим reflow для корректной анимации
            this.fileInfoTarget.offsetHeight;
            this.fileInfoTarget.classList.add('visible');
        }, 200);
    }

    /**
     * Обновление иконки файла в зависимости от типа
     * @param {string} mimeType
     */
    updateFileIcon(mimeType) {
        const iconElement = this.fileIconTarget;

        // Очищаем предыдущее содержимое
        iconElement.innerHTML = '';
        iconElement.className = 'file-icon';

        if (mimeType.startsWith('video/')) {
            // Для видео создаём превью из первого кадра
            this.createVideoThumbnail(this.inputTarget.files[0], iconElement);
        } else if (mimeType.startsWith('image/')) {
            // Для изображений показываем само изображение
            this.createImagePreview(this.inputTarget.files[0], iconElement);
        } else if (mimeType.startsWith('audio/')) {
            // Для аудио используем SVG иконку
            iconElement.innerHTML = this.getAudioIcon();
        } else {
            // Для остальных файлов используем общую иконку
            iconElement.innerHTML = this.getFileIcon();
        }
    }

    /**
     * Создаёт превью видео из первого кадра
     * @param {File} file
     * @param {HTMLElement} container
     */
    createVideoThumbnail(file, container) {
        const video = document.createElement('video');
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const url = URL.createObjectURL(file);

        video.preload = 'metadata';
        video.muted = true;
        video.playsInline = true;

        video.onloadedmetadata = () => {
            // Устанавливаем время на 1 секунду (или начало если видео короче)
            video.currentTime = Math.min(1, video.duration / 2);
        };

        video.onseeked = () => {
            // Устанавливаем размер canvas
            const maxSize = 80;
            const scale = Math.min(maxSize / video.videoWidth, maxSize / video.videoHeight);
            canvas.width = video.videoWidth * scale;
            canvas.height = video.videoHeight * scale;

            // Рисуем кадр на canvas
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            // Создаём img элемент с превью
            const img = document.createElement('img');
            img.src = canvas.toDataURL();
            img.alt = 'Video preview';
            img.className = 'file-preview-image';

            // Добавляем иконку play поверх превью
            const playIcon = document.createElement('div');
            playIcon.className = 'file-preview-play';
            playIcon.innerHTML = '▶';

            container.innerHTML = '';
            container.appendChild(img);
            container.appendChild(playIcon);

            // Очищаем ресурсы
            URL.revokeObjectURL(url);
            video.remove();
        };

        video.onerror = () => {
            // В случае ошибки показываем иконку видео
            container.innerHTML = this.getVideoIcon();
            URL.revokeObjectURL(url);
        };

        video.src = url;
    }

    /**
     * Создаёт превью изображения
     * @param {File} file
     * @param {HTMLElement} container
     */
    createImagePreview(file, container) {
        const reader = new FileReader();

        reader.onload = (e) => {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.alt = 'Image preview';
            img.className = 'file-preview-image';

            container.innerHTML = '';
            container.appendChild(img);
        };

        reader.onerror = () => {
            // В случае ошибки показываем иконку изображения
            container.innerHTML = this.getImageIcon();
        };

        reader.readAsDataURL(file);
    }

    /**
     * SVG иконка видео
     * @returns {string}
     */
    getVideoIcon() {
        return `
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="5" width="20" height="14" rx="2" stroke="currentColor" stroke-width="2"/>
                <path d="M10 9L15 12L10 15V9Z" fill="currentColor"/>
            </svg>
        `;
    }

    /**
     * SVG иконка изображения
     * @returns {string}
     */
    getImageIcon() {
        return `
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/>
                <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor"/>
                <path d="M21 15L16 10L5 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        `;
    }

    /**
     * SVG иконка аудио
     * @returns {string}
     */
    getAudioIcon() {
        return `
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 18V5L21 3V16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="6" cy="18" r="3" stroke="currentColor" stroke-width="2"/>
                <circle cx="18" cy="16" r="3" stroke="currentColor" stroke-width="2"/>
            </svg>
        `;
    }

    /**
     * SVG иконка файла
     * @returns {string}
     */
    getFileIcon() {
        return `
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    }

    /**
     * Очистка выбранного файла
     */
    clearFile() {
        // Очищаем input
        this.inputTarget.value = '';

        // Плавная анимация перехода
        // 1. Скрываем информацию о файле
        if (this.hasFileInfoTarget) {
            this.fileInfoTarget.classList.remove('visible');
        }

        // 2. После анимации скрытия показываем дропзону
        setTimeout(() => {
            if (this.hasFileInfoTarget) {
                this.fileInfoTarget.classList.add('d-none');
            }

            // Показываем дропзону обратно
            if (this.hasDropzoneTarget) {
                this.dropzoneTarget.classList.remove('hidden');
            }
        }, 400);

        // Очищаем ошибки
        this.hideError();

        // Скрываем прогресс
        this.hideProgress();
    }

    /**
     * Отображение ошибки
     * @param {string} message
     */
    showError(message) {
        if (this.hasErrorTarget) {
            this.errorTarget.textContent = message;
            this.errorTarget.classList.remove('d-none');
            this.errorTarget.style.display = 'block';
        }

        // Добавляем класс ошибки к input
        this.inputTarget.classList.add('is-invalid');
    }

    /**
     * Скрытие ошибки
     */
    hideError() {
        if (this.hasErrorTarget) {
            this.errorTarget.classList.add('d-none');
            this.errorTarget.style.display = 'none';
        }

        // Убираем класс ошибки у input
        this.inputTarget.classList.remove('is-invalid');
    }

    /**
     * Показать прогресс-бар
     * @param {number} percent - Прогресс в процентах (0-100)
     */
    showProgress(percent = 0) {
        if (this.hasProgressTarget) {
            this.progressTarget.classList.remove('d-none');
        }

        if (this.hasProgressBarTarget) {
            this.progressBarTarget.style.width = `${percent}%`;
        }
    }

    /**
     * Обновить прогресс-бар (новая версия для SSE)
     * @param {CustomEvent|number} eventOrPercent - Событие с данными прогресса или просто процент
     */
    updateProgress(eventOrPercent) {
        console.log('[FileController] updateProgress called with:', eventOrPercent);

        // Поддержка старого API (число)
        if (typeof eventOrPercent === 'number') {
            const percent = eventOrPercent;
            console.log('[FileController] Using old API (number):', percent);
            // Показываем прогресс-бар если он скрыт
            this.showProgress(percent);
            return;
        }

        // Новый API для SSE (событие)
        const event = eventOrPercent;
        const { progress, stage } = event.detail || {};

        console.log('[FileController] SSE Progress update:', { 
            progress, 
            stage,
            hasProgressTarget: this.hasProgressTarget,
            hasProgressBarTarget: this.hasProgressBarTarget,
            hasProgressPercentTarget: this.hasProgressPercentTarget,
            hasProgressStageTarget: this.hasProgressStageTarget
        });

        // Показываем прогресс-бар если он скрыт
        if (this.hasProgressTarget) {
            console.log('[FileController] Removing d-none from progress');
            this.progressTarget.classList.remove('d-none');
        } else {
            console.warn('[FileController] progressTarget not found!');
        }

        // Обновляем прогресс-бар
        if (this.hasProgressBarTarget && progress !== undefined) {
            console.log('[FileController] Setting progress bar width to', progress + '%');
            this.progressBarTarget.style.width = `${progress}%`;
        }

        // Обновляем текст процента
        if (this.hasProgressPercentTarget && progress !== undefined) {
            console.log('[FileController] Setting progress percent text to', progress + '%');
            this.progressPercentTarget.textContent = `${progress}%`;
        }

        // Обновляем название этапа
        if (this.hasProgressStageTarget && stage) {
            const stageLabel = this.getStageLabel(stage);
            console.log('[FileController] Setting stage label to', stageLabel);
            this.progressStageTarget.textContent = stageLabel;
        }
    }

    /**
     * Получить человекочитаемое название этапа
     * @param {string} stage - Техническое имя этапа
     * @returns {string} - Человекочитаемое название
     */
    getStageLabel(stage) {
        // Пытаемся получить перевод из languageController
        const i18nKey = `stage-${stage}`;
        
        // Ищем languageController
        const languageElement = document.querySelector('[data-controller*="language"]');
        if (languageElement) {
            const languageController = this.application.getControllerForElementAndIdentifier(
                languageElement,
                'language'
            );
            
            if (languageController && typeof languageController.getTranslation === 'function') {
                const translation = languageController.getTranslation(i18nKey);
                if (translation) {
                    return translation;
                }
            }
        }

        // Fallback: используем встроенный словарь (русский)
        const stageLabels = {
            'initializing': 'Инициализация',
            'file_saved': 'Файл сохранен',
            'copying_file': 'Копирование файла',
            'splitting_frames': 'Разбиение на кадры',
            'extracting_audio': 'Извлечение аудио',
            'recognizing_speech': 'Распознавание речи',
            'translating_text': 'Перевод текста',
            'generating_tts': 'Генерация озвучки',
            'processing_frames': 'Обработка видеокадров',
            'assembling_video': 'Сборка финального видео',
            'complete': 'Обработка завершена'
        };

        return stageLabels[stage] || stage || 'Обработка...';
    }

    /**
     * Скрыть прогресс-бар
     */
    hideProgress() {
        if (this.hasProgressTarget) {
            this.progressTarget.classList.add('d-none');
        }

        if (this.hasProgressBarTarget) {
            this.progressBarTarget.style.width = '0%';
        }
    }

    /**
     * Форматирование размера файла
     * @param {number} bytes
     * @returns {string}
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Получение выбранного файла
     * @returns {File|null}
     */
    getFile() {
        return this.inputTarget.files[0] || null;
    }

    /**
     * Диспатч события готовности контроллера
     */
    dispatchReadyEvent() {
        const event = new CustomEvent('controller:ready', {
            bubbles: true,
            cancelable: false,
            detail: {
                controllerName: 'file'
            }
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Восстанавливает информацию о файле из сессии
     * @param {Object} fileData - Данные файла из сессии {filename, size, upload_time}
     */
    restoreFromSession(fileData) {
        const timestamp = new Date().toISOString();
        console.log(`[${timestamp}] 🔄 FileController.restoreFromSession`, fileData);

        if (!fileData || !fileData.filename) {
            console.warn(`[${timestamp}] ⚠️  Некорректные данные файла`);
            return;
        }

        // Устанавливаем имя файла
        if (this.hasFileNameTarget) {
            this.fileNameTarget.textContent = fileData.filename;
        }

        // Устанавливаем детали файла
        if (this.hasFileDetailsTarget) {
            const details = [];
            
            // Размер файла
            if (fileData.size) {
                details.push(this.formatFileSize(fileData.size));
            }
            
            // Время загрузки
            if (fileData.upload_time) {
                const uploadDate = new Date(fileData.upload_time);
                details.push(uploadDate.toLocaleString('ru-RU'));
            }

            this.fileDetailsTarget.textContent = details.join(' • ');
        }

        // Определяем иконку по расширению файла
        if (this.hasFileIconTarget) {
            const extension = fileData.filename.split('.').pop().toLowerCase();
            this.updateFileIconByExtension(extension);
        }

        // Показываем информацию о файле
        // 1. Скрываем дропзону
        if (this.hasDropzoneTarget) {
            this.dropzoneTarget.classList.add('hidden');
        }

        // 2. Показываем информацию о файле
        if (this.hasFileInfoTarget) {
            this.fileInfoTarget.classList.remove('d-none');
            // Триггерим reflow для корректной анимации
            this.fileInfoTarget.offsetHeight;
            this.fileInfoTarget.classList.add('visible');
        }

        console.log(`[${timestamp}] ✅ Файл восстановлен из сессии`);
    }

    /**
     * Обновляет иконку файла по расширению (без доступа к File объекту)
     * @param {string} extension - Расширение файла (без точки)
     */
    updateFileIconByExtension(extension) {
        const iconElement = this.fileIconTarget;
        
        // Очищаем предыдущее содержимое
        iconElement.innerHTML = '';
        iconElement.className = 'file-icon';

        // Определяем тип файла по расширению
        const videoExtensions = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv'];
        const audioExtensions = ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a'];
        const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'];

        if (videoExtensions.includes(extension)) {
            iconElement.innerHTML = this.getVideoIcon();
        } else if (audioExtensions.includes(extension)) {
            iconElement.innerHTML = this.getAudioIcon();
        } else if (imageExtensions.includes(extension)) {
            iconElement.innerHTML = this.getImageIcon();
        } else {
            iconElement.innerHTML = this.getFileIcon();
        }
    }
}
