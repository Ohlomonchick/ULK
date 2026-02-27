"""
Парсинг и валидация поля answer заданий с выбором ответа (single/multiple choice).

Формат:
- Строки вида "- Текст", "* Текст", "# Текст": первый символ — маркер.
- Один правильный (single): ровно одна строка с #.
- Несколько правильных (multiple): одна или несколько строк с *, без #.
"""


class AnswerChoiceParseError(Exception):
    """Ошибка разбора или валидации формата выбора ответов."""
    pass


def parse_answer_choices(raw: str) -> dict | None:
    """
    Разбирает поле answer на варианты выбора.

    Возвращает None, если в тексте нет ни одной строки, начинающейся с -, * или #
    (задание считается с свободным ответом).

    Иначе возвращает:
    {
        'mode': 'single' | 'multiple',
        'options': [{'index': int, 'text': str, 'correct': bool}, ...]
    }

    При невалидном синтаксисе выбрасывает AnswerChoiceParseError.
    """
    if not raw or not raw.strip():
        return None

    lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
    if not lines:
        return None

    # Проверяем, есть ли хотя бы одна строка с маркером выбора
    markers = ('-', '*', '#')
    has_choice_marker = any(line.startswith(markers) for line in lines)
    if not has_choice_marker:
        return None

    options = []
    for i, line in enumerate(lines):
        first = line[0] if line else ''
        if first not in markers:
            raise AnswerChoiceParseError(
                f'Строка "{line[:50]}{"..." if len(line) > 50 else ""}" должна начинаться с одного из символов: -, *, #'
            )
        text = line[1:].strip()
        correct = first in ('*', '#')
        options.append({'index': i, 'text': text, 'correct': correct})

    hash_count = sum(1 for line in lines if line.startswith('#'))
    star_count = sum(1 for line in lines if line.startswith('*'))

    if hash_count >= 1 and star_count >= 1:
        raise AnswerChoiceParseError(
            'Нельзя смешивать # (один правильный ответ) и * (несколько правильных). '
            'Используйте только # для одного правильного или только * для нескольких.'
        )
    if hash_count > 1:
        raise AnswerChoiceParseError(
            f'Для одного правильного ответа допускается только одна строка с #. Найдено: {hash_count}.'
        )
    if hash_count == 1:
        return {'mode': 'single', 'options': options}
    if star_count >= 1:
        return {'mode': 'multiple', 'options': options}
    # только минусы — нет правильного ответа
    raise AnswerChoiceParseError(
        'Укажите правильный ответ: один вариант с # (один правильный) или один или несколько с * (несколько правильных).'
    )


def get_display_choices_from_parsed(parsed: dict) -> dict:
    """
    Возвращает структуру для отображения без признака правильности:
    {'mode': 'single'|'multiple', 'options': [{'index': i, 'text': str}, ...]}
    """
    if not parsed:
        return None
    return {
        'mode': parsed['mode'],
        'options': [{'index': opt['index'], 'text': opt['text']} for opt in parsed['options']]
    }
