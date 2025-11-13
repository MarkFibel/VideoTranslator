/**
 * API Controller
 * 
 * Отвечает за взаимодействие с backend API.
 * 
 * События:
 * - Слушает: form:submit
 * - Генерирует: api:submit, api:success, api:error, api:network-error
 *               api:sse-start, api:sse-progress, api:sse-complete, api:sse-error
 */

// static/js/controllers/hello_controller.js
const { Controller } = Stimulus;
import SSEHelper from '../helpers/sseHelper.js';

export default class extends Controller {
    static values = {
        endpoint: String,
        csrfToken: String
    };

    /**
     * Инициализация контроллера
     * Подписка на события отправки формы
     */
    connect() {
        this.element.addEventListener('form:submit', this.submitForm.bind(this));

        // Отправляем событие готовности контроллера
        this.dispatchControllerReady();
    }

    /**
     * Отключение контроллера
     * Очистка слушателей событий
     */
    disconnect() {
        this.element.removeEventListener('form:submit', this.submitForm.bind(this));

        // Отменяем загрузку если она в процессе
        this.cancelUpload();
    }

    /**
     * Главный метод обработки отправки формы
     * Слушает событие form:submit от formController
     * Автоматически определяет наличие файлов и использует соответствующий метод отправки
     * 
     * @param {CustomEvent} event - Событие с данными формы
     * @param {string} event.detail.endpoint - URL для отправки
     * @param {Object} event.detail.payload - Данные формы
     * @param {File} event.detail.file - Файл для загрузки (опционально)
     * @param {string} event.detail.csrfToken - CSRF токен
     */
    async submitForm(event) {
        const requestId = this.generateRequestId();
        const timestamp = new Date().toISOString();

        console.log(`[${timestamp}] 🎯 ApiController [${requestId}] submitForm вызван`, {
            hasEvent: !!event,
            hasDetail: !!event.detail
        });

        const { endpoint, payload, file, csrfToken } = event.detail;

        console.log(`[${timestamp}] 🎯 ApiController [${requestId}] Параметры события`, {
            endpoint,
            hasPayload: !!payload,
            hasFile: !!file,
            fileName: file?.name,
            hasCsrfToken: !!csrfToken
        });

        // Используем endpoint из события или из data-атрибута
        const targetEndpoint = endpoint || this.endpointValue;
        const token = csrfToken || this.csrfTokenValue;

        console.log(`[${timestamp}] 🎯 ApiController [${requestId}] Целевой endpoint: ${targetEndpoint}`);

        // Если endpoint не указан или равен '#', имитируем успешную отправку
        // Это используется для интеграции с Битрикс24, где форма отображается 
        // в iframe без реальной отправки данных
        if (!targetEndpoint || targetEndpoint === '#') {
            this.simulateSuccess(payload);
            return;
        }

        // Проверяем, нужно ли использовать SSE
        const useSSE = this.shouldUseSSE(targetEndpoint, file);

        if (useSSE) {
            console.log(`[${timestamp}] 📡 ApiController [${requestId}] Используем SSE для загрузки`);
            return this.submitWithSSE(targetEndpoint, payload, file, token, requestId, timestamp);
        }

        // Если есть файл - используем XMLHttpRequest с прогрессом
        if (file) {
            console.log(`[${timestamp}] 📤 ApiController [${requestId}] Обнаружен файл, используем XMLHttpRequest`);
            return this.submitWithFile(targetEndpoint, payload, file, token, requestId, timestamp);
        }

        // Иначе используем обычный fetch для JSON
        console.log(`[${timestamp}] 📤 ApiController [${requestId}] Отправка JSON данных`);
        return this.submitWithoutFile(targetEndpoint, payload, token, requestId, timestamp);
    }

    /**
     * Определяет, нужно ли использовать SSE для данного запроса
     * 
     * @param {string} endpoint - URL endpoint
     * @param {File} file - Файл для загрузки
     * @returns {boolean}
     */
    shouldUseSSE(endpoint, file) {
        // SSE используется для endpoints с /stream и при наличии файла
        return file && endpoint && endpoint.includes('/stream');
    }

