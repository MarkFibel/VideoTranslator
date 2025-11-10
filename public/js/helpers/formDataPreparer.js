/**
 * Модуль для подготовки данных формы к отправке на API
 * 
 * Извлекает данные из формы, обрабатывает различные типы полей
 * и формирует структурированный payload для отправки.
 * 
 * Интеграция с fieldChangeHelper:
 * Модуль подписывается на события field:changed:* для получения значений
 * из сложных контроллеров (tracklist, eventgroup и т.д.)
 */

/**
 * Хранилище значений полей из событий field:changed
 */
const fieldChangedValues = new Map();

/**
 * Публичная функция для регистрации значения поля из внешних контроллеров
 * @param {string} fieldKey - Ключ поля
 * @param {any} value - Значение поля
 */
export function registerFieldValue(fieldKey, value) {
    fieldChangedValues.set(fieldKey, value);
}

/**
 * Очищает все сохраненные значения полей
 */
export function clearFieldValues() {
    fieldChangedValues.clear();
}

/**
 * Подготавливает payload для отправки на API
 * @param {HTMLFormElement} formElement - DOM-элемент формы
 * @param {Object} schema - JSON-схема формы
 * @returns {Promise<Object>} - Объект с данными для отправки
 */
export async function preparePayload(formElement, schema) {
    const formData = new FormData(formElement);
    const payload = {};

    // 1. Сбор базовых данных полей
    // Пропускаем поля с [] в имени - они будут обработаны как множественные select
    for (const [key, value] of formData.entries()) {
        // Пропускаем поля, оканчивающиеся на []
        if (key.endsWith('[]')) {
            continue;
        }
        payload[key] = value;
    }

    // 2. Применяем значения из событий field:changed (приоритет над FormData)
    for (const [fieldKey, fieldValue] of fieldChangedValues.entries()) {
        // Парсим JSON-строки обратно в массивы/объекты
        let parsedValue = fieldValue;
        if (typeof fieldValue === 'string') {
            // Специальная обработка булевых строк из чекбоксов
            if (fieldValue === 'true') {
                parsedValue = true;
            } else if (fieldValue === 'false') {
                parsedValue = false;
            } else {
                // Пытаемся распарсить как JSON
                try {
                    parsedValue = JSON.parse(fieldValue);
                } catch (e) {
                    // Если не JSON, используем как есть
                    parsedValue = fieldValue;
                }
            }
        }

        payload[fieldKey] = parsedValue;
    }

    // 3. Обработка checklist (чекбоксы с именами, заканчивающимися на [])
    const checklistGroups = new Map();
    formElement.querySelectorAll('input[type="checkbox"][name$="[]"]').forEach(checkbox => {
        if (checkbox.name) {
            // Убираем [] из имени поля для унификации
            const cleanName = checkbox.name.slice(0, -2);
            
            // Если значение уже есть из события field:changed, пропускаем
            if (fieldChangedValues.has(cleanName)) {
                return;
            }

            if (!checklistGroups.has(cleanName)) {
                checklistGroups.set(cleanName, []);
            }

            if (checkbox.checked) {
                checklistGroups.get(cleanName).push(checkbox.value);
            }
        }
    });

    // Добавляем собранные checklist в payload
    checklistGroups.forEach((values, name) => {
        payload[name] = values;
    });

    // 4. Обработка одиночных чекбоксов (checked/unchecked)
    // Исключаем чекбоксы, значения которых уже пришли из событий field:changed
    const checkboxes = formElement.querySelectorAll('input[type="checkbox"]:not([name$="[]"])');
    checkboxes.forEach(checkbox => {
        if (checkbox.name) {
            const dataKey = checkbox.getAttribute('data-key');

            // Если значение уже есть из события field:changed, не перезаписываем его
            if (dataKey && fieldChangedValues.has(dataKey)) {
                return;
            }

            payload[checkbox.name] = checkbox.checked;
        }
    });

    // 5. Обработка множественных select
    const multiSelects = formElement.querySelectorAll('select[multiple]');
    multiSelects.forEach(select => {
        if (select.name) {
            const dataKey = select.getAttribute('data-key');

            // Если значение уже есть из события field:changed, не перезаписываем
            if (dataKey && fieldChangedValues.has(dataKey)) {
                return;
            }

            // Убираем [] из имени поля для унификации
            const cleanName = select.name.endsWith('[]') ? select.name.slice(0, -2) : select.name;
            payload[cleanName] = Array.from(select.selectedOptions).map(opt => opt.value);
        }
    });

    // 6. Обработка radio buttons
    const radioGroups = new Set();
    formElement.querySelectorAll('input[type="radio"]').forEach(radio => {
        if (radio.name) {
            radioGroups.add(radio.name);
        }
    });

    radioGroups.forEach(groupName => {
        const dataKey = formElement.querySelector(`input[type="radio"][name="${groupName}"]`)?.getAttribute('data-key');

        // Если значение уже есть из события field:changed, не перезаписываем
        if (dataKey && fieldChangedValues.has(dataKey)) {
            return;
        }

        const checkedRadio = formElement.querySelector(`input[type="radio"][name="${groupName}"]:checked`);
        payload[groupName] = checkedRadio ? checkedRadio.value : null;
    });

    // 7. Извлечение метаданных полей (если схема предоставлена)
    if (schema) {
        payload._metadata = extractFieldsMetadata(formElement, schema);
    }

    // 8. Определение флагов типа лица
    payload._flags = {
        isIndividual: determineIsIndividual(payload),
        isLegal: determineIsLegal(payload),
    };

    return payload;
}

