// static/js/controllers/hello_controller.js
const { Controller } = Stimulus;

/**
 * Captcha Controller
 * 
 * Управляет интеграцией с Yandex SmartCaptcha:
 * - Загружает JS API SmartCaptcha
 * - Инициализирует виджет капчи (видимый/невидимый режим)
 * - Обрабатывает callbacks успешной проверки
 * - Предоставляет методы для получения токена и сброса
 * - Интегрируется с FormController
 * 
 * Документация:
 * - https://yandex.cloud/ru/docs/smartcaptcha/concepts/widget-methods
 * - https://yandex.cloud/ru/docs/smartcaptcha/concepts/invisible-captcha
 */
export default class extends Controller {
    static targets = ["container", "token"];

    static values = {
        sitekey: String,      // Client-side ключ из Yandex SmartCaptcha
        invisible: Boolean,   // Невидимый режим (true) или видимый (false)
        callback: String      // Имя callback функции (опционально)
    };

    static outlets = ["form"];

    /**
     * Инициализация контроллера
     */
    connect() {
        this.widgetId = null;
        this.isScriptLoaded = false;
        this.isWidgetReady = false;
        this.isVerified = false; // Флаг успешной проверки капчи
        this.executePromiseResolve = null; // Резолвер для execute()
        this.executePromiseReject = null; // Реджектор для execute()

        // Слушаем событие валидации
        this.element.addEventListener('captcha:validate', this.handleValidation.bind(this));

        // Загружаем SmartCaptcha API
        this.loadSmartCaptchaScript()
            .then(() => {
                this.initializeWidget();
            })
            .catch(error => {
                console.error('Failed to load SmartCaptcha script:', error);
                this.dispatchCaptchaError('Не удалось загрузить капчу');
            });
    }

    /**
     * Очистка при отключении контроллера
     */
    disconnect() {
        // Отклоняем pending Promise если есть
        if (this.executePromiseReject) {
            this.executePromiseReject(new Error('Controller disconnected'));
            this.executePromiseResolve = null;
            this.executePromiseReject = null;
        }

        // Удаляем слушатель событий
        this.element.removeEventListener('captcha:validate', this.handleValidation.bind(this));

        if (this.widgetId !== null && window.smartCaptcha) {
            try {
                window.smartCaptcha.destroy(this.widgetId);
            } catch (error) {
                console.error('Error destroying captcha widget:', error);
            }
        }
    }

    /**
     * Загружает скрипт Yandex SmartCaptcha API
     * @returns {Promise} - Промис загрузки скрипта
     */
    loadSmartCaptchaScript() {
        return new Promise((resolve, reject) => {
            // Проверяем, не загружен ли уже скрипт
            if (window.smartCaptcha) {
                this.isScriptLoaded = true;
                resolve();
                return;
            }

            // Проверяем, не загружается ли уже скрипт
            const existingScript = document.querySelector('script[src*="smartcaptcha.yandexcloud.net"]');
            if (existingScript) {
                existingScript.addEventListener('load', () => {
                    this.isScriptLoaded = true;
                    resolve();
                });
                existingScript.addEventListener('error', reject);
                return;
            }

            // Загружаем скрипт
            const script = document.createElement('script');
            script.src = 'https://smartcaptcha.yandexcloud.net/captcha.js?render=onload&onload=onSmartCaptchaLoad';
            script.async = true;
            script.defer = true;

            script.addEventListener('load', () => {
                this.isScriptLoaded = true;
                resolve();
            });

            script.addEventListener('error', (error) => {
                console.error('SmartCaptcha script load error:', error);
                reject(new Error('Failed to load SmartCaptcha script'));
            });

            document.head.appendChild(script);
        });
    }

    /**
     * Инициализирует виджет SmartCaptcha
     */
    initializeWidget() {
        if (!this.hasContainerTarget) {
            console.error('Captcha container target not found');
            this.dispatchControllerReady(); // Отправляем готовность даже при ошибке
            return;
        }

        if (!window.smartCaptcha) {
            console.error('SmartCaptcha API not available');
            this.dispatchControllerReady(); // Отправляем готовность даже при ошибке
            return;
        }

        // Проверяем наличие sitekey
        if (!this.sitekeyValue) {
            console.error('Captcha sitekey is required');
            this.dispatchCaptchaError('Конфигурация капчи отсутствует');
            this.dispatchControllerReady(); // Отправляем готовность даже при ошибке
            return;
        }

        try {
            const config = {
                sitekey: this.sitekeyValue,
                invisible: this.invisibleValue,
                callback: this.onCaptchaSuccess.bind(this),
                'error-callback': this.onCaptchaError.bind(this),
                'expired-callback': this.onCaptchaExpired.bind(this),
                'network-error-callback': this.onCaptchaNetworkError.bind(this),
                'challenge-hidden-callback': this.onCaptchaChallengeHidden.bind(this)
            };

            // Инициализация через глобальный метод render
            this.widgetId = window.smartCaptcha.render(this.containerTarget, config);

            this.isWidgetReady = true;

            // Если невидимая капча и есть форма - подписываемся на событие submit
            if (this.invisibleValue && this.hasFormOutlet) {
                // Invisible captcha mode
            }

            // Отправляем событие готовности контроллера
            this.dispatchControllerReady();

        } catch (error) {
            console.error('Error initializing SmartCaptcha widget:', error);
            this.dispatchCaptchaError('Ошибка инициализации капчи');
            this.dispatchControllerReady(); // Отправляем готовность даже при ошибке
        }
    }