    /**
     * Отправка данных без файла (JSON)
     * 
     * @param {string} targetEndpoint - URL для отправки
     * @param {Object} payload - Данные формы
     * @param {string} token - CSRF токен
     * @param {string} requestId - ID запроса
     * @param {string} timestamp - Временная метка
     */
    async submitWithoutFile(targetEndpoint, payload, token, requestId, timestamp) {
        // Диспатчим событие начала отправки
        this.dispatchSubmit(targetEndpoint, payload);

        try {
            // Добавляем CSRF токен клиента в payload
            const payloadWithToken = {
                ...payload,
                _csrf_token: token
            };

            // Отправляем запрос
            const response = await fetch(targetEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token && { 'X-CSRF-Token': token })
                },
                body: JSON.stringify({ data: payloadWithToken })
            });

            // Парсим ответ
            let result;
            try {
                result = await response.json();
            } catch (parseError) {
                console.error(`[${timestamp}] ❌ ApiController [${requestId}] Ошибка парсинга JSON`, {
                    error: parseError.message,
                    responseText: response.text ? '(text mode)' : 'N/A'
                });
                throw new Error('Сервер вернул некорректный ответ');
            }

            // Обработка успешного ответа
            if (response.ok && result.success !== false) {
                this.dispatchSuccess(result, targetEndpoint);
            }
            // Обработка ошибки валидации или бизнес-логики
            else {
                console.warn(`[${timestamp}] ⚠️  ApiController [${requestId}] Ошибка валидации/бизнес-логики - диспатчим api:error`, {
                    status: response.status,
                    success: result.success,
                    message: result.message
                });
                this.dispatchError(result, response.status);
            }
        } catch (error) {
            // Обработка сетевой ошибки или исключения
            console.error(`[${timestamp}] 💥 ApiController [${requestId}] КРИТИЧЕСКАЯ ОШИБКА`, {
                error: error.message,
                stack: error.stack
            });
            this.dispatchNetworkError(error, this.getNetworkErrorMessage(error));
        }
    }

    /**
     * Отправка данных с файлом через XMLHttpRequest с отслеживанием прогресса
     * 
     * @param {string} targetEndpoint - URL для отправки
     * @param {Object} payload - Данные формы
     * @param {File} file - Файл для загрузки
     * @param {string} token - CSRF токен
     * @param {string} requestId - ID запроса
     * @param {string} timestamp - Временная метка
     */
    async submitWithFile(targetEndpoint, payload, file, token, requestId, timestamp) {
        console.log(`[${timestamp}] 🚀 ApiController [${requestId}] submitWithFile вызван`, {
            targetEndpoint,
            fileName: file.name,
            fileSize: file.size
        });

        // Диспатчим событие начала отправки
        this.dispatchSubmit(targetEndpoint, { _fileUpload: true, fileName: file.name });

        return new Promise((resolve, reject) => {
            console.log(`[${timestamp}] 🔨 ApiController [${requestId}] Создание XMLHttpRequest`);
            const xhr = new XMLHttpRequest();

            // Создаем FormData
            const formData = new FormData();
            // Сервер ожидает параметр 'file'
            formData.append('file', file);

            // Добавляем остальные поля из payload
            for (const [key, value] of Object.entries(payload)) {
                if (value !== undefined && value !== null) {
                    formData.append(key, value);
                }
            }

            console.log(`[${timestamp}] 📦 ApiController [${requestId}] FormData подготовлен`, {
                fileName: file.name,
                fileSize: file.size,
                payloadKeys: Object.keys(payload)
            });

            // Добавляем CSRF токен
            if (token) {
                formData.append('_csrf_token', token);
            }

            // Обработчик прогресса загрузки
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);

                    console.log(`[${timestamp}] 📊 ApiController [${requestId}] Прогресс загрузки: ${percentComplete}%`);

                    // Диспатчим событие прогресса
                    this.dispatchProgress(percentComplete, e.loaded, e.total);
                }
            });

            // Обработчик завершения загрузки
            xhr.addEventListener('load', () => {
                console.log(`[${timestamp}] ✅ ApiController [${requestId}] Загрузка завершена, статус: ${xhr.status}`);

                try {
                    // Парсим ответ
                    let result;
                    try {
                        result = JSON.parse(xhr.responseText);
                    } catch (parseError) {
                        console.error(`[${timestamp}] ❌ ApiController [${requestId}] Ошибка парсинга JSON`, {
                            error: parseError.message,
                            responseText: xhr.responseText.substring(0, 200)
                        });
                        this.dispatchError({
                            message: 'Сервер вернул некорректный ответ',
                            errors: {}
                        }, xhr.status);
                        reject(new Error('Сервер вернул некорректный ответ'));
                        return;
                    }

                    // Обработка успешного ответа
                    if (xhr.status >= 200 && xhr.status < 300 && result.success !== false) {
                        console.log(`[${timestamp}] 🎉 ApiController [${requestId}] Файл успешно загружен`);
                        this.dispatchSuccess(result, targetEndpoint);
                        resolve(result);
                    }
                    // Обработка ошибки валидации или бизнес-логики
                    else {
                        console.warn(`[${timestamp}] ⚠️  ApiController [${requestId}] Ошибка при загрузке файла`, {
                            status: xhr.status,
                            success: result.success,
                            message: result.message
                        });
                        this.dispatchError(result, xhr.status);
                        reject(new Error(result.message || 'Ошибка при загрузке файла'));
                    }
                } catch (error) {
                    console.error(`[${timestamp}] 💥 ApiController [${requestId}] Критическая ошибка при обработке ответа`, {
                        error: error.message
                    });
                    this.dispatchNetworkError(error, 'Ошибка при обработке ответа сервера');
                    reject(error);
                }
            });

            // Обработчик ошибки сети
            xhr.addEventListener('error', () => {
                console.error(`[${timestamp}] 🌐❌ ApiController [${requestId}] Сетевая ошибка при загрузке файла`);
                const error = new Error('Ошибка сети при загрузке файла');
                this.dispatchNetworkError(error, this.getNetworkErrorMessage(error));
                reject(error);
            });

            // Обработчик отмены загрузки
            xhr.addEventListener('abort', () => {
                console.warn(`[${timestamp}] 🛑 ApiController [${requestId}] Загрузка файла отменена`);
                const error = new Error('Загрузка файла отменена');
                this.dispatchNetworkError(error, 'Загрузка была отменена');
                reject(error);
            });

            // Обработчик таймаута
            xhr.addEventListener('timeout', () => {
                console.error(`[${timestamp}] ⏱️  ApiController [${requestId}] Таймаут при загрузке файла`);
                const error = new Error('Превышено время ожидания загрузки');
                this.dispatchNetworkError(error, 'Превышено время ожидания. Попробуйте загрузить файл меньшего размера.');
                reject(error);
            });

            // Настройка запроса
            xhr.open('POST', targetEndpoint, true);

            // Добавляем CSRF токен в заголовок
            if (token) {
                xhr.setRequestHeader('X-CSRF-Token', token);
            }

            // Устанавливаем таймаут (10 минут для больших файлов)
            xhr.timeout = 600000;

            // Отправляем FormData
            console.log(`[${timestamp}] 🚀 ApiController [${requestId}] Отправляем запрос с файлом`);
            xhr.send(formData);

            // Сохраняем ссылку на xhr для возможной отмены
            this.currentUploadXhr = xhr;
        });
    }

    /**
     * Отменяет текущую загрузку файла
     */
    cancelUpload() {
        if (this.currentUploadXhr) {
            console.log('ApiController: Отмена загрузки файла');
            this.currentUploadXhr.abort();
            this.currentUploadXhr = null;
        }
    }

    /**
     * Диспатчит событие начала отправки
     * 
     * @param {string} endpoint - URL запроса
     * @param {Object} payload - Отправляемые данные
     */
    dispatchSubmit(endpoint, payload) {
        this.dispatch('submit', {
            detail: {
                endpoint,
                payload
            }
        });
    }

    /**
     * Диспатчит событие прогресса загрузки файла
     * 
     * @param {number} percent - Процент загрузки (0-100)
     * @param {number} loaded - Загружено байт
     * @param {number} total - Всего байт
     */
    dispatchProgress(percent, loaded, total) {
        this.dispatch('progress', {
            detail: {
                percent,
                loaded,
                total
            }
        });
    }

    /**
     * Имитирует успешную отправку формы без реального HTTP-запроса
     * Используется когда endpoint не указан или равен '#'
     * 
     * @param {Object} payload - Данные формы
     */
    simulateSuccess(payload) {
        // Небольшая задержка для имитации сетевого запроса
        setTimeout(() => {
            this.dispatch('submit', {
                detail: {
                    endpoint: '#',
                    payload
                }
            });

            // Через 300ms диспатчим успешный результат
            setTimeout(() => {
                this.dispatchSuccess({
                    success: true,
                    message: 'Форма успешно заполнена',
                    data: payload
                }, '#');
            }, 300);
        }, 100);
    }

    /**
     * Диспатчит событие успешного ответа
     * 
     * @param {Object} result - Ответ от сервера
     * @param {string} endpoint - URL запроса
     */
    dispatchSuccess(result, endpoint) {
        this.dispatch('success', {
            detail: {
                message: result.message || 'Операция выполнена успешно',
                data: result.data || result,
                endpoint
            }
        });
    }

    /**
     * Диспатчит событие ошибки валидации/бизнес-логики
     * 
     * @param {Object} result - Ответ от сервера с ошибками
     * @param {number} status - HTTP статус код
     */
    dispatchError(result, status) {
        const timestamp = new Date().toISOString();
        console.warn(`[${timestamp}] 🛑 ApiController.dispatchError - диспатчим событие api:error`, {
            message: result.message || 'Произошла ошибка при обработке запроса',
            hasErrors: !!result.errors,
            status: status,
            repeat: result.repeat
        });

        this.dispatch('error', {
            detail: {
                message: result.message || 'Произошла ошибка при обработке запроса',
                errors: result.errors || {},
                repeat: result.repeat,  // НОВОЕ: можно ли повторить запрос (без дефолта!)
                error_type: result.error_type || 'unknown',  // НОВОЕ: тип ошибки
                captcha_retry: result.captcha_retry || false,  // Требуется ли новая капча
                status: status
            }
        });
    }

    /**
     * Диспатчит событие сетевой ошибки
     * 
     * @param {Error} error - Объект ошибки
     * @param {string} message - Пользовательское сообщение
     */
    dispatchNetworkError(error, message) {
        const timestamp = new Date().toISOString();
        console.error(`[${timestamp}] 🌐❌ ApiController.dispatchNetworkError - диспатчим событие api:network-error`, {
            error: error.message,
            userMessage: message || 'Ошибка соединения. Проверьте интернет и попробуйте снова.'
        });

        this.dispatch('network-error', {
            detail: {
                error,
                message: message || 'Ошибка соединения. Проверьте интернет и попробуйте снова.'
            }
        });
    }

    /**
     * Вспомогательный метод для диспатчинга событий
     * Все события имеют префикс 'api:'
     * 
     * @param {string} eventName - Название события (без префикса)
     * @param {Object} options - Опции события (detail, bubbles, cancelable)
     */
    dispatch(eventName, options = {}) {
        const event = new CustomEvent(`api:${eventName}`, {
            bubbles: true,
            cancelable: true,
            ...options
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Генерирует уникальный ID для запроса (для логирования)
     * @returns {string} - Уникальный ID в формате XXXX-XXXX
     */
    generateRequestId() {
        return `${Math.random().toString(16).substr(2, 4)}-${Math.random().toString(16).substr(2, 4)}`.toUpperCase();
    }

    /**
     * Запрос к DaData API для получения данных компании по ИНН
     * 
     * @param {string} inn - ИНН для поиска
     * @param {string} dadataEndpoint - URL эндпоинта DaData
     * @param {string} csrfToken - CSRF токен
     * @returns {Promise<Object>} - Результат запроса { success: boolean, data?: Object, error?: string }
     */
    async fetchDadata(inn, dadataEndpoint, csrfToken) {
        try {
            const response = await fetch(dadataEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    inn: inn,
                    _csrf_token: csrfToken
                })
            });

            const result = await response.json();

            if (!response.ok) {
                console.error('ApiController: ошибка DaData API', { status: response.status, result });
                return {
                    success: false,
                    error: result.error || 'Ошибка при запросе к DaData'
                };
            }

            // Проверяем наличие данных компании в ответе
            if (result.suggestions && result.suggestions.length > 0) {
                const companyData = result.suggestions[0].data;

                return {
                    success: true,
                    data: {
                        companyName: companyData.name?.short_with_opf || companyData.name?.full_with_opf || '',
                        inn: companyData.inn,
                        kpp: companyData.kpp,
                        ogrn: companyData.ogrn,
                        address: companyData.address?.value || ''
                    }
                };
            } else {
                return {
                    success: false,
                    error: 'Компания не найдена'
                };
            }
        } catch (error) {
            console.error('ApiController: ошибка запроса к DaData', error);
            return {
                success: false,
                error: this.getNetworkErrorMessage(error)
            };
        }
    }

    /**
     * Отправка данных с файлом через SSE
     * 
     * @param {string} targetEndpoint - URL для отправки
     * @param {Object} payload - Данные формы
     * @param {File} file - Файл для загрузки
     * @param {string} token - CSRF токен
     * @param {string} requestId - ID запроса
     * @param {string} timestamp - Временная метка
     */
    async submitWithSSE(targetEndpoint, payload, file, token, requestId, timestamp) {
        console.log(`[${timestamp}] 🚀 ApiController [${requestId}] submitWithSSE вызван`, {
            targetEndpoint,
            fileName: file.name,
            fileSize: file.size
        });

        // Диспатчим событие начала SSE загрузки
        this.dispatchSSEStart(targetEndpoint, payload);

        try {
            // Создаем FormData
            const formData = new FormData();
            formData.append('file', file);

            // Добавляем остальные поля из payload
            for (const [key, value] of Object.entries(payload)) {
                if (value !== undefined && value !== null) {
                    formData.append(key, value);
                }
            }

            // Добавляем CSRF токен
            if (token) {
                formData.append('_csrf_token', token);
            }

            console.log(`[${timestamp}] 📡 ApiController [${requestId}] Устанавливаем SSE соединение...`);

            // Используем SSEHelper для установки соединения
            await SSEHelper.connect(targetEndpoint, {
                body: formData,
                headers: {
                    ...(token && { 'X-CSRF-Token': token })
                },
                onProgress: (data) => {
                    console.log(`[${timestamp}] 📊 ApiController [${requestId}] SSE Progress: ${data.progress}% at stage ${data.stage}`);
                    this.dispatchSSEProgress(data);
                },
                onComplete: (data) => {
                    console.log(`[${timestamp}] ✅ ApiController [${requestId}] SSE Complete`);
                    this.dispatchSSEComplete(data);
                },
                onError: (error) => {
                    console.error(`[${timestamp}] ❌ ApiController [${requestId}] SSE Error:`, error);
                    this.dispatchSSEError(error);
                }
            });

        } catch (error) {
            console.error(`[${timestamp}] 💥 ApiController [${requestId}] КРИТИЧЕСКАЯ ОШИБКА SSE`, {
                error: error.message,
                stack: error.stack
            });
            this.dispatchNetworkError(error, this.getNetworkErrorMessage(error));
        }
    }

    /**
     * Диспатчит событие начала SSE загрузки
     * 
     * @param {string} endpoint - URL endpoint
     * @param {Object} payload - Данные формы
     */
    dispatchSSEStart(endpoint, payload) {
        const event = new CustomEvent('api:sse-start', {
            bubbles: true,
            detail: { endpoint, payload }
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Диспатчит событие SSE прогресса
     * 
     * @param {Object} data - Данные прогресса {progress, stage, ...}
     */
    dispatchSSEProgress(data) {
        const event = new CustomEvent('api:sse-progress', {
            bubbles: true,
            detail: data
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Диспатчит событие завершения SSE
     * 
     * @param {Object} data - Данные результата
     */
    dispatchSSEComplete(data) {
        const event = new CustomEvent('api:sse-complete', {
            bubbles: true,
            detail: data
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Диспатчит событие ошибки SSE
     * 
     * @param {Object} error - Объект ошибки
     */
    dispatchSSEError(error) {
        const event = new CustomEvent('api:sse-error', {
            bubbles: true,
            detail: error
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Формирует понятное сообщение об ошибке для пользователя
     * 
     * @param {Error} error - Объект ошибки
     * @returns {string} - Сообщение для пользователя
     */
    getNetworkErrorMessage(error) {
        if (!navigator.onLine) {
            return 'Отсутствует подключение к интернету. Проверьте ваше соединение.';
        }

        if (error.message === 'Failed to fetch') {
            return 'Не удалось соединиться с сервером. Проверьте интернет-соединение.';
        }

        if (error.name === 'AbortError') {
            return 'Запрос был отменен. Попробуйте снова.';
        }

        if (error.message.includes('JSON')) {
            return 'Сервер вернул некорректные данные. Обратитесь к администратору.';
        }

        return error.message || 'Произошла неизвестная ошибка. Попробуйте позже.';
    }

    /**
     * Отправляет событие готовности контроллера
     */
    dispatchControllerReady() {
        const event = new CustomEvent('controller:ready', {
            bubbles: true,
            cancelable: false,
            detail: {
                controllerName: 'api'
            }
        });
        this.element.dispatchEvent(event);
    }
}
