// static/js/controllers/languageController.js
const { Controller } = Stimulus;

/**
 * Контроллер управления языком интерфейса
 * 
 * Возможности:
 * - Переключение между языками (RU/EN)
 * - Сохранение выбранного языка в localStorage
 * - Автоматическое применение переводов ко всем элементам с data-i18n
 * - Определение языка браузера при первом посещении
 */
export default class extends Controller {
    static targets = ["button"];

    static values = {
        defaultLang: { type: String, default: 'ru' }
    };

    // Словарь переводов
    translations = {
        ru: {
            'title': 'VIDEO PROCESSOR',
            'subtitle': 'Загрузите и обработайте ваши видео с нашими продвинутыми алгоритмами',
            'upload-title': 'ЗАГРУЗИТЕ ВАШЕ ВИДЕО',
            'upload-subtitle': 'Выберите видеофайл для начала обработки',
            'upload-button': 'ЗАГРУЗИТЬ ВИДЕО',
            'submit-btn': 'ОТПРАВИТЬ ВИДЕО',
            'how-it-works': 'Как работает VideoProcessor',
            'step1-number': '1. Загрузите видео',
            'step1-desc': 'Выберите и загрузите видеофайл на наш защищённый сервер',
            'step2-number': '2. ИИ обработка',
            'step2-desc': 'Наш продвинутый ИИ анализирует и улучшает ваше видео',
            'step3-number': '3. Скачайте результат',
            'step3-desc': 'Получите обработанное видео с улучшенным качеством',
            'version': 'Продвинутая система обработки видео версия 1.0.0'
        },
        en: {
            'title': 'VIDEO PROCESSOR',
            'subtitle': 'Upload and process your videos with our advanced algorithms',
            'upload-title': 'UPLOAD YOUR VIDEO',
            'upload-subtitle': 'Select a video file to start processing',
            'upload-button': 'UPLOAD VIDEO',
            'submit-btn': 'SUBMIT VIDEO',
            'how-it-works': 'How VideoProcessor Works',
            'step1-number': '1. Upload Video',
            'step1-desc': 'Select and upload a video file to our secure server',
            'step2-number': '2. AI Processing',
            'step2-desc': 'Our advanced AI analyzes and enhances your video',
            'step3-number': '3. Download Result',
            'step3-desc': 'Get your processed video with improved quality',
            'version': 'Advanced video processing system version 1.0.0'
        }
    };

    /**
     * Инициализация контроллера
     */
    connect() {
        console.log('LanguageController connected');

        // Получаем сохраненный язык или определяем по браузеру
        const savedLang = this.getSavedLanguage();
        this.currentLang = savedLang || this.detectBrowserLanguage();

        // Применяем текущий язык
        this.applyLanguage(this.currentLang);

        // Обновляем состояние кнопок
        this.updateButtonStates();
    }

    /**
     * Получает сохраненный язык из localStorage
     * @returns {string|null} - Код языка или null
     */
    getSavedLanguage() {
        try {
            return localStorage.getItem('preferredLanguage');
        } catch (e) {
            console.warn('localStorage недоступен:', e);
            return null;
        }
    }

    /**
     * Сохраняет выбранный язык в localStorage
     * @param {string} lang - Код языка
     */
    saveLanguage(lang) {
        try {
            localStorage.setItem('preferredLanguage', lang);
        } catch (e) {
            console.warn('Не удалось сохранить язык в localStorage:', e);
        }
    }

    /**
     * Определяет язык браузера
     * @returns {string} - Код языка (ru или en)
     */
    detectBrowserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;

        // Если язык браузера начинается с 'ru', используем русский
        if (browserLang && browserLang.toLowerCase().startsWith('ru')) {
            return 'ru';
        }

        // По умолчанию - язык из конфигурации
        return this.defaultLangValue;
    }

    /**
     * Обработчик переключения языка
     * @param {Event} event - Событие клика
     */
    switchLanguage(event) {
        const button = event.currentTarget;
        const lang = button.dataset.lang;

        if (!lang || lang === this.currentLang) {
            return;
        }

        // Применяем новый язык
        this.applyLanguage(lang);

        // Сохраняем выбор
        this.saveLanguage(lang);

        // Обновляем состояние кнопок
        this.updateButtonStates();

        // Диспатчим событие смены языка
        this.dispatchLanguageChangeEvent(lang);
    }

    /**
     * Применяет выбранный язык ко всем элементам
     * @param {string} lang - Код языка
     */
    applyLanguage(lang) {
        if (!this.translations[lang]) {
            console.error(`Переводы для языка "${lang}" не найдены`);
            return;
        }

        this.currentLang = lang;
        const translations = this.translations[lang];

        // Находим все элементы с атрибутом data-i18n
        const elements = document.querySelectorAll('[data-i18n]');

        elements.forEach(element => {
            const key = element.getAttribute('data-i18n');

            if (translations[key]) {
                // Обновляем текстовое содержимое элемента
                element.textContent = translations[key];
            } else {
                console.warn(`Перевод для ключа "${key}" не найден в языке "${lang}"`);
            }
        });

        console.log(`Язык изменен на: ${lang}`);
    }

    /**
     * Обновляет визуальное состояние кнопок языка
     */
    updateButtonStates() {
        this.buttonTargets.forEach(button => {
            const lang = button.dataset.lang;

            if (lang === this.currentLang) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    /**
     * Отправляет событие смены языка
     * @param {string} lang - Новый язык
     */
    dispatchLanguageChangeEvent(lang) {
        const event = new CustomEvent('language:changed', {
            bubbles: true,
            cancelable: false,
            detail: {
                language: lang,
                previousLanguage: this.previousLang || this.currentLang
            }
        });

        this.previousLang = this.currentLang;
        this.element.dispatchEvent(event);
    }

    /**
     * Получает текущий язык
     * @returns {string} - Код текущего языка
     */
    getCurrentLanguage() {
        return this.currentLang;
    }

    /**
     * Добавляет новые переводы (для расширения функционала)
     * @param {string} lang - Код языка
     * @param {Object} translations - Объект с переводами
     */
    addTranslations(lang, translations) {
        if (!this.translations[lang]) {
            this.translations[lang] = {};
        }

        this.translations[lang] = {
            ...this.translations[lang],
            ...translations
        };
    }

    /**
     * Получает перевод по ключу для текущего языка
     * @param {string} key - Ключ перевода
     * @returns {string|null} - Переведенная строка или null
     */
    getTranslation(key) {
        const translations = this.translations[this.currentLang];
        return translations ? translations[key] : null;
    }
}
