// static/js/controllers/hello_controller.js
const { Controller } = Stimulus;
import { preparePayload, validateFormData } from '../helpers/formDataPreparer.js';

/**
 * Form Controller
 * 
 * Координирует процесс отправки формы:
 * - Собирает данные формы
 * - Выполняет клиентскую валидацию
 * - Управляет UI-состоянием (кнопки, модалки)
 * - Взаимодействует с apiController для отправки
 * - Обрабатывает результаты отправки
 */
export default class extends Controller {
    static targets = [
        "submitButton",
        "form",
        "formContainer",
        "spinnerContainer",
        "errorContainer",
        "successContainer",
        "errorMessage",
        "successMessage",
        "retryButton"
    ];

    static values = {
        endpoint: String,
        csrfToken: String,
        schema: Object,  // JSON-схема формы для валидации
        params: Object   // Дополнительные параметры формы (style, настройки и т.д.)
    };

    static outlets = ["captcha"];

    /**
     * Инициализация контроллера
     */
    connect() {
        const timestamp = new Date().toISOString();

        // Инициализация системы отслеживания готовности контроллеров
        this.initializationState = {
            controllers: new Set(),
            readyControllers: new Set(),
            isInitialized: false
        };

        // Показываем спиннер при инициализации
        this.showSpinner();

        // Слушаем события готовности контроллеров
        this.element.addEventListener('controller:ready', this.onControllerReady.bind(this));

        // Слушаем события от apiController
        this.element.addEventListener('api:submit', this.onApiSubmit.bind(this));
        this.element.addEventListener('api:success', this.onApiSuccess.bind(this));
        this.element.addEventListener('api:error', this.onApiError.bind(this));
        this.element.addEventListener('api:network-error', this.onNetworkError.bind(this));
        this.element.addEventListener('api:progress', this.onApiProgress.bind(this));

        // Слушаем события от captchaController
        this.element.addEventListener('captcha:success', this.onCaptchaSuccess.bind(this));
        this.element.addEventListener('captcha:error', this.onCaptchaError.bind(this));
        this.element.addEventListener('captcha:expired', this.onCaptchaExpired.bind(this));

        // Регистрируем контроллеры, которые требуют асинхронной инициализации
        this.registerControllersToWatch();

        // Запускаем таймаут на случай, если контроллеры не отзовутся
        this.initializationTimeout = setTimeout(() => {
            if (!this.initializationState.isInitialized) {
                console.warn(`[${timestamp}] ⏱️  FormController.connect - инициализация завершена по таймауту (5 сек)`);
                this.completeInitialization();
            }
        }, 5000); // 5 секунд на инициализацию
    }

    /**
     * Очистка при отключении контроллера
     */
    disconnect() {
        // Очищаем таймаут инициализации если он еще активен
        if (this.initializationTimeout) {
            clearTimeout(this.initializationTimeout);
        }

        this.element.removeEventListener('controller:ready', this.onControllerReady.bind(this));
        this.element.removeEventListener('api:submit', this.onApiSubmit.bind(this));
        this.element.removeEventListener('api:success', this.onApiSuccess.bind(this));
        this.element.removeEventListener('api:error', this.onApiError.bind(this));
        this.element.removeEventListener('api:network-error', this.onNetworkError.bind(this));
        this.element.removeEventListener('api:progress', this.onApiProgress.bind(this));
        this.element.removeEventListener('captcha:success', this.onCaptchaSuccess.bind(this));
        this.element.removeEventListener('captcha:error', this.onCaptchaError.bind(this));
        this.element.removeEventListener('captcha:expired', this.onCaptchaExpired.bind(this));
    }

