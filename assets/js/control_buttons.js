class ControlButtons {
    constructor() {
        this.video = document.getElementById('exam-video');
        this.init();
    }

    init() {
        
        document.querySelectorAll('.control-button').forEach(button => {
            button.addEventListener('click', (e) => this.handleClick(e));
        });
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

        if (action === 'start' && this.video) {
            this.showVideo(() => {
                this.pressButton(action, slug, kkzId);
            });
        } else {
            this.pressButton(action, slug, kkzId);
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

    pressButton(action, slug = null, kkzId = null) {
        const body = slug ? { slug: slug } : { kkz_id: kkzId };
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
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            } else if (data.error) {
                alert('Ошибка: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Произошла ошибка');
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.control-button')) {
        window.controlButtons = new ControlButtons();
    }
});