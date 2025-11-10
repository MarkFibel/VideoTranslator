// static/js/controllers/hello_controller.js
const { Controller } = Stimulus;
import { Modal } from 'bootstrap';

/**
 * Универсальный контроллер модальных окон
 * Обеспечивает централизованное управление модальными окнами с поддержкой Bootstrap 5
 */
export default class extends Controller {
    connect() {
    }

    /**
     * Показать модальное окно
     * @param {Object} config - Конфигурация модального окна
     * @returns {Object} - Объект с методами управления модальным окном
     */
    show(config) {
        // Валидация конфигурации
        if (!config.id || !config.content) {
            console.error('Modal config must include id, and content');
            return;
        }

        // Удаляем предыдущее модальное окно с таким же ID
        const existingModal = document.getElementById(config.id);
        if (existingModal) {
            existingModal.remove();
        }

        // Генерируем HTML модального окна
        const modalHtml = this.generateModalHtml(config);

        // Добавляем модальное окно в DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modalElement = document.getElementById(config.id);

        // Инициализируем Bootstrap Modal
        const bootstrapModal = new Modal(modalElement, {
            backdrop: config.backdrop !== undefined ? config.backdrop : true,
            keyboard: config.keyboard !== undefined ? config.keyboard : true,
        });

        // Настраиваем обработчики кнопок
        this.setupButtonHandlers(modalElement, config.buttons || [], bootstrapModal);

        // Настраиваем обработчики событий жизненного цикла
        this.setupLifecycleHandlers(modalElement, bootstrapModal, config);

        // Показываем модальное окно
        bootstrapModal.show();

        // Возвращаем API для внешнего управления
        return {
            hide: () => bootstrapModal.hide(),
            dispose: () => bootstrapModal.dispose(),
            element: modalElement
        };
    }