    /**
     * Обработка отправки формы
     * @param {Event} event - Событие submit
     */
    async submit(event) {
        const timestamp = new Date().toISOString();

        event.preventDefault();

        // 0. НЕМЕДЛЕННО блокируем кнопку отправки, чтобы предотвратить повторные отправки
        this.disableSubmitButton();

        // 1. Очистка предыдущих ошибок
        this.clearValidationErrors();

        // 2. Проверяем наличие капчи и получаем токен ДО сбора данных
        const captchaResult = await this.getCaptchaToken();
        if (captchaResult === false) {
            // Капча обязательна, но не пройдена
            this.enableSubmitButton();
            this.dispatchValidationError({ captcha: 'Пожалуйста, подтвердите, что вы не робот' });
            return;
        }

        // 3. Получаем файл из input[type="file"] если он есть
        const file = this.getFileFromInput();
        if (file) {
            console.log(`[${timestamp}] 📎 FormController.submit - файл найден`, {
                fileName: file.name,
                fileSize: file.size,
                fileType: file.type
            });
        }

        // 4. Сбор данных формы через formDataPreparer
        let payload;
        try {
            payload = await preparePayload(
                this.formTarget,
                this.schemaValue
            );
        } catch (error) {
            this.enableSubmitButton();
            this.dispatchValidationError({ _form: 'Ошибка при подготовке данных формы' });
            return;
        }

        // 5. Добавляем токен капчи в payload если есть
        if (captchaResult && captchaResult !== null) {
            payload.captcha_token = captchaResult;
        }

        // 6. Клиентская валидация
        const validationErrors = await this.validatePayload(payload);

        if (Object.keys(validationErrors).length > 0) {
            console.warn(`[${timestamp}] ❌ FormController.submit - найдены ошибки валидации`, {
                errorCount: Object.keys(validationErrors).length,
                errors: Object.keys(validationErrors)
            });
            this.enableSubmitButton();
            this.dispatchValidationError(validationErrors);
            return;
        }

        // 7. Диспатч события для apiController (передаем файл если есть)
        // Кнопка уже заблокирована в начале метода
        this.dispatchFormSubmit(payload, file);
    }

    // ==========================================
    // === Управление инициализацией ===
    // ==========================================

    /**
     * Регистрирует контроллеры, которые требуют асинхронной инициализации
     */
    registerControllersToWatch() {
        // Находим все контроллеры, которые требуют ожидания инициализации
        const asyncControllers = [
            'captcha',    // Загружает внешний скрипт Yandex SmartCaptcha
            'mask',       // Динамически импортирует Inputmask
            'validation', // Должен быть готов для валидации
            'api'         // Должен быть готов для отправки
        ];

        asyncControllers.forEach(controllerName => {
            const controllerElement = this.element.querySelector(`[data-controller*="${controllerName}"]`);
            if (controllerElement) {
                this.initializationState.controllers.add(controllerName);
            }
        });

        // Если нет контроллеров для ожидания - сразу завершаем инициализацию
        if (this.initializationState.controllers.size === 0) {
            this.completeInitialization();
        }
    }

    /**
     * Обработчик события готовности контроллера
     * @param {CustomEvent} event
     */
    onControllerReady(event) {
        const { controllerName } = event.detail;

        // Добавляем контроллер в список готовых
        this.initializationState.readyControllers.add(controllerName);

        // Проверяем, все ли контроллеры готовы
        this.checkInitializationComplete();
    }

    /**
     * Проверяет, завершена ли инициализация всех контроллеров
     */
    checkInitializationComplete() {
        if (this.initializationState.isInitialized) {
            return; // Уже инициализировано
        }

        // Проверяем, что все зарегистрированные контроллеры готовы
        const allReady = Array.from(this.initializationState.controllers).every(
            controller => this.initializationState.readyControllers.has(controller)
        );

        if (allReady) {
            this.completeInitialization();
        }
    }

    /**
     * Завершает инициализацию формы
     */
    completeInitialization() {
        if (this.initializationState.isInitialized) {
            return; // Уже завершено
        }

        this.initializationState.isInitialized = true;

        // Очищаем таймаут если он еще активен
        if (this.initializationTimeout) {
            clearTimeout(this.initializationTimeout);
            this.initializationTimeout = null;
        }

        // Скрываем спиннер и показываем форму
        this.showForm();

        // Диспатчим событие завершения инициализации
        const event = new CustomEvent('form:initialized', {
            bubbles: true,
            cancelable: false,
            detail: {
                controllers: Array.from(this.initializationState.controllers),
                readyControllers: Array.from(this.initializationState.readyControllers)
            }
        });
        this.element.dispatchEvent(event);
    }

    // ==========================================
    // === Управление видимостью состояний ===
    // ==========================================

    /**
     * Скрыть все state-контейнеры
     */
    hideAllStates() {
        if (this.hasFormContainerTarget) {
            this.formContainerTarget.classList.add('form-state-hidden');
            this.formContainerTarget.classList.remove('form-state-visible');
        }

        if (this.hasSpinnerContainerTarget) {
            this.spinnerContainerTarget.classList.add('form-state-hidden');
            this.spinnerContainerTarget.classList.remove('form-state-visible');
        }

        if (this.hasErrorContainerTarget) {
            this.errorContainerTarget.classList.add('form-state-hidden');
            this.errorContainerTarget.classList.remove('form-state-visible');
        }

        if (this.hasSuccessContainerTarget) {
            this.successContainerTarget.classList.add('form-state-hidden');
            this.successContainerTarget.classList.remove('form-state-visible');
        }
    }

