"""
Описания для админ-панели Django.
Содержит тексты документации для различных inline-форм.
"""

# Описание для SSH-нод
LAB_NODE_DESCRIPTION = """<strong>Настройка SSH-нод для развертывания флагов</strong><br><br>

<strong>1. Настройка нод:</strong><br>
Укажите имя ноды, логин и пароль пользователя, от которого будет создан файл с флагами.<br><br>

<strong>2. Автоматическое создание файла:</strong><br>
Веб-система автоматически создаст файл <code>/etc/configs/checker_conf.json</code> с правами 600 (читать может только владелец) следующего вида:<br>
<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto;">
{
  "TASK_1": "FLAG_krwnojvn26g32272r",
  "TASK_2": "FLAG_972hf9fh9202hf2u9",
  ...
}
</pre>
Где ключ - это идентификатор задания (task_id), который вы указываете при создании задания на веб-интерфейсе.<br><br>

<strong>3. Засчитывание флагов:</strong><br>
Флаги автоматически засчитываются как правильные ответы в заданиях, если у задания выбран тип "В форме тестирования" (т.е. задание имеет поле Вопрос)."""


# Описания для заданий в зависимости от типа
LAB_TASK_DESCRIPTIONS = {
    "CLASSIC": """<strong>Обычные задания</strong><br><br>

<strong>Настройка:</strong><br>
Для лабораторных работ с типом "Обычные" задания настраиваются просто: укажите <strong>Идентификатор задания</strong> (task_id) и <strong>Описание</strong>.<br><br>

<strong>Использование:</strong><br>
Задания отображаются пользователям в виде списка. Каждое задание идентифицируется по своему task_id. Флаги для таких заданий автоматически генерируются и развертываются на SSH-нодах, если они настроены.""",

    "JSON_CONFIGURED": """<strong>Задания с JSON-конфигурацией</strong><br><br>

<strong>Настройка:</strong><br>
Для лабораторных работ с типом "C JSON-конфигурацией" каждое задание содержит расширенную конфигурацию в поле <strong>JSON-конфигурация</strong>.<br><br>

<strong>Структура JSON-конфигурации:</strong><br>
<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto;">
{
  "id": "task_1",
  "task_type": "input",
  "answer": "correct_answer",
  "regex": "^correct_answer$"
}
</pre>

<strong>Поля конфигурации:</strong><br>
• <strong>id</strong> - идентификатор задания (должен совпадать с task_id)<br>
• <strong>task_type</strong> - тип задания: <code>"input"</code> или <code>"state"</code><br>
• <strong>answer</strong> - ожидаемый правильный ответ<br>
• <strong>regex</strong> - регулярное выражение для проверки ответа<br><br>

<strong>Важно:</strong> Ответ (answer) должен соответствовать указанному регулярному выражению (regex). Это проверяется при сохранении в админке.<br><br>

<strong>Примеры:</strong><br>
• Для задания типа "input": <code>{"id": "task_1", "task_type": "input", "answer": "password123", "regex": "^password\\d+$"}</code><br>
• Для задания типа "state": <code>{"id": "task_2", "task_type": "state", "answer": "running", "regex": "^running$"}</code>""",

    "TESTING": """<strong>Задания в форме тестирования</strong><br><br>

<strong>Настройка:</strong><br>
Для лабораторных работ с типом "В форме тестирования" каждое задание должно содержать:<br>
• <strong>Идентификатор задания</strong> (task_id)<br>
• <strong>Описание</strong> задания<br>
• <strong>Вопрос</strong> - текст вопроса, который будет отображаться пользователю<br>
• <strong>Ответ</strong> - правильный ответ на вопрос (опционально, если используется флаг)<br><br>

<strong>Работа с флагами:</strong><br>
• При назначении заданий пользователям автоматически генерируются уникальные флаги, если настроены SSH-ноды<br>
• Флаги развертываются на SSH-нодах в файле <code>/etc/configs/checker_conf.json</code><br>
• Флаги могут быть засчитаны как правильные ответы через веб-интерфейс или API<br>
• Флаг проверяется регистронезависимо и работает как альтернатива обычному ответу<br><br>

<strong>Использование:</strong><br>
Пользователи видят вопросы на веб-странице и могут вводить ответы. Система проверяет как обычный ответ (если указан), так и флаг. Задания могут быть зачтены через API, не только через ввод ответа на вебе.<br><br>
"""
}


def get_lab_task_description(tasks_type):
    """
    Возвращает описание для заданий в зависимости от типа лабораторной работы.
    
    Args:
        tasks_type: Тип заданий (CLASSIC, JSON_CONFIGURED, TESTING)
    
    Returns:
        str: HTML-описание для отображения в админке
    """
    return LAB_TASK_DESCRIPTIONS.get(tasks_type, LAB_TASK_DESCRIPTIONS["CLASSIC"])

