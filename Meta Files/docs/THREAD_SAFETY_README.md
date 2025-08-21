# Thread-Safety в Cyberpolygon

## Обзор

Проект Cyberpolygon использует многопоточность для оптимизации производительности, особенно при работе с PNet платформой. Это требует особого внимания к thread-safety.

## Ключевые компоненты

### 1. PNetSessionManager

**Проблема:** Класс `PNetSessionManager` используется в многопоточной среде через `ThreadPoolExecutor`, что может привести к race conditions при одновременном доступе к состоянию аутентификации.

**Решение:** Добавлена блокировка `threading.Lock()` для защиты всех операций с состоянием:

```python
class PNetSessionManager:
    def __init__(self):
        self._is_authenticated = False
        self._lock = threading.Lock()  # Блокировка для thread-safety
    
    def login(self):
        with self._lock:  # Атомарная проверка и установка флага
            if self._is_authenticated:
                return
            # ... логика логина
            self._is_authenticated = True
```

**Защищенные операции:**
- `login()` - атомарная проверка и установка флага аутентификации
- `logout()` - атомарная проверка и сброс флага
- `session_data` property - атомарная проверка состояния

### 2. Глобальная административная сессия

**Проблема:** Каждый `post_create` сигнал создавал новую сессию PNet, что приводило к множественным аутентификациям.

**Решение:** Создана глобальная административная сессия `ADMIN_PNET_SESSION` с thread-safe управлением:

```python
# Глобальная административная сессия PNet
ADMIN_PNET_SESSION = None
ADMIN_SESSION_LOCK = threading.Lock()

def get_admin_pnet_session():
    """Thread-safe получение глобальной сессии"""
    global ADMIN_PNET_SESSION
    with ADMIN_SESSION_LOCK:
        if ADMIN_PNET_SESSION is None:
            ADMIN_PNET_SESSION = PNetSessionManager()
        return ADMIN_PNET_SESSION

def ensure_admin_pnet_session():
    """Обеспечение готовности глобальной сессии с автоматическим логином"""
    session = get_admin_pnet_session()
    try:
        session.session_data
        return session
    except RuntimeError:
        session.login()
        return session
```

**Преимущества:**
- Одна аутентификация для всех операций
- Значительное ускорение работы
- Меньше нагрузки на PNet сервер
- Thread-safe доступ из всех потоков

### 3. ThreadPoolExecutor в forms.py

**Использование:** Параллельное создание записей `Competition2User` в базе данных с инициализацией глобальной сессии.

```python
# Инициализируем глобальную PNet сессию перед выполнением операций
if instance.lab.get_platform() == "PN":
    from interface.pnet_session_manager import ensure_admin_pnet_session
    ensure_admin_pnet_session()

with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_user = {executor.submit(create_single_competition_user, user): user 
                     for user in users}
```

**Thread-safety обеспечена:**
- Глобальная сессия инициализируется один раз перед выполнением futures
- Все `post_create` сигналы используют одну и ту же сессию
- Атомарные операции с состоянием аутентификации

## Архитектура thread-safety

### Уровни защиты:

1. **Глобальная переменная:** `ADMIN_SESSION_LOCK` защищает создание/сброс сессии
2. **Внутренняя блокировка:** `_lock` в `PNetSessionManager` защищает операции с состоянием
3. **Атомарные операции:** Все критические секции защищены блокировками

### Сценарии использования:

```python
# Сценарий 1: Параллельное создание пользователей
# 1. Инициализация глобальной сессии (один раз)
ensure_admin_pnet_session()

# 2. Параллельное выполнение futures
with ThreadPoolExecutor() as executor:
    futures = [executor.submit(create_user, user) for user in users]
    
# 3. Каждый post_create использует глобальную сессию
# (автоматически через ensure_admin_pnet_session)

# Сценарий 2: Ручные операции
session = ensure_admin_pnet_session()
session.create_lab_for_user(lab, username)
```

## Тестирование

Созданы тесты для проверки thread-safety:

- `interface/tests/test_thread_safety.py` - тесты базового thread-safety
- `interface/tests/test_global_session.py` - тесты глобальной сессии

### Ключевые тесты:

- `test_concurrent_access_to_global_session` - одновременный доступ из потоков
- `test_ensure_admin_pnet_session_reuse` - переиспользование сессии
- `test_global_session_thread_safety` - thread-safety при операциях

## Производительность

### Преимущества глобальной сессии:

- **Скорость:** Одна аутентификация вместо множественных
- **Эффективность:** Переиспользование соединения
- **Надежность:** Меньше точек отказа

### Метрики оптимизации:

```python
# До оптимизации: N аутентификаций для N пользователей
# После оптимизации: 1 аутентификация для N пользователей

# Примерное ускорение:
# - 10 пользователей: ~10x быстрее
# - 100 пользователей: ~100x быстрее
```

## Мониторинг

Для мониторинга работы глобальной сессии:

1. **Логирование:** Все операции с сессиями логируются
2. **Состояние:** Отслеживание `_is_authenticated` флага
3. **Ошибки:** Мониторинг исключений при операциях
