import re
from jsonschema import validate, ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

# Define the JSON schema
schema = {
    "type": "array",
    "items": {
        "type": "object"
    }
}


def validate_top_level_array(value):
    """Validate that the JSON data is an array at the top level."""
    try:
        # Use jsonschema to validate the JSON data against the schema
        validate(instance=value, schema=schema)
    except ValidationError as e:
        raise DjangoValidationError("Ошибка: поле должно содержать список JSON: [{}, ...]") from e


def validate_lab_task_json_config(value):
    """
    Валидатор для JSON-конфигурации заданий лабораторной работы.
    
    Проверяет:
    1. Структуру JSON
    2. Обязательные поля: task_type, answer, regex
    3. Допустимые значения task_type: 'input' или 'state'
    4. Соответствие answer регулярному выражению regex
    """
    if not value:
        return
    
    if not isinstance(value, dict):
        raise DjangoValidationError("JSON-конфигурация должна быть объектом")
    
    # Проверяем обязательные поля
    required_fields = ['task_type', 'answer', 'regex']
    missing_fields = [field for field in required_fields if field not in value]
    
    if missing_fields:
        raise DjangoValidationError(
            f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
        )
    
    # Проверяем допустимые значения task_type
    valid_task_types = ['input', 'state']
    task_type = value.get('task_type')
    
    if task_type not in valid_task_types:
        raise DjangoValidationError(
            f"Недопустимое значение task_type: '{task_type}'. "
            f"Допустимые значения: {', '.join(valid_task_types)}"
        )
    
    # Проверяем, что regex является корректным регулярным выражением
    regex_pattern = value.get('regex')
    if not isinstance(regex_pattern, str):
        raise DjangoValidationError("Поле 'regex' должно быть строкой")
    
    try:
        re.compile(regex_pattern)
    except re.error as e:
        raise DjangoValidationError(f"Некорректное регулярное выражение 'regex': {e}")
    
    # Главная проверка: answer должен соответствовать regex
    answer = value.get('answer')
    if not isinstance(answer, str):
        raise DjangoValidationError("Поле 'answer' должно быть строкой")
    
    try:
        if not re.match(regex_pattern, answer):
            raise DjangoValidationError(
                f"Ответ '{answer}' не соответствует регулярному выражению '{regex_pattern}'. "
                f"Проверьте корректность данных."
            )
    except re.error as e:
        raise DjangoValidationError(f"Ошибка при проверке ответа с регулярным выражением: {e}")
