// static/js/controllers/hello_controller.js
const { Controller } = Stimulus;

/**
 * Контроллер кнопок формы
 * Диспатчит событие при инициализации, чтобы другие компоненты могли узнать текст кнопки
 */
export default class extends Controller {
    static values = {
        label: String,
        action: String,
        key: String
    };

    connect() {
        // Если это кнопка отправки, диспатчим событие с её текстом
        if (this.actionValue === 'submit') {
            this.dispatchButtonReadyEvent();
        }

        console.log(`ButtonController connected: ${this.labelValue} (${this.actionValue})`);
    }

    /**
     * Диспатчит событие о готовности кнопки
     */
    dispatchButtonReadyEvent() {
        const event = new CustomEvent('formzilla:submit-button-ready', {
            detail: {
                label: this.labelValue,
                action: this.actionValue,
                key: this.keyValue,
                element: this.element
            },
            bubbles: true,
            cancelable: false
        });

        document.dispatchEvent(event);
    }
}