    /**
     * Скрыть форму
     */
    hideForm() {
        if (this.hasFormContainerTarget) {
            this.formContainerTarget.classList.add('form-state-hidden');
            this.formContainerTarget.classList.remove('form-state-visible');
        }
    }

    /**
     * Показать форму
     */
    showForm() {
        this.hideAllStates();
        if (this.hasFormContainerTarget) {
            this.formContainerTarget.classList.remove('form-state-hidden');
            this.formContainerTarget.classList.add('form-state-visible');
        }
    }

    /**
     * Показать спиннер загрузки
     * @param {string} message - Текст сообщения (по умолчанию "Загрузка формы...")
     */
    showSpinner(message = 'Загрузка формы...') {
        this.hideAllStates();
        if (this.hasSpinnerContainerTarget) {
            this.spinnerContainerTarget.classList.remove('form-state-hidden');
            this.spinnerContainerTarget.classList.add('form-state-visible');

            // Обновляем текст сообщения
            const messageElement = this.spinnerContainerTarget.querySelector('p');
            if (messageElement) {
                messageElement.textContent = message;
            }
        }
    }

    /**
     * Скрыть спиннер загрузки
     */
    hideSpinner() {
        if (this.hasSpinnerContainerTarget) {
            this.spinnerContainerTarget.classList.add('form-state-hidden');
            this.spinnerContainerTarget.classList.remove('form-state-visible');
        }
    }

    /**
     * Показать сообщение об ошибке
     * @param {string} message - Текст ошибки
     * @param {boolean} allowRetry - Показывать ли кнопку повтора
     */
    showError(message, allowRetry = false) {
        this.hideAllStates();

        if (this.hasErrorContainerTarget) {
            this.errorContainerTarget.classList.remove('form-state-hidden');
            this.errorContainerTarget.classList.add('form-state-visible');
        }

        if (this.hasErrorMessageTarget) {
            this.errorMessageTarget.textContent = message;
        }

        if (this.hasRetryButtonTarget) {
            if (allowRetry) {
                this.retryButtonTarget.style.display = 'inline-block';
            } else {
                this.retryButtonTarget.style.display = 'none';
            }
        }
    }

    /**
     * Показать сообщение об успехе
     * @param {string} message - Текст сообщения
     */
    showSuccess(message) {
        this.hideAllStates();

        if (this.hasSuccessContainerTarget) {
            this.successContainerTarget.classList.remove('form-state-hidden');
            this.successContainerTarget.classList.add('form-state-visible');
        }

        if (this.hasSuccessMessageTarget) {
            this.successMessageTarget.textContent = message;
        }
    }

    /**
     * Восстановить форму в исходное состояние
     * (показать форму, разблокировать кнопки, сбросить капчу)
     */
    restoreForm() {
        // Показываем форму
        this.showForm();

        // Разблокируем кнопку отправки
        this.enableSubmitButton();

        // Очищаем ошибки валидации
        this.clearValidationErrors();

        // Сбрасываем капчу
        this.resetCaptcha();
    }

    /**
     * Обработчик клика на кнопку "Повторить запрос"
     */
    retrySubmit() {
        this.restoreForm();
    }

    // ==========================================
    // === Обработчики событий от apiController ===
    // ==========================================

    /**
     * Обработчик начала отправки (перед fetch-запросом)
     * @param {CustomEvent} event
     */
    onApiSubmit(event) {
        // Скрываем форму и показываем спиннер отправки
        this.showSpinner('Отправка данных...');
    }

    /**
     * Обработчик прогресса загрузки файла
     * @param {CustomEvent} event
     */
    onApiProgress(event) {
        const { percent, loaded, total } = event.detail;

        // Получаем элементы прогресс-бара и обновляем их
        const progressElement = this.getFileProgressElement();
        const progressBar = this.getFileProgressBar();

        if (progressElement) {
            progressElement.classList.remove('d-none');
        }

        if (progressBar) {
            progressBar.style.width = `${percent}%`;
        }

        // Обновляем текст спиннера с информацией о прогрессе
        const loadedMB = (loaded / (1024 * 1024)).toFixed(1);
        const totalMB = (total / (1024 * 1024)).toFixed(1);
        this.showSpinner(`Загрузка файла: ${percent}% (${loadedMB} / ${totalMB} MB)`);
    }    /**
     * Обработчик успешной отправки
     * @param {CustomEvent} event
     */
    onApiSuccess(event) {
        const { message } = event.detail;

        // Скрываем спиннер и показываем сообщение об успехе
        this.showSuccess(message || 'Форма успешно отправлена');
    }

