# Class Diagram Description - Cyberpolygon Web Service

## Назначение

Этот документ описывает 3 class-диаграммы по логическим уровням приложения:

1. `Meta Files/application_layer_class_diagram.plantuml`
2. `Meta Files/business_logic_layer_class_diagram.plantuml`
3. `Meta Files/data_management_layer_class_diagram.plantuml`

Диаграммы отражают не полный перечень классов, а ключевые сущности и важные связи:
- наследование;
- реализация интерфейсов;
- управление и оркестрацию процессов;
- критичные зависимости между слоями.

---

## Легенда

- `--|>`: наследование.
- `<|..`: реализация интерфейса классом.
- `-->`: явная зависимость (объект использует другой объект).
- `..>`: зависимость/использование (вызов сервиса, формы, API, модуля).
- `--`: ассоциация (устойчивая связь между сущностями).
- `o--`: агрегация (объект содержит ссылку на другой как часть структуры).
- `*--`: композиция (жизненный цикл части управляется владельцем).

---

## Application Layer

Файл: `Meta Files/application_layer_class_diagram.plantuml`

### Что показано

- Иерархия ключевых Django views:
  - `CompetitionHistoryListView --|> CompetitionListView`
  - `TeamCompetitionListView --|> CompetitionListView`
  - `TeamCompetitionDetailView --|> CompetitionDetailView`
- Только два блока: `Views` и `Frontend JS` (без форм/моделей).
- Все классы, реально объявленные в `assets/js`:
  - `CountdownTimer`
  - `TasksController`
  - `ControlButtons`
  - `SolutionsTable`
  - `ExportRating`
- Модульные контроллеры, представленные как классы:
  - `PnetController`
  - `CmdController`
  - `IframeController`
- Связь консольных контроллеров с iframe-слоем:
  - `PnetController --> IframeController`
  - `CmdController --> IframeController`
- Реализация общего интерфейса режимов консоли:
  - `IConsoleModeController <|.. PnetController`
  - `IConsoleModeController <|.. CmdController`

### Почему это важно

Диаграмма сфокусирована на frontend-view связке: какие view подключают ключевые JS-классы и как организованы контроллеры консольных режимов.

---

## Business Logic Layer

Файл: `Meta Files/business_logic_layer_class_diagram.plantuml`

### Что показано

- Оркестрация в формах:
  - `TeamCompetitionForm --|> CompetitionForm`
  - `SimpleCompetitionForm` выбирает путь через `CompetitionForm` или `TeamCompetitionForm`.
  - `KkzForm`/`SimpleKkzForm` используют общий билдер (`KkzCompetitionBuilder`).
- Управление сессией PNET:
  - `ISessionManager <|.. PNetSessionManager`
  - `AdminPNetSessionRegistry o-- PNetSessionManager` (глобальная/переиспользуемая сессия).
  - `PNetSessionManager` инкапсулирует операции создания/удаления лаб и работы с пользователями в PNET.
- Конвейер развертывания флагов:
  - `FlagDeploymentQueue *-- FlagDeploymentTask`
  - `FlagDeploymentTask -> TaskStatus`
  - `FlagDeploymentService -> LabTopology -> SSHTaskFactory/SSHTaskProcessor -> SSHConnectionTask`

### Почему это важно

Диаграмма фиксирует основные управляющие контуры системы:
- как формы запускают provisioning;
- как устроен поток deploy флагов;
- где находятся точки интеграции с внешними API (PNET, dynamic config).

---

## Data Management Layer

Файл: `Meta Files/data_management_layer_class_diagram.plantuml`

### Что показано

- Основные доменные модели и связи:
  - `Lab` композитно связан с `LabLevel`, `LabTaskType`, `LabTask`, `LabNode`.
  - `Competition` с `Lab`, `LabLevel`, `LabTask`, `Platoon`, `User`, `Kkz`.
  - `TeamCompetition --|> Competition`.
  - Композиционные контуры назначений: `Competition *-- Competition2User`, `TeamCompetition *-- TeamCompetition2Team`.
  - Контур ККЗ: `Kkz`, `KkzLab`, `KkzPreview`.
  - `Answers` как факт решения.
- Важные lifecycle-зависимости моделей от бизнес-сервисов:
  - post-create/delete операции через `PNetSessionManager`;
  - `tasks_changed` через `FlagDeploymentService`.
- Dynamic config:
  - `IWorkerCredentialsProvider <|.. WorkerCredentialsProvider`
  - `WorkerCredentialsProvider -> ConfigEntry`.

### Почему это важно

Диаграмма показывает не только структуру БД, но и поведение моделей в жизненном цикле (сигналы, удаление с платформы, генерация/деплой флагов), что критично для понимания реальной архитектуры.

### Стиль представления

- Из названий пакетов убраны ссылки на файлы.
- Убраны кратности (`1`, `0..*`) для снижения визуального шума.
- Используется `skinparam linetype ortho` для более читаемых трасс связей.
- Убраны `note`-блоки.

---

## Связь между диаграммами

- **Application Layer** инициирует пользовательские сценарии.
- **Business Logic Layer** оркестрирует процессы и интеграции.
- **Data Management Layer** хранит состояние и запускает lifecycle-логику через сигналы/методы моделей.

Вместе эти 3 диаграммы дают целостное представление о ключевых классах и их взаимодействиях без перегрузки второстепенными элементами.
