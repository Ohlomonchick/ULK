class ControlButtons {
    constructor() {
        this.video = document.getElementById('exam-video');
        this.resumeInput = document.getElementById('resume-minutes');
        this.resumeButton = document.getElementById('resume');
        this.modal = document.getElementById('delete-confirm-modal');
        this.pendingAction = null;
        this.pendingSlug = null;
        this.pendingKkzId = null;
        this.pendingButton = null;
        this.init();
    }

    init() {
        document.querySelectorAll('.control-button').forEach(button => {
            button.addEventListener('click', (e) => this.handleClick(e));
        });

        // Обновление текста кнопки при изменении значения в поле ввода
        if (this.resumeInput && this.resumeButton) {
            this.updateResumeButtonText();
            this.resumeInput.addEventListener('input', () => this.updateResumeButtonText());
        }

        // Modal handlers - используем делегирование событий для надежности
        this.setupModalHandlers();
    }

    setupModalHandlers() {
        // Базовая настройка - обработчики будут привязаны при показе модального окна
        // Это гарантирует, что элементы уже в DOM
    }

    updateResumeButtonText() {
        const minutes = parseInt(this.resumeInput.value, 10) || 15;
        this.resumeButton.textContent = `Продлить на ${minutes} минут`;
    }

    showModal() {
        if (this.modal) {
            this.modal.classList.add('is-active');
            // Привязываем обработчики при показе модального окна для гарантии
            this.attachModalHandlers();
        }
    }

    attachModalHandlers() {
        // Привязываем обработчики при показе модального окна
        // Используем once: true чтобы избежать дублирования обработчиков
        const modalClose = document.getElementById('modal-close');
        const modalCancel = document.getElementById('modal-cancel-delete');
        const modalConfirm = document.getElementById('modal-confirm-delete');
        const modalBackground = this.modal ? this.modal.querySelector('.modal-background') : null;

        if (modalClose) {
            modalClose.onclick = (e) => {
                e.preventDefault();
                this.closeModal();
            };
        }
        if (modalCancel) {
            modalCancel.onclick = (e) => {
                e.preventDefault();
                this.closeModal();
            };
        }
        if (modalConfirm) {
            modalConfirm.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.confirmDelete();
            };
        }
        if (modalBackground) {
            modalBackground.onclick = (e) => {
                e.preventDefault();
                this.closeModal();
            };
        }
    }

    closeModal() {
        if (this.modal) {
            this.modal.classList.remove('is-active');
        }
        this.pendingAction = null;
        this.pendingSlug = null;
        this.pendingKkzId = null;
        this.pendingButton = null;
    }

    confirmDelete() {
        if (!this.pendingAction) {
            console.error('No pending action to confirm');
            this.closeModal();
            return;
        }

        // Сохраняем значения перед очисткой
        const action = this.pendingAction;
        const slug = this.pendingSlug;
        const kkzId = this.pendingKkzId;
        let button = this.pendingButton;

        // Закрываем модальное окно
        this.closeModal();

        // Находим кнопку удаления, если она не была сохранена
        if (!button) {
            button = document.getElementById('delete-from-platform');
        }

        // Очищаем pending значения
        this.pendingAction = null;
        this.pendingSlug = null;
        this.pendingKkzId = null;
        this.pendingButton = null;

        // Вызываем pressButton
        this.pressButton(action, slug, kkzId, button);
    }

    handleClick(event) {
        const button = event.currentTarget;
        const action = button.dataset.action;
        const instanceType = button.dataset.instanceType;
        const slug = button.dataset.slug;
        const kkzId = button.dataset.kkzId;

        if (action === 'end') {
            const confirmMessage = instanceType === 'kkz'
                ? 'Вы уверены что хотите завершить ККЗ?'
                : 'Вы уверены что хотите завершить работу?';

            if (!confirm(confirmMessage)) {
                return;
            }
        }

        if (action === 'delete') {
            // Сохраняем параметры для подтверждения
            this.pendingAction = action;
            this.pendingSlug = slug;
            this.pendingKkzId = kkzId;
            this.pendingButton = button;
            this.showModal();
            return;
        }

        if (action === 'start' && this.video) {
            this.showVideo(() => {
                this.pressButton(action, slug, kkzId, button);
            });
        } else {
            this.pressButton(action, slug, kkzId, button);
        }
    }

    showVideo(callback) {
        this.video.style.display = "block";
        this.video.classList.remove('is-hidden');
        this.video.play();

        this.video.onended = () => {
            this.video.style.display = "none";
            if (callback) callback();
        };
    }

    pressButton(action, slug = null, kkzId = null, button = null) {
        // Находим кнопку, если не передана
        if (!button) {
            if (action === 'delete') {
                button = document.getElementById('delete-from-platform');
            } else {
                button = document.querySelector(`[data-action="${action}"]`);
            }
        }

        // Добавляем класс загрузки
        if (button) {
            button.classList.add('is-loading');
            button.disabled = true;
        } else {
            console.warn(`Button not found for action: ${action}`);
        }

        const body = slug ? { slug: slug } : { kkz_id: kkzId };
        
        // Добавляем количество минут для действия resume
        if (action === 'resume' && this.resumeInput) {
            body.minutes = parseInt(this.resumeInput.value, 10) || 15;
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        fetch(`/api/press_button/${action}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(body)
        })
        .then(response => response.json())
        .then(data => {
            // Убираем класс загрузки
            if (button) {
                button.classList.remove('is-loading');
                button.disabled = false;
            }

            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            } else if (data.error) {
                alert('Ошибка: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Убираем класс загрузки при ошибке
            if (button) {
                button.classList.remove('is-loading');
                button.disabled = false;
            }
            alert('Произошла ошибка');
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.control-button')) {
        window.controlButtons = new ControlButtons();
    }
});