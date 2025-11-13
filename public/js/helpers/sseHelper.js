/**
 * SSE Helper - Утилита для работы с Server-Sent Events
 * 
 * Инкапсулирует логику подключения к SSE endpoint'ам,
 * чтения потока событий и парсинга SSE формата.
 * 
 * @example
 * await SSEHelper.connect('/files/upload/stream', {
 *     body: formData,
 *     onProgress: (data) => console.log(data.progress),
 *     onComplete: (data) => console.log('Done!'),
 *     onError: (error) => console.error(error)
 * });
 */

export class SSEHelper {
    /**
     * Устанавливает SSE соединение и читает поток событий
     * 
     * @param {string} url - URL SSE endpoint
     * @param {Object} options - Опции
     * @param {FormData} [options.body] - Данные для POST запроса
     * @param {Object} [options.headers] - Дополнительные заголовки
     * @param {Function} [options.onProgress] - Callback для progress событий
     * @param {Function} [options.onComplete] - Callback для complete события
     * @param {Function} [options.onError] - Callback для error событий
     * @param {Function} [options.onMessage] - Callback для custom событий
     * @param {AbortSignal} [options.signal] - AbortSignal для отмены
     * @returns {Promise<void>}
     * @throws {Error} При ошибках сети или сервера
     */
    static async connect(url, options = {}) {
        const {
            body = null,
            headers = {},
            onProgress = null,
            onComplete = null,
            onError = null,
            onMessage = null,
            signal = null
        } = options;

        console.log('[SSEHelper] Connecting to:', url);

        try {
            // Формируем опции запроса
            const fetchOptions = {
                method: body ? 'POST' : 'GET',
                headers: {
                    ...headers,
                    // НЕ устанавливаем Content-Type для FormData - браузер сделает это автоматически
                },
                credentials: 'include', // Включаем куки для сессий
            };

            // Добавляем body если есть
            if (body) {
                fetchOptions.body = body;
            }

            // Добавляем signal для отмены
            if (signal) {
                fetchOptions.signal = signal;
            }

            // Отправляем запрос
            const response = await fetch(url, fetchOptions);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Проверяем Content-Type
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('text/event-stream')) {
                console.warn('[SSEHelper] Warning: Response is not SSE stream:', contentType);
            }

            console.log('[SSEHelper] Connection established. Reading SSE stream...');

            // Читаем SSE поток
            await this.readSSEStream(response.body, {
                onProgress,
                onComplete,
                onError,
                onMessage
            });

        } catch (error) {
            console.error('[SSEHelper] Connection error:', error);

            // Если это ошибка отмены - не вызываем onError
            if (error.name === 'AbortError') {
                console.log('[SSEHelper] Connection aborted by user');
                return;
            }

            // Вызываем onError если задан
            if (onError) {
                onError({
                    error_code: 'CONNECTION_ERROR',
                    error_message: error.message,
                    stage_failed: 'connection'
                });
            }

            throw error;
        }
    }

    /**
     * Читает SSE поток из ReadableStream
     * 
     * @param {ReadableStream} stream - Поток для чтения
     * @param {Object} callbacks - Callback функции
     * @private
     */
    static async readSSEStream(stream, callbacks) {
        const { onProgress, onComplete, onError, onMessage } = callbacks;

        const reader = stream.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let chunkCount = 0;

        try {
            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log('[SSEHelper] Stream finished');
                    break;
                }

                chunkCount++;
                console.log(`[SSEHelper] Chunk ${chunkCount} received: ${value.length} bytes`);

                // Декодируем chunk
                const decoded = decoder.decode(value, { stream: true });
                buffer += decoded;

                // Обрабатываем полные SSE сообщения (разделенные \n\n)
                const messages = buffer.split('\n\n');
                buffer = messages.pop() || ''; // Сохраняем неполное сообщение

                console.log(`[SSEHelper] Processing ${messages.length} complete SSE messages`);

                for (const message of messages) {
                    if (!message.trim()) {
                        continue; // Пропускаем пустые сообщения
                    }

                    try {
                        const event = this.parseSSEMessage(message);
                        console.log(`[SSEHelper] Event [${event.type}]:`, event.data);

                        // Вызываем соответствующий callback
                        if (event.type === 'progress' && onProgress) {
                            onProgress(event.data);
                        } else if (event.type === 'complete' && onComplete) {
                            onComplete(event.data);
                        } else if (event.type === 'error' && onError) {
                            onError(event.data);
                        } else if (onMessage) {
                            // Для custom событий
                            onMessage(event);
                        }

                    } catch (parseError) {
                        console.error('[SSEHelper] Error parsing SSE message:', parseError);
                        console.error('[SSEHelper] Message:', message.substring(0, 200));
                    }
                }
            }

        } catch (error) {
            console.error('[SSEHelper] Stream reading error:', error);
            throw error;
        } finally {
            reader.releaseLock();
        }
    }

    /**
     * Парсит SSE формат в объект события
     * 
     * SSE формат:
     * event: progress
     * data: {"progress": 50, "stage": "processing"}
     * 
     * @param {string} message - SSE сообщение
     * @returns {Object} - {type: 'progress', data: {...}, id: '...', retry: ...}
     */
    static parseSSEMessage(message) {
        const lines = message.split('\n');
        let eventType = 'message'; // По умолчанию
        let eventData = '';
        let eventId = null;
        let retry = null;

        for (const line of lines) {
            if (line.startsWith('event: ')) {
                eventType = line.substring(7).trim();
            } else if (line.startsWith('data: ')) {
                eventData += line.substring(6);
            } else if (line.startsWith('id: ')) {
                eventId = line.substring(4).trim();
            } else if (line.startsWith('retry: ')) {
                retry = parseInt(line.substring(7).trim(), 10);
            }
        }

        // Парсим JSON из data
        let parsedData = null;
        if (eventData) {
            try {
                parsedData = JSON.parse(eventData);
            } catch (e) {
                console.warn('[SSEHelper] Failed to parse JSON data:', eventData);
                parsedData = { raw: eventData };
            }
        }

        return {
            type: eventType,
            data: parsedData,
            id: eventId,
            retry: retry
        };
    }

    /**
     * Создает AbortController для отмены SSE соединения
     * 
     * @returns {AbortController}
     * @example
     * const abortController = SSEHelper.createAbortController();
     * // ... позже
     * abortController.abort();
     */
    static createAbortController() {
        return new AbortController();
    }

    /**
     * Проверяет поддержку SSE в браузере
     * 
     * @returns {boolean}
     */
    static isSupported() {
        return typeof EventSource !== 'undefined' && 
               typeof ReadableStream !== 'undefined';
    }
}

// Экспортируем по умолчанию для совместимости
export default SSEHelper;
