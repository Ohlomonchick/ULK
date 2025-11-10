class CountdownTimer {
    constructor(countdownElement) {
        this.countdownElem = countdownElement;
        this.instanceType = countdownElement.dataset.instanceType; 
        this.instanceId = countdownElement.dataset.instanceId;
        this.end = false;

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
        this.intervalId = setInterval(() => this.updateTimer(), 1000);
        this.syncIntervalId = setInterval(() => this.fetchTime(), 30000);
        this.fetchTime();
    }

    updateTimer() {
        const text = this.countdownElem.textContent.trim();
        const completedText = this.instanceType === 'kkz' ? 'ККЗ завершено' : 'Экзамен завершён';

        if (text === completedText) {
            return;
        }

        if (this.hours === 0 && this.minutes === 0 && this.seconds === 0) {
            this.countdownElem.textContent = completedText;
            if (!this.end) {
                this.end = true;
                const storageKey = `${this.instanceType}_end_${this.instanceId}`;
                localStorage.setItem(storageKey, 'true');
            }
            return;
        }

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
                }
            }
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
            })
            .catch(error => {
                console.error('Error fetching time:', error);
            });
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
    }
});