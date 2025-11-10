/**
 * Хелпер для управления событиями изменения полей
 * Оптимизирует отправку событий, предотвращая дубликаты и ненужные срабатывания
 */

import { registerFieldValue } from './formDataPreparer';

class FieldChangeHelper {
    constructor() {
        // Кэш последних значений полей для предотвращения дубликатов событий
        this.fieldValuesCache = new Map();
    }

    /**
     * Отправляет событие изменения поля, если значение действительно изменилось
     * @param {string} dataKey - Ключ поля (data-key)
     * @param {string} newValue - Новое значение
     * @returns {boolean} - true если событие было отправлено, false если значение не изменилось
     */
    dispatchFieldChange(dataKey, newValue) {
        // Проверяем, изменилось ли значение
        const cachedValue = this.fieldValuesCache.get(dataKey);

        if (cachedValue === newValue) {
            // Значение не изменилось, не отправляем событие
            return false;
        }

        // Обновляем кэш
        this.fieldValuesCache.set(dataKey, newValue);

        // Регистрируем значение в formDataPreparer для интеграции с preparePayload
        registerFieldValue(dataKey, newValue);

        // Отправляем событие для других контроллеров (conditional-formatting и т.д.)
        window.dispatchEvent(new CustomEvent(`field:changed:${dataKey}`, {
            detail: {
                dataKey: dataKey,
                value: newValue
            }
        }));

        return true;
    }

    /**
     * Очищает кэш для конкретного поля
     * @param {string} dataKey - Ключ поля
     */
    clearCache(dataKey) {
        this.fieldValuesCache.delete(dataKey);
    }

    /**
     * Очищает весь кэш
     */
    clearAllCache() {
        this.fieldValuesCache.clear();
    }
}

// Экспортируем синглтон
export const fieldChangeHelper = new FieldChangeHelper();
