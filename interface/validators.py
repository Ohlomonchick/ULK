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