    /**
     * Генерация HTML-разметки модального окна
     * @param {Object} config - Конфигурация
     * @returns {string} - HTML-разметка
     */
    generateModalHtml(config) {
        const sizeClass = config.size ? `modal-${config.size}` : '';
        const scrollableClass = config.scrollable ? 'modal-dialog-scrollable' : '';
        const centeredClass = config.centered ? 'modal-dialog-centered' : '';
        const dialogClasses = ['modal-dialog', sizeClass, scrollableClass, centeredClass]
            .filter(Boolean)
            .join(' ');

        const buttonsHtml = this.generateButtonsHtml(config.buttons || [], config.type);

        return `
            <div class="modal fade" id="${config.id}" tabindex="-1" 
                 aria-labelledby="${config.id}Label" aria-hidden="true">
                <div class="${dialogClasses}">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="${config.id}Label">
                                ${config.title}
                            </h5>
                            <button type="button" class="btn-close" 
                                    data-bs-dismiss="modal" 
                                    aria-label="Закрыть"
                                    data-action="close"></button>
                        </div>
                        <div class="modal-body">
                            ${config.content}
                        </div>
                        ${buttonsHtml ? `<div class="modal-footer">${buttonsHtml}</div>` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Генерация HTML для кнопок
     * @param {Array} buttons - Массив конфигураций кнопок
     * @param {string} type - Тип модального окна
     * @returns {string} - HTML кнопок
     */
    generateButtonsHtml(buttons, type) {
        // Если кнопки не заданы, используем дефолтные для типа
        if (buttons.length === 0) {
            buttons = this.getDefaultButtonsForType(type);
        }

        return buttons.map(button => {
            const btnClass = `btn btn-${button.style || 'primary'}`;
            return `
                <button type="button" 
                        class="${btnClass}" 
                        data-action="${button.action || 'default'}">
                    ${button.label}
                </button>
            `;
        }).join('');
    }

    /**
     * Получить дефолтные кнопки для типа модального окна
     * @param {string} type - Тип модального окна
     * @returns {Array} - Массив конфигураций кнопок
     */
    getDefaultButtonsForType(type) {
        const defaults = {
            info: [
                { label: 'ОК', style: 'primary', action: 'ok' }
            ],
            confirm: [
                { label: 'Да', style: 'primary', action: 'confirm' },
                { label: 'Нет', style: 'secondary', action: 'cancel' }
            ],
            agreement: [
                { label: 'Принимаю', style: 'success', action: 'accept' },
                { label: 'Не принимаю', style: 'outline-secondary', action: 'reject' }
            ]
        };

        return defaults[type] || [];
    }

    /**
     * Настройка обработчиков кнопок
     * @param {HTMLElement} modalElement - DOM элемент модального окна
     * @param {Array} buttons - Массив конфигураций кнопок
     * @param {bootstrap.Modal} bootstrapModal - Экземпляр Bootstrap Modal
     */
    setupButtonHandlers(modalElement, buttons, bootstrapModal) {
        buttons.forEach(button => {
            const btnElement = modalElement.querySelector(`button[data-action="${button.action}"]`);
            if (btnElement && button.callback) {
                btnElement.addEventListener('click', () => {
                    // Вызываем callback
                    const result = button.callback();

                    // Если callback вернул не false, закрываем модальное окно
                    if (result !== false) {
                        bootstrapModal.hide();
                    }
                });
            }
        });
    }

    /**
     * Настройка обработчиков жизненного цикла
     * @param {HTMLElement} modalElement - DOM элемент модального окна
     * @param {bootstrap.Modal} bootstrapModal - Экземпляр Bootstrap Modal
     * @param {Object} config - Конфигурация
     */
    setupLifecycleHandlers(modalElement, bootstrapModal, config) {
        // Событие после показа модального окна
        if (config.onShow) {
            modalElement.addEventListener('shown.bs.modal', config.onShow);
        }

        // Событие после скрытия модального окна
        if (config.onHide) {
            modalElement.addEventListener('hidden.bs.modal', config.onHide);
        }

        // Обработка закрытия через крестик, ESC или backdrop
        const closeButton = modalElement.querySelector('button[data-action="close"]');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                if (config.onClose) {
                    config.onClose();
                }
            });
        }

        // Событие при закрытии через backdrop или ESC
        modalElement.addEventListener('hidden.bs.modal', (event) => {
            // Проверяем, было ли закрытие через крестик или кнопку
            // Если нет - значит через backdrop или ESC
            if (event.target === modalElement && config.onClose) {
                const wasButtonClick = Array.from(config.buttons || []).some(btn => {
                    const btnEl = modalElement.querySelector(`button[data-action="${btn.action}"]`);
                    return btnEl && btnEl === document.activeElement;
                });

                if (!wasButtonClick) {
                    config.onClose();
                }
            }
        });

        // Автоматическое удаление из DOM после закрытия
        modalElement.addEventListener('hidden.bs.modal', () => {
            setTimeout(() => {
                modalElement.remove();
            }, 300); // Задержка для завершения анимации
        });
    }

    /**
     * Хелпер-методы для быстрого создания типовых модальных окон
     */

    /**
     * Показать информационное модальное окно
     */
    showInfo(title, content, onOk) {
        return this.show({
            id: `modal-info-${Date.now()}`,
            type: 'info',
            title,
            content,
            size: 'md',
            centered: true,
            buttons: [
                {
                    label: 'ОК',
                    style: 'primary',
                    action: 'ok',
                    callback: onOk || (() => { })
                }
            ]
        });
    }

    /**
     * Показать модальное окно подтверждения
     */
    showConfirm(title, content, onConfirm, onCancel) {
        return this.show({
            id: `modal-confirm-${Date.now()}`,
            type: 'confirm',
            title,
            content,
            size: 'md',
            centered: true,
            buttons: [
                {
                    label: 'Да',
                    style: 'primary',
                    action: 'confirm',
                    callback: onConfirm || (() => { })
                },
                {
                    label: 'Нет',
                    style: 'secondary',
                    action: 'cancel',
                    callback: onCancel || (() => { })
                }
            ]
        });
    }

    /**
     * Показать модальное окно согласия
     */
    showAgreement(title, content, onAccept, onReject, onClose) {
        return this.show({
            id: `modal-agreement-${Date.now()}`,
            type: 'agreement',
            title: '',
            content,
            size: 'lg',
            scrollable: true,
            centered: true,
            backdrop: 'static',
            keyboard: true,
            buttons: [
                {
                    label: 'Принимаю',
                    style: 'success',
                    action: 'accept',
                    callback: onAccept || (() => { })
                },
                {
                    label: 'Не принимаю',
                    style: 'outline-secondary',
                    action: 'reject',
                    callback: onReject || (() => { })
                }
            ],
            onClose: onClose || (() => { })
        });
    }
}
