/**
 * Контроллер для работы с заданиями и их проверкой (jQuery версия)
 */

class TasksController {
    constructor() {
        this.$checkBtn = $('#check-tasks-btn');
        this.$tasksContainer = $('#tasks-container');
        
        if (this.$checkBtn.length) {
            this.competitionSlug = this.$checkBtn.data('competition-slug');
            this.isOneAttempt = this.$checkBtn.data('one-attempt') === true;
            this.init();
        }
    }

    init() {
        // Привязываем обработчик к кнопке проверки
        this.$checkBtn.on('click', () => this.handleCheckTasks());
        
        // Инициализируем модальное окно предупреждения
        this.initWarningModal();
        
        // Загружаем начальный статус заданий
        this.loadTasksStatus();
        
        // Автообновление счётчика и статусов заданий каждые 10 секунд (без отправки ответов)
        this._statusIntervalId = setInterval(() => this.loadTasksStatus(), 10000);
    }

    /**
     * Инициализирует модальное окно предупреждения для режима ONE_ATTEMPT
     */
    initWarningModal() {
        const $modal = $('#one-attempt-warning-modal');
        const $closeBtn = $('#one-attempt-modal-close');
        const $cancelBtn = $('#one-attempt-modal-cancel');
        
        // Закрытие модального окна
        const closeModal = () => {
            $modal.removeClass('is-active');
        };
        
        $closeBtn.on('click', closeModal);
        $cancelBtn.on('click', closeModal);
        $modal.find('.modal-background').on('click', closeModal);
        
        // НЕ вешаем обработчик на confirmBtn здесь - он будет в showWarningModal()
    }

    /**
     * Показывает модальное окно предупреждения
     */
    showWarningModal() {
        return new Promise((resolve, reject) => {
            const $modal = $('#one-attempt-warning-modal');
            const $confirmBtn = $('#one-attempt-modal-confirm');
            const $cancelBtn = $('#one-attempt-modal-cancel');
            
            // Перемещаем модальное окно в конец body, чтобы оно было поверх всего
            // Это особенно важно для полноэкранного режима iframe
            if ($modal.parent()[0] !== document.body) {
                $modal.appendTo('body');
            }
            
            // Удаляем старые обработчики
            $confirmBtn.off('click.warning');
            $cancelBtn.off('click.warning');
            
            // Добавляем новые обработчики
            $confirmBtn.on('click.warning', () => {
                $modal.removeClass('is-active');
                resolve(true);
            });
            
            $cancelBtn.on('click.warning', () => {
                $modal.removeClass('is-active');
                reject(false);
            });
            
            // Показываем модальное окно
            $modal.addClass('is-active');
        });
    }

    /**
     * Продолжает проверку после подтверждения в модальном окне
     */
    async proceedWithCheck() {
        // Отключаем кнопку на время проверки
        this.$checkBtn.prop('disabled', true).addClass('is-loading');
        
        try {
            const hasQuestions = this.hasQuestions();
            const answers = this.collectAnswers();
            
            if (hasQuestions && Object.keys(answers).length > 0) {
                // Есть вопросы и заполнены ответы - проверяем их
                const result = await this.checkAnswers(answers);
                
                if (result.success) {
                    this.showCheckResults(result.results);
                    // Сразу обновляем счётчик по результатам проверки (на проде get_user_tasks_status
                    // может приходить с задержкой реплики или падать — счётчик уже будет верным)
                    this.updateCounterFromCheckResults(result.results);
                }
            } else {
                // Если не было ответов для проверки, показываем уведомление
                this.showNotification('Обновлено', 'info');
            }
            
            // Всегда подтягиваем статусы из БД (может не успеть на проде — счётчик уже обновлён выше)
            await this.loadTasksStatus();
        } catch (error) {
            console.error('Error in proceedWithCheck:', error);
            this.showNotification(`Ошибка: ${error.responseJSON?.error || error.message}`, 'danger');
        } finally {
            // Включаем кнопку обратно
            this.$checkBtn.prop('disabled', false).removeClass('is-loading');
        }
    }

    /**
     * Получает CSRF токен из мета-тега
     */
    getCSRFToken() {
        return $('meta[name="csrf-token"]').attr('content') || 
               document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    }

    /**
     * Собирает ответы пользователя из полей ввода
     */
    collectAnswers() {
        const answers = {};
        
        $('.task-answer-input').each(function() {
            const taskId = $(this).data('task-id');
            const answer = $(this).val().trim();
            
            if (answer) {
                answers[taskId] = answer;
            }
        });
        
        return answers;
    }

    /**
     * Проверяет, есть ли вопросы в заданиях
     */
    hasQuestions() {
        return $('.task-answer-input').length > 0;
    }

    /**
     * Отправляет ответы на проверку
     */
    checkAnswers(answers) {
        return $.ajax({
            url: '/api/check_task_answers/',
            method: 'POST',
            contentType: 'application/json',
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            },
            data: JSON.stringify({
                competition_slug: this.competitionSlug,
                answers: answers
            })
        });
    }

    /**
     * Загружает текущий статус заданий
     */
    loadTasksStatus() {
        return $.ajax({
            url: '/api/get_user_tasks_status/',
            method: 'GET',
            data: { competition_slug: this.competitionSlug }
        })
        .done(data => this.updateTasksUI(data.tasks))
        .fail((xhr) => {
            console.error('Error loading tasks status', xhr.status, xhr.responseText);
        });
    }

    updateCounterFromCheckResults(results) {
        const $counter = $('#tasks-completion-counter');
        if (!$counter.length) return;
        const correctCount = Object.values(results).filter(r => r && r.status === 'correct').length;
        if (correctCount === 0) return;
        const current = parseInt($counter.find('.completed-count').text(), 10) || 0;
        const total = parseInt($counter.find('.total-count').text(), 10) || 0;
        this.updateCompletionCounter(current + correctCount, total);
    }

    /**
     * Обновляет UI заданий на основе данных
     */
    updateTasksUI(tasks) {
        const completedCount = tasks.filter(task => task.done).length;
        const totalCount = tasks.length;
        
        this.updateCompletionCounter(completedCount, totalCount);

        tasks.forEach(task => {
            const $taskElement = $(`.task-item[data-task-id="${task.id}"]`);
            if (!$taskElement.length) return;

            const $statusTag = $taskElement.find('.task-status-tag');
            const $answerInput = $taskElement.find('.task-answer-input');
            
            // Проверяем, есть ли уже тег "Неверно" - если есть, не трогаем его
            const hasIncorrectTag = $statusTag.find('.tag.is-danger').length > 0;
            
            if (task.done) {
                $statusTag.html(`
                    <span class="tag is-success has-text-white title is-6">
                        <span class="icon is-small">
                            <i class="fas fa-check"></i>
                        </span>
                        <span>Выполнено</span>
                    </span>
                `);
                
                // Убираем поле ввода для выполненного задания
                $taskElement.find('.field').remove();
            } else if (task.failed) {
                // Задание с неверным ответом (failed_tasks)
                if (!hasIncorrectTag) {
                    $statusTag.html(`
                        <span class="tag is-danger has-text-white title is-6">
                            <span class="icon is-small">
                                <i class="fas fa-times"></i>
                            </span>
                            <span>Неверный ответ</span>
                        </span>
                    `);
                }
                
                // Скрываем поле ввода полностью
                $taskElement.find('.field').hide();
            } else if (!hasIncorrectTag) {
                // Очищаем только если нет тега "Неверно"
                $statusTag.empty();
            }
        });
    }

    /**
     * Обновляет счётчик выполненных заданий
     */
    updateCompletionCounter(completed, total) {
        const $counter = $('#tasks-completion-counter');
        if ($counter.length) {
            $counter.find('.completed-count').text(completed);
            $counter.find('.total-count').text(total);
        }
    }

    /**
     * Показывает результаты проверки в UI
     */
    showCheckResults(results) {
        $.each(results, (taskId, result) => {
            const $taskElement = $(`.task-item[data-task-id="${taskId}"]`);
            if (!$taskElement.length) return;

            const $statusTag = $taskElement.find('.task-status-tag');
            $statusTag.empty();
            
            if (result.status === 'correct') {
                $statusTag.html(`
                    <span class="tag is-success has-text-white title is-6">
                        <span class="icon is-small">
                            <i class="fas fa-check"></i>
                        </span>
                        <span>Выполнено</span>
                    </span>
                `);
                
                // Убираем поле ввода для выполненного задания
                $taskElement.find('.field').remove();
            } else if (result.status === 'incorrect') {
                $statusTag.html(`
                    <span class="tag is-danger has-text-white title is-6">
                        <span class="icon is-small">
                            <i class="fas fa-times"></i>
                        </span>
                        <span>Неверно</span>
                    </span>
                `);
                
                // Подсвечиваем поле ввода красным
                $taskElement.find('.task-answer-input')
                    .removeClass('is-success')
                    .addClass('is-danger');
            }
        });
    }

    /**
     * Показывает уведомление пользователю
     */
    showNotification(message, type = 'info') {
        const $notification = $(`
            <div class="notification is-${type}" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
                <button class="delete"></button>
                ${message}
            </div>
        `);
        
        $('body').append($notification);
        
        // Обработчик закрытия
        $notification.find('.delete').on('click', () => $notification.remove());
        
        // Автоматическое скрытие через 3 секунды
        setTimeout(() => {
            $notification.fadeOut(300, () => $notification.remove());
        }, 3000);
    }

    /**
     * Обработчик нажатия на кнопку "Проверить"
     */
    async handleCheckTasks() {
        // Предотвращаем двойные клики
        if (this.$checkBtn.prop('disabled')) {
            return; // Уже обрабатывается
        }
        
        const hasQuestions = this.hasQuestions();
        const answers = this.collectAnswers();
        
        // Если режим ONE_ATTEMPT и есть ответы для проверки, показываем предупреждение
        if (this.isOneAttempt && hasQuestions && Object.keys(answers).length > 0) {
            try {
                await this.showWarningModal();
                // Пользователь подтвердил - продолжаем проверку
                // proceedWithCheck() сам заблокирует кнопку
                await this.proceedWithCheck();
            } catch {
                // Пользователь отменил - ничего не делаем
                return;
            }
        } else {
            // Обычная проверка без предупреждения
            // proceedWithCheck() сам заблокирует кнопку
            await this.proceedWithCheck();
        }
    }
}

// Инициализация при загрузке страницы
$(document).ready(() => {
    new TasksController();
});