    // ==========================================
    // === Callbacks SmartCaptcha ===
    // ==========================================

    /**
     * Callback успешной проверки капчи
     * @param {string} token - Токен от SmartCaptcha
     */
    onCaptchaSuccess(token) {
        // Помечаем, что капча успешно пройдена
        this.isVerified = true;

        // Сохраняем токен в hidden input
        if (this.hasTokenTarget) {
            this.tokenTarget.value = token;
        }

        // Если есть pending Promise от execute() - резолвим его
        if (this.executePromiseResolve) {
            this.executePromiseResolve(token);
        }

        // Диспатчим событие успеха
        this.dispatchCaptchaSuccess(token);

        // Если был задан кастомный callback - вызываем его
        if (this.callbackValue && typeof window[this.callbackValue] === 'function') {
            window[this.callbackValue](token);
        }
    }

    /**
     * Callback ошибки капчи
     */
    onCaptchaError() {
        this.isVerified = false;

        // Если есть pending Promise от execute() - реджектим его
        if (this.executePromiseReject) {
            this.executePromiseReject(new Error('Captcha verification error'));
            this.executePromiseResolve = null;
            this.executePromiseReject = null;
        }

        this.dispatchCaptchaError('Ошибка проверки капчи');
    }

    /**
     * Callback истечения срока действия токена
     */
    onCaptchaExpired() {
        // Сбрасываем флаг проверки
        this.isVerified = false;

        // Очищаем токен
        if (this.hasTokenTarget) {
            this.tokenTarget.value = '';
        }

        this.dispatchCaptchaExpired();
    }

    /**
     * Callback сетевой ошибки
     */
    onCaptchaNetworkError() {
        // Если есть pending Promise от execute() - реджектим его
        if (this.executePromiseReject) {
            this.executePromiseReject(new Error('Captcha network error'));
            this.executePromiseResolve = null;
            this.executePromiseReject = null;
        }

        this.dispatchCaptchaError('Проблемы с сетью при проверке капчи');
    }

    /**
     * Callback скрытия challenge (для невидимой капчи)
     */
    onCaptchaChallengeHidden() {
        // Challenge hidden (user closed or completed)
    }

    // ==========================================
    // === Публичные методы ===
    // ==========================================

    /**
     * Получить токен капчи
     * @returns {string|null} - Токен или null если не готов
     */
    getToken() {
        if (!this.isWidgetReady) {
            return null;
        }

        // Для видимой капчи - получаем из hidden input
        if (!this.invisibleValue && this.hasTokenTarget) {
            const token = this.tokenTarget.value;
            return token || null;
        }

        // Для невидимой капчи - получаем через API
        if (this.invisibleValue && window.smartCaptcha && this.widgetId !== null) {
            try {
                const response = window.smartCaptcha.getResponse(this.widgetId);
                return response || null;
            } catch (error) {
                console.error('Error getting captcha token:', error);
                return null;
            }
        }

        return null;
    }

    /**
     * Выполнить проверку капчи (для невидимой капчи)
     * @returns {Promise<string>} - Промис с токеном
     */
    execute() {
        return new Promise((resolve, reject) => {
            if (!this.invisibleValue) {
                reject(new Error('execute() only works with invisible captcha'));
                return;
            }

            if (!this.isWidgetReady || this.widgetId === null) {
                reject(new Error('Captcha widget not ready'));
                return;
            }

            // Если уже есть pending Promise - отклоняем его
            if (this.executePromiseReject) {
                this.executePromiseReject(new Error('New execute() call started'));
            }

            // Если капча уже была пройдена - сбрасываем виджет для повторного выполнения
            if (this.isVerified) {
                try {
                    // Полный сброс виджета через API
                    window.smartCaptcha.reset(this.widgetId);
                    this.isVerified = false;
                    if (this.hasTokenTarget) {
                        this.tokenTarget.value = '';
                    }
                } catch (error) {
                    console.error('Error resetting widget:', error);
                    reject(new Error('Failed to reset captcha widget'));
                    return;
                }
            }

            // Сохраняем resolve/reject для использования в callbacks
            this.executePromiseResolve = resolve;
            this.executePromiseReject = reject;

            // Таймаут на случай если капча не выполнится
            const timeoutId = setTimeout(() => {
                if (this.executePromiseReject) {
                    const reject = this.executePromiseReject;
                    this.executePromiseResolve = null;
                    this.executePromiseReject = null;
                    reject(new Error('Captcha execution timeout'));
                }
            }, 30000); // 30 секунд таймаут

            try {
                // Оборачиваем resolve/reject для очистки таймаута
                const originalResolve = this.executePromiseResolve;
                const originalReject = this.executePromiseReject;

                this.executePromiseResolve = (token) => {
                    clearTimeout(timeoutId);
                    this.executePromiseResolve = null;
                    this.executePromiseReject = null;
                    originalResolve(token);
                };

                this.executePromiseReject = (error) => {
                    clearTimeout(timeoutId);
                    this.executePromiseResolve = null;
                    this.executePromiseReject = null;
                    originalReject(error);
                };

                // Выполняем капчу - результат придёт в onCaptchaSuccess callback
                window.smartCaptcha.execute(this.widgetId);

            } catch (error) {
                console.error('Error executing captcha:', error);
                clearTimeout(timeoutId);
                this.executePromiseResolve = null;
                this.executePromiseReject = null;
                reject(error);
            }
        });
    }

    /**
     * Сбросить капчу
     */
    reset() {
        // Сбрасываем флаг проверки
        this.isVerified = false;

        // Отклоняем pending Promise если есть
        if (this.executePromiseReject) {
            this.executePromiseReject(new Error('Captcha reset'));
            this.executePromiseResolve = null;
            this.executePromiseReject = null;
        }

        // Очищаем токен
        if (this.hasTokenTarget) {
            this.tokenTarget.value = '';
        }

        // Сбрасываем виджет через API
        if (this.isWidgetReady && window.smartCaptcha && this.widgetId !== null) {
            try {
                window.smartCaptcha.reset(this.widgetId);
            } catch (error) {
                console.error('Error resetting captcha:', error);
            }
        }

        // Диспатчим событие сброса
        this.dispatchCaptchaReset();
    }

    /**
     * Проверяет, готова ли капча к использованию
     * @returns {boolean}
     */
    isReady() {
        return this.isWidgetReady && this.widgetId !== null;
    }

    // ==========================================
    // === Валидация ===
    // ==========================================

    /**
     * Обрабатывает событие валидации от ValidationController
     * @param {CustomEvent} event
     */
    handleValidation(event) {
        const { respond } = event.detail;

        // Проверяем, готова ли капча
        if (!this.isReady()) {
            respond('Капча ещё не загружена');
            return;
        }

        // Для видимой капчи проверяем, что пользователь прошёл проверку
        if (!this.invisibleValue && !this.isVerified) {
            respond('Пожалуйста, подтвердите, что вы не робот');
            return;
        }

        // Проверяем наличие токена
        const token = this.getToken();
        if (!token) {
            respond('Пожалуйста, пройдите проверку капчи');
            return;
        }

        respond(null); // null = нет ошибки
    }

    // ==========================================
    // === Диспатчинг событий ===
    // ==========================================

    /**
     * Отправляет событие успешной проверки капчи
     * @param {string} token
     */
    dispatchCaptchaSuccess(token) {
        const event = new CustomEvent('captcha:success', {
            bubbles: true,
            cancelable: false,
            detail: { token }
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Отправляет событие ошибки капчи
     * @param {string} message
     */
    dispatchCaptchaError(message) {
        const event = new CustomEvent('captcha:error', {
            bubbles: true,
            cancelable: false,
            detail: { message }
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Отправляет событие истечения капчи
     */
    dispatchCaptchaExpired() {
        const event = new CustomEvent('captcha:expired', {
            bubbles: true,
            cancelable: false,
            detail: {}
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Отправляет событие сброса капчи
     */
    dispatchCaptchaReset() {
        const event = new CustomEvent('captcha:reset', {
            bubbles: true,
            cancelable: false,
            detail: {}
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Отправляет событие готовности контроллера
     */
    dispatchControllerReady() {
        const event = new CustomEvent('controller:ready', {
            bubbles: true,
            cancelable: false,
            detail: {
                controllerName: 'captcha'
            }
        });
        this.element.dispatchEvent(event);
    }
}