    /**
     * Обработчик ошибки валидации от сервера
     * @param {CustomEvent} event
     */
    onApiError(event) {
        const timestamp = new Date().toISOString();
        const { message, errors, repeat, captcha_retry } = event.detail;

        console.warn(`[${timestamp}] ❌ FormController.onApiError - ошибка от сервера`, {
            message,
            hasErrors: !!errors && Object.keys(errors).length > 0,
            errorCount: errors ? Object.keys(errors).length : 0,
            repeat,
            captcha_retry
        });

        // Если ошибка связана с капчей и требуется повторная попытка
        if (captcha_retry) {
            this.resetCaptcha();
        }

        // Если есть ошибки валидации полей - передаем их в validationController
        // и восстанавливаем форму, чтобы пользователь мог исправить
        if (errors && Object.keys(errors).length > 0) {
            this.showForm();
            this.enableSubmitButton();
            this.dispatchValidationError(errors);
            return;
        }

        // Иначе показываем общее сообщение об ошибке
        // repeat определяет, показывать ли кнопку "Повторить запрос"
        const allowRetry = repeat === true;
        this.showError(
            message || 'Произошла ошибка при обработке запроса',
            allowRetry
        );
    }

    /**
     * Обработчик сетевой ошибки
     * @param {CustomEvent} event
     */
    onNetworkError(event) {
        const timestamp = new Date().toISOString();
        const { message } = event.detail;

        console.error(`[${timestamp}] 🌐❌ FormController.onNetworkError - сетевая ошибка`, { message });

        // Сетевые ошибки всегда можно повторить
        this.showError(
            message || 'Ошибка соединения. Проверьте интернет и попробуйте снова.',
            true  // allowRetry = true
        );
    }

    // ==========================================
    // === Валидация ===
    // ==========================================

    /**
     * Выполняет валидацию данных формы
     * @param {Object} payload - Данные формы
     * @returns {Promise<Object>} - Объект с ошибками
     */
    async validatePayload(payload) {
        // ValidationController вернет результат через событие validation:complete
        // Ждем результата валидации
        return new Promise((resolve) => {
            let resolved = false;

            const handleValidationResult = (event) => {
                if (resolved) return;

                resolved = true;
                this.element.removeEventListener('validation:complete', handleValidationResult);
                resolve(event.detail.errors || {});
            };

            // Регистрируем слушатель ПЕРЕД отправкой события
            this.element.addEventListener('validation:complete', handleValidationResult);

            // Таймаут на случай, если ValidationController не установлен
            const timeoutId = setTimeout(() => {
                if (resolved) return;

                resolved = true;
                this.element.removeEventListener('validation:complete', handleValidationResult);

                // Fallback: используем базовую валидацию из formDataPreparer
                const errors = validateFormData(payload, this.schemaValue);
                resolve(errors);
            }, 500);

            // Запускаем валидацию через ValidationController
            const validationEvent = new CustomEvent('validation:run', {
                bubbles: true,
                cancelable: true,
                detail: {
                    payload,
                    schema: this.schemaValue
                }
            });

            this.element.dispatchEvent(validationEvent);
        });
    }

    // ==========================================
    // === Диспатчинг событий ===
    // ==========================================

    /**
     * Отправляет событие form:submit для apiController
     * @param {Object} payload - Данные формы
     * @param {File} file - Файл для загрузки (опционально)
     */
    dispatchFormSubmit(payload, file = null) {
        // Добавляем params в payload если они есть
        const payloadWithParams = {
            ...payload,
            //_params: this.hasParamsValue ? this.paramsValue : {}
        };

        const event = new CustomEvent('form:submit', {
            bubbles: true,
            cancelable: false,
            detail: {
                endpoint: this.endpointValue,
                payload: payloadWithParams,
                file: file,
                csrfToken: this.csrfTokenValue
            }
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Получает файл из input[type="file"] в форме
     * @returns {File|null} - Файл или null
     */
    getFileFromInput() {
        // Ищем input с типом file в форме
        const fileInput = this.element.querySelector('input[type="file"]');
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            return null;
        }

        return fileInput.files[0];
    }

    /**
     * Получает элемент с data-file-target="progress" для обновления прогресса
     * @returns {HTMLElement|null}
     */
    getFileProgressElement() {
        return this.element.querySelector('[data-file-target="progress"]');
    }

    /**
     * Получает элемент с data-file-target="progressBar" для обновления прогресс-бара
     * @returns {HTMLElement|null}
     */
    getFileProgressBar() {
        return this.element.querySelector('[data-file-target="progressBar"]');
    }

    /**
     * Отправляет событие form:validation-error
     * @param {Object} errors - Ошибки валидации
     */
    dispatchValidationError(errors) {
        const event = new CustomEvent('form:validation-error', {
            bubbles: true,
            cancelable: false,
            detail: { errors }
        });

        this.element.dispatchEvent(event);
    }

    /**
     * Очищает ошибки валидации
     */
    clearValidationErrors() {
        const event = new CustomEvent('validation:clear', {
            bubbles: true,
            cancelable: false
        });
        this.element.dispatchEvent(event);
    }

    // ==========================================
    // === UI-методы (управление состоянием) ===
    // ==========================================

    /**
     * Блокирует кнопку отправки
     */
    disableSubmitButton() {
        if (this.hasSubmitButtonTarget) {
            this.submitButtonTarget.disabled = true;
            this.submitButtonTarget.classList.add('loading');

            // Скрываем текст кнопки и показываем спиннер
            const buttonText = this.submitButtonTarget.querySelector('.button-text');
            const buttonSpinner = this.submitButtonTarget.querySelector('.button-spinner');

            if (buttonText) {
                buttonText.classList.add('d-none');
            }

            if (buttonSpinner) {
                buttonSpinner.classList.remove('d-none');
            }

            // Старая логика для совместимости
            const spinner = this.submitButtonTarget.querySelector('.spinner-border');
            if (spinner) {
                spinner.classList.remove('d-none');
            }
        }
    }

    /**
     * Разблокирует кнопку отправки
     */
    enableSubmitButton() {
        if (this.hasSubmitButtonTarget) {
            this.submitButtonTarget.disabled = false;
            this.submitButtonTarget.classList.remove('loading');

            // Показываем текст кнопки и скрываем спиннер
            const buttonText = this.submitButtonTarget.querySelector('.button-text');
            const buttonSpinner = this.submitButtonTarget.querySelector('.button-spinner');

            if (buttonText) {
                buttonText.classList.remove('d-none');
            }

            if (buttonSpinner) {
                buttonSpinner.classList.add('d-none');
            }

            // Старая логика для совместимости
            const spinner = this.submitButtonTarget.querySelector('.spinner-border');
            if (spinner) {
                spinner.classList.add('d-none');
            }
        }
    }

    // ==========================================
    // === Вспомогательные методы ===
    // ==========================================

    /**
     * Проверяет наличие target'а формы
     * @returns {boolean}
     */
    get hasFormTarget() {
        return this.targets.has('form');
    }

    /**
     * Проверяет наличие target'а кнопки отправки
     * @returns {boolean}
     */
    get hasSubmitButtonTarget() {
        return this.targets.has('submitButton');
    }

    // ==========================================
    // === Методы работы с капчей ===
    // ==========================================

    /**
     * Получает токен капчи перед отправкой формы
     * @returns {Promise<string|null|false>} - Токен, null (капча опциональна), или false (капча обязательна но не пройдена)
     */
    async getCaptchaToken() {
        // Проверяем наличие captcha контроллера через outlets
        if (!this.hasCaptchaOutlet || this.captchaOutlets.length === 0) {
            return null;
        }

        const captchaController = this.captchaOutlets[0];

        // Проверяем, готова ли капча
        if (!captchaController.isReady()) {
            return false;
        }

        // Для невидимой капчи - выполняем проверку
        if (captchaController.invisibleValue) {
            try {
                const token = await captchaController.execute();
                return token;
            } catch (error) {
                console.error('Error executing invisible captcha:', error);
                return false;
            }
        }

        // Для видимой капчи - проверяем, что пользователь прошёл проверку
        if (!captchaController.isVerified) {
            return false;
        }

        // Получаем токен
        const token = captchaController.getToken();

        if (!token) {
            return false;
        }

        return token;
    }

    /**
     * Сбрасывает капчу (например, после ошибки отправки)
     */
    resetCaptcha() {
        if (!this.hasCaptchaOutlet || this.captchaOutlets.length === 0) {
            return;
        }

        const captchaController = this.captchaOutlets[0];
        captchaController.reset();
    }

    /**
     * Обработчик успешной проверки капчи
     * @param {CustomEvent} event
     */
    onCaptchaSuccess(event) {
        // Можно добавить визуальную индикацию успеха
        // Например, показать галочку рядом с капчей
    }

    /**
     * Обработчик ошибки капчи
     * @param {CustomEvent} event
     */
    onCaptchaError(event) {
        // Ошибки капчи обрабатываются в submit() и в onApiError()
    }

    /**
     * Обработчик истечения срока действия капчи
     * @param {CustomEvent} event
     */
    onCaptchaExpired(event) {

        // Можно показать предупреждение пользователю
        // что нужно пройти капчу заново
    }
}
