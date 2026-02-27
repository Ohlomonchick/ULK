"""Тесты парсинга и валидации поля answer для заданий с выбором ответа."""
import unittest

from django.test import TestCase

from interface.task_answer_parsing import (
    parse_answer_choices,
    get_display_choices_from_parsed,
    AnswerChoiceParseError,
)
from interface.forms import LabTaskInlineForm
from interface.models import Lab, LabTask


class ParseAnswerChoicesTestCase(unittest.TestCase):
    """Тесты функции parse_answer_choices."""

    def test_returns_none_for_empty(self):
        self.assertIsNone(parse_answer_choices(''))
        self.assertIsNone(parse_answer_choices('   \n  '))

    def test_returns_none_when_no_choice_markers(self):
        self.assertIsNone(parse_answer_choices('just some text'))
        self.assertIsNone(parse_answer_choices('^regex$'))

    def test_single_choice_valid(self):
        raw = '''- Ответ 1
- Ответ 2
# Ответ 3
- Ответ 4'''
        result = parse_answer_choices(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result['mode'], 'single')
        self.assertEqual(len(result['options']), 4)
        self.assertEqual([o['correct'] for o in result['options']], [False, False, True, False])
        self.assertEqual([o['text'] for o in result['options']], ['Ответ 1', 'Ответ 2', 'Ответ 3', 'Ответ 4'])

    def test_multiple_choice_valid(self):
        raw = '''- Ответ 1
- Ответ 2
* Ответ 3
* Ответ 4'''
        result = parse_answer_choices(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result['mode'], 'multiple')
        self.assertEqual(len(result['options']), 4)
        self.assertEqual([o['correct'] for o in result['options']], [False, False, True, True])

    def test_two_hashes_raises(self):
        raw = '''- A
# B
# C'''
        with self.assertRaises(AnswerChoiceParseError) as ctx:
            parse_answer_choices(raw)
        self.assertIn('одна строка с #', str(ctx.exception))

    def test_mix_hash_and_star_raises(self):
        raw = '''# A
* B'''
        with self.assertRaises(AnswerChoiceParseError) as ctx:
            parse_answer_choices(raw)
        self.assertIn('Нельзя смешивать', str(ctx.exception))

    def test_only_minus_raises(self):
        raw = '''- A
- B'''
        with self.assertRaises(AnswerChoiceParseError) as ctx:
            parse_answer_choices(raw)
        self.assertIn('Укажите правильный ответ', str(ctx.exception))

    def test_line_without_marker_raises(self):
        raw = '''- A
Wrong line
# B'''
        with self.assertRaises(AnswerChoiceParseError) as ctx:
            parse_answer_choices(raw)
        self.assertIn('должна начинаться', str(ctx.exception))


class GetDisplayChoicesFromParsedTestCase(unittest.TestCase):
    """Тесты get_display_choices_from_parsed."""

    def test_strips_correct_flag(self):
        from interface.task_answer_parsing import get_display_choices_from_parsed
        parsed = {
            'mode': 'single',
            'options': [
                {'index': 0, 'text': 'A', 'correct': False},
                {'index': 1, 'text': 'B', 'correct': True},
            ]
        }
        display = get_display_choices_from_parsed(parsed)
        self.assertEqual(display['mode'], 'single')
        self.assertEqual(len(display['options']), 2)
        self.assertNotIn('correct', display['options'][0])
        self.assertNotIn('correct', display['options'][1])
        self.assertEqual(display['options'][1]['text'], 'B')
        self.assertEqual(display['options'][1]['index'], 1)


class LabTaskInlineFormCleanAnswerTestCase(TestCase):
    """Тесты валидации поля answer в LabTaskInlineForm."""

    def setUp(self):
        self.lab = Lab.objects.create(
            name='Test Lab',
            platform='NO',
            slug='test-lab',
            description='Test'
        )

    def test_valid_single_choice(self):
        form = LabTaskInlineForm(
            data={
                'lab': self.lab.pk,
                'answer': '- A\n- B\n# C',
            },
            instance=LabTask(lab=self.lab)
        )
        form.full_clean()
        self.assertNotIn('answer', form.errors)

    def test_valid_multiple_choice(self):
        form = LabTaskInlineForm(
            data={
                'lab': self.lab.pk,
                'answer': '- A\n* B\n* C',
            },
            instance=LabTask(lab=self.lab)
        )
        form.full_clean()
        self.assertNotIn('answer', form.errors)

    def test_free_text_allowed(self):
        form = LabTaskInlineForm(
            data={
                'lab': self.lab.pk,
                'answer': '^[0-9]+$',
            },
            instance=LabTask(lab=self.lab)
        )
        form.full_clean()
        self.assertNotIn('answer', form.errors)

    def test_two_hashes_error(self):
        form = LabTaskInlineForm(
            data={
                'lab': self.lab.pk,
                'answer': '- A\n# B\n# C',
            },
            instance=LabTask(lab=self.lab)
        )
        form.full_clean()
        self.assertIn('answer', form.errors)
        self.assertIn('одна строка с #', str(form.errors['answer']))

    def test_mix_hash_star_error(self):
        form = LabTaskInlineForm(
            data={
                'lab': self.lab.pk,
                'answer': '# A\n* B',
            },
            instance=LabTask(lab=self.lab)
        )
        form.full_clean()
        self.assertIn('answer', form.errors)
