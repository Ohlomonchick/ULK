class CountdownTimer {
    constructor(countdownElement) {
        this.countdownElem = countdownElement;
        this.instanceType = countdownElement.dataset.instanceType; 
        this.instanceId = countdownElement.dataset.instanceId;
        this.end = false;
        this.iframeHidden = false;

        this.hours = parseInt(countdownElement.dataset.hours);
        this.minutes = parseInt(countdownElement.dataset.minutes);
        this.seconds = parseInt(countdownElement.dataset.seconds);

        const storageKey = `${this.instanceType}_end_${this.instanceId}`;
        if (localStorage.getItem(storageKey) === 'true') {
            this.end = true;
        }

        this.init();
    }

    init() {
        // Проверяем, не истекло ли время уже при загрузке
        if (this.hours === 0 && this.minutes === 0 && this.seconds === 0) {
            const completedText = this.instanceType === 'kkz' ? 'ККЗ завершено' : 'Работа завершена';
            this.countdownElem.textContent = completedText;
            this.end = true;
            const storageKey = `${this.instanceType}_end_${this.instanceId}`;
            localStorage.setItem(storageKey, 'true');
            setTimeout(() => this.hideIframeElements(), 100);
        }
        
        this.intervalId = setInterval(() => this.updateTimer(), 1000);
        this.syncIntervalId = setInterval(() => this.fetchTime(), 30000);
        this.fetchTime();
    }

    updateTimer() {
        const text = this.countdownElem.textContent.trim();
        const completedText = this.instanceType === 'kkz' ? 'ККЗ завершено' : 'Работа завершена';

        // Если таймер уже завершен и iframe скрыт, просто выходим
        if (text === completedText && this.iframeHidden) {
            return;
        }

        // Проверяем, не истекло ли время ДО декремента
        if (this.hours === 0 && this.minutes === 0 && this.seconds === 0) {
            this.countdownElem.textContent = completedText;
            if (!this.end) {
                this.end = true;
                const storageKey = `${this.instanceType}_end_${this.instanceId}`;
                localStorage.setItem(storageKey, 'true');
            }
            if (!this.iframeHidden) {
                this.hideIframeElements();
            }
            return;
        }

        // Если таймер уже завершен, но iframe еще не скрыт
        if (text === completedText) {
            if (!this.end) {
                this.end = true;
                const storageKey = `${this.instanceType}_end_${this.instanceId}`;
                localStorage.setItem(storageKey, 'true');
            }
            if (!this.iframeHidden) {
                this.hideIframeElements();
            }
            return;
        }

        // Декрементируем время
        if (this.seconds > 0) {
            this.seconds--;
        } else {
            if (this.minutes > 0) {
                this.minutes--;
                this.seconds = 59;
            } else {
                if (this.hours > 0) {
                    this.hours--;
                    this.minutes = 59;
                    this.seconds = 59;
                } else {
                    this.seconds = 0;
                }
            }
        }

        // Проверяем, не истекло ли время ПОСЛЕ декремента
        if (this.hours === 0 && this.minutes === 0 && this.seconds === 0) {
            this.countdownElem.textContent = completedText;
            if (!this.end) {
                this.end = true;
                const storageKey = `${this.instanceType}_end_${this.instanceId}`;
                localStorage.setItem(storageKey, 'true');
            }
            if (!this.iframeHidden) {
                this.hideIframeElements();
            }
            return;
        }

        // Защита от отрицательных значений
        if (this.hours < 0 || this.minutes < 0 || this.seconds < 0) {
            this.hours = 0;
            this.minutes = 0;
            this.seconds = 0;
            this.countdownElem.textContent = completedText;
            if (!this.end) {
                this.end = true;
                const storageKey = `${this.instanceType}_end_${this.instanceId}`;
                localStorage.setItem(storageKey, 'true');
            }
            if (!this.iframeHidden) {
                this.hideIframeElements();
            }
            return;
        }

        this.render();
    }

    render() {
        this.countdownElem.textContent =
            (this.hours < 10 ? '0' : '') + this.hours + ' : ' +
            (this.minutes < 10 ? '0' : '') + this.minutes + ' : ' +
            (this.seconds < 10 ? '0' : '') + this.seconds;
    }

    fetchTime() {
        const url = `/api/get_time/${this.instanceType}/${this.instanceId}/`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                this.hours = data.hours;
                this.minutes = data.minutes;
                this.seconds = data.seconds;
                this.render();
                
                // Проверяем, не истекло ли время после синхронизации
                if (this.hours === 0 && this.minutes === 0 && this.seconds === 0) {
                    if (!this.end) {
                        this.end = true;
                        const storageKey = `${this.instanceType}_end_${this.instanceId}`;
                        localStorage.setItem(storageKey, 'true');
                    }
                    const completedText = this.instanceType === 'kkz' ? 'ККЗ завершено' : 'Работа завершена';
                    this.countdownElem.textContent = completedText;
                    if (!this.iframeHidden) {
                        this.hideIframeElements();
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching time:', error);
            });
    }

    /**
     * Скрывает iframe и связанные элементы управления для не-superuser пользователей
     * когда время работы истекло
     */
    hideIframeElements() {
        // Если уже скрыт, не делаем ничего
        if (this.iframeHidden) {
            return;
        }

        const iframeContainer = document.querySelector('.iframe-container');
        if (!iframeContainer) {
            return;
        }

        // Проверяем, что контейнер видим (не скрыт)
        const containerStyle = window.getComputedStyle(iframeContainer);
        if (containerStyle.display === 'none') {
            this.iframeHidden = true;
            return;
        }

        // Список элементов для скрытия
        const elementsToHide = [
            '.iframe-container',
            '#iframeOverlay',
            '#collapseIframeBtn',
            '#sidebarExpandBtn',
            '#descriptionExpandBtn',
            '#sidebarPanel',
            '#descriptionPanel'
        ];

        elementsToHide.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                const currentStyle = window.getComputedStyle(element);
                if (currentStyle.display !== 'none') {
                    element.style.display = 'none';
                }
            }
        });

        // Останавливаем iframe, если он загружен
        const iframe = document.getElementById('pnetFrame');
        if (iframe) {
            try {
                iframe.src = 'about:blank';
            } catch (e) {
                // Игнорируем ошибки CORS
            }
        }

        this.iframeHidden = true;
    }
    
    destroy() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
        if (this.syncIntervalId) {
            clearInterval(this.syncIntervalId);
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const countdownElement = document.getElementById('countdown');
    if (countdownElement) {
        window.countdownTimer = new CountdownTimer(countdownElement);
        
        // Дополнительная проверка: если текст уже "Работа завершена", вызываем hideIframeElements
        const text = countdownElement.textContent.trim();
        const instanceType = countdownElement.dataset.instanceType;
        const completedText = instanceType === 'kkz' ? 'ККЗ завершено' : 'Работа завершена';
        
        if (text === completedText) {
            setTimeout(() => {
                if (window.countdownTimer && typeof window.countdownTimer.hideIframeElements === 'function') {
                    window.countdownTimer.hideIframeElements();
                }
            }, 500);
        }
    }
});