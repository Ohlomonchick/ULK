/**
 * Контроллер для работы с заданиями и их проверкой (jQuery версия)
 */

class TasksController {
    constructor() {
        this.$checkBtn = $('#check-tasks-btn');
        this.$tasksContainer = $('#tasks-container');
        
        if (this.$checkBtn.length) {
            this.competitionSlug = this.$checkBtn.data('competition-slug');
            this.init();
        }
    }

    init() {
        // Привязываем обработчик к кнопке проверки
        this.$checkBtn.on('click', () => this.handleCheckTasks());
        
        // Загружаем начальный статус заданий
        this.loadTasksStatus();
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
        $.ajax({
            url: '/api/get_user_tasks_status/',
            method: 'GET',
            data: { competition_slug: this.competitionSlug }
        })
        .done(data => this.updateTasksUI(data.tasks))
        .fail(() => console.error('Error loading tasks status'));
    }

    /**
     * Обновляет UI заданий на основе данных
     */
    updateTasksUI(tasks) {
        tasks.forEach(task => {
            const $taskElement = $(`.task-item[data-task-id="${task.id}"]`);
            if (!$taskElement.length) return;

            const $statusTag = $taskElement.find('.task-status-tag');
            
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
            } else if (!hasIncorrectTag) {
                // Очищаем только если нет тега "Неверно"
                $statusTag.empty();
            }
        });
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
                }
            } else {
                // Если не было ответов для проверки, показываем уведомление
                this.showNotification('Обновлено', 'info');
            }
            
            // Всегда обновляем статусы заданий из БД
            // updateTasksUI теперь не затирает теги "Неверно"
            await this.loadTasksStatus();
        } catch (error) {
            console.error('Error in handleCheckTasks:', error);
            this.showNotification(`Ошибка: ${error.responseJSON?.error || error.message}`, 'danger');
        } finally {
            // Включаем кнопку обратно
            this.$checkBtn.prop('disabled', false).removeClass('is-loading');
        }
    }
}

// Инициализация при загрузке страницы
$(document).ready(() => {
    new TasksController();
});