/**
 * Извлекает метаданные полей формы
 * @param {HTMLFormElement} formElement - DOM-элемент формы
 * @param {Object} schema - JSON-схема формы (формат formzilla с rows)
 * @returns {Object} - Метаданные полей
 */
function extractFieldsMetadata(formElement, schema) {
    const metadata = {};

    // Рекурсивная функция для поиска всех полей в схеме
    const findAllFieldsInSchema = (obj) => {
        const fields = {};
        
        const traverse = (item) => {
            if (!item || typeof item !== 'object') return;
            
            // Если это поле с ключом (component)
            if (item.key) {
                fields[item.key] = item;
            }
            
            // Рекурсивно обходим массивы
            if (Array.isArray(item)) {
                item.forEach(traverse);
            } else {
                // Рекурсивно обходим свойства объектов
                Object.values(item).forEach(traverse);
            }
        };
        
        traverse(obj);
        return fields;
    };

    // Извлекаем все поля из схемы если она предоставлена
    let schemaFields = {};
    if (schema) {
        schemaFields = findAllFieldsInSchema(schema);
    }

    // Проход по всем полям в DOM
    const allInputs = formElement.querySelectorAll('input, select, textarea');
    allInputs.forEach(field => {
        if (!field.name) return;
        
        // Убираем [] из имени поля для унификации ключей метаданных
        const fieldName = field.name.endsWith('[]') ? field.name.slice(0, -2) : field.name;
        const schemaField = schemaFields[fieldName];
        
        metadata[fieldName] = {
            type: field.type || field.tagName.toLowerCase(),
            required: field.hasAttribute('required'),
            label: field.dataset.label ||
                field.getAttribute('aria-label') ||
                field.getAttribute('placeholder') ||
                (schemaField?.label) ||
                fieldName,
        };

        // Для select-полей добавляем доступные опции из DOM
        if (field.tagName.toLowerCase() === 'select') {
            metadata[fieldName].options = Array.from(field.options)
                .filter(opt => opt.value) // Исключаем пустые placeholder-опции
                .map(opt => ({
                    value: opt.value,
                    text: opt.text
                }));
            
            // Также добавляем values из схемы если они есть (важно для backend обработки)
            if (schemaField?.values) {
                metadata[fieldName].values = schemaField.values;
            }
        }

        // Для числовых полей добавляем диапазоны
        if (field.type === 'number') {
            if (field.min) metadata[fieldName].min = field.min;
            if (field.max) metadata[fieldName].max = field.max;
            if (field.step) metadata[fieldName].step = field.step;
        }

        // Для текстовых полей добавляем паттерны
        if (field.pattern) {
            metadata[fieldName].pattern = field.pattern;
        }

        // Для всех полей добавляем ограничения длины
        if (field.minLength) metadata[fieldName].minLength = field.minLength;
        if (field.maxLength) metadata[fieldName].maxLength = field.maxLength;
    });

    return metadata;
}

/**
 * Определяет, является ли субъект физическим лицом
 * @param {Object} payload - Данные формы
 * @returns {boolean}
 */
function determineIsIndividual(payload) {
    // Логика определения на основе данных формы
    // Проверка наличия ИНН физлица (12 цифр)
    if (payload.inn) {
        const innStr = String(payload.inn).trim();
        return innStr.length === 12 && /^\d{12}$/.test(innStr);
    }

    // Дополнительные признаки физлица
    if (payload.personType === 'individual' ||
        payload.type === 'individual' ||
        payload.entity_type === 'individual') {
        return true;
    }

    // Если есть поля, характерные для физлица
    if (payload.lastName || payload.firstName || payload.middleName) {
        return true;
    }

    return false;
}

/**
 * Определяет, является ли субъект юридическим лицом
 * @param {Object} payload - Данные формы
 * @returns {boolean}
 */
function determineIsLegal(payload) {
    // Логика определения на основе данных формы
    // Проверка наличия ИНН юрлица (10 цифр)
    if (payload.inn) {
        const innStr = String(payload.inn).trim();
        return innStr.length === 10 && /^\d{10}$/.test(innStr);
    }

    // Дополнительные признаки юрлица
    if (payload.personType === 'legal' ||
        payload.type === 'legal' ||
        payload.entity_type === 'legal') {
        return true;
    }

    // Если есть поля, характерные для юрлица
    if (payload.companyName || payload.ogrn || payload.kpp) {
        return true;
    }

    return false;
}

/**
 * Валидирует данные формы (базовые проверки для использования в FormController)
 * @param {Object} payload - Подготовленные данные
 * @param {Object} schema - JSON-схема
 * @returns {Object} - Объект с ошибками { fieldName: "error message" }
 */
export function validateFormData(payload, schema) {
    const errors = {};

    // Проверка обязательных полей
    if (schema && schema.required) {
        schema.required.forEach(fieldName => {
            const value = payload[fieldName];

            // Проверяем на пустоту с учетом различных типов данных
            if (value === null ||
                value === undefined ||
                (typeof value === 'string' && value.trim() === '') ||
                (Array.isArray(value) && value.length === 0)) {
                errors[fieldName] = 'Это поле обязательно для заполнения';
            }
        });
    }

    // Проверка формата ИНН (базовая, детальная проверка в InnController)
    if (payload.inn) {
        const innStr = String(payload.inn).trim();
        if (!/^\d{10}$|^\d{12}$/.test(innStr)) {
            errors.inn = 'ИНН должен содержать 10 или 12 цифр';
        }
    }

    // Проверка email
    if (payload.email) {
        const emailStr = String(payload.email).trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(emailStr)) {
            errors.email = 'Введите корректный email адрес';
        }
    }

    // Проверка телефона (базовая)
    if (payload.phone) {
        const phoneStr = String(payload.phone).replace(/\D/g, '');
        if (phoneStr.length < 10 || phoneStr.length > 15) {
            errors.phone = 'Введите корректный номер телефона';
        }
    }

    // Проверка ОГРН (базовая длина)
    if (payload.ogrn) {
        const ogrnStr = String(payload.ogrn).trim();
        if (!/^\d{13}$|^\d{15}$/.test(ogrnStr)) {
            errors.ogrn = 'ОГРН должен содержать 13 или 15 цифр';
        }
    }

    // Проверка КПП (базовая длина)
    if (payload.kpp) {
        const kppStr = String(payload.kpp).trim();
        if (!/^\d{9}$/.test(kppStr)) {
            errors.kpp = 'КПП должен содержать 9 цифр';
        }
    }

    return errors;
}

/**
 * Очищает данные формы от пустых значений и служебных полей
 * @param {Object} payload - Исходные данные
 * @param {boolean} keepMetadata - Сохранять ли служебные поля (_metadata, _flags)
 * @returns {Object} - Очищенные данные
 */
export function cleanPayload(payload, keepMetadata = true) {
    const cleaned = {};

    Object.keys(payload).forEach(key => {
        const value = payload[key];

        // Пропускаем служебные поля если не нужно их сохранять
        if (!keepMetadata && (key.startsWith('_'))) {
            return;
        }

        // Пропускаем пустые значения
        if (value === null ||
            value === undefined ||
            (typeof value === 'string' && value.trim() === '') ||
            (Array.isArray(value) && value.length === 0)) {
            return;
        }

        cleaned[key] = value;
    });

    return cleaned;
}
