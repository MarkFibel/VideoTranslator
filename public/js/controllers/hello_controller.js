// static/js/controllers/hello_controller.js
const { Controller } = Stimulus;

export default class extends Controller {
    static targets = ["name", "output"];

    greet() {
        const name = this.nameTarget.value || "Мир";
        this.outputTarget.textContent = `Привет, ${name}!`;
    }
}