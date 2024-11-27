document.addEventListener("DOMContentLoaded", function () {
    const startButton = document.getElementById("start-now");
    const videoContainer = document.getElementById("video-container");
    const video = document.getElementById("exam-video");

    if (startButton) {
        startButton.addEventListener("click", function () {
            videoContainer.classList.remove("hidden");
            const labName = startButton.dataset.lab;

            fetch('/api/press_button/start/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    lab: labName,
                    action: 'start',
                })
            })
            .then(response => response.json())
            .then(data => {
                localStorage.setItem("reloadCompetitions", "true");
                video.classList.remove("is-hidden");
                video.play();

                setTimeout(function() {
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else if (data.error) {
                        console.error("Ошибка:", data.error);
                    }
                }, 6200);
            })
            video.onended = function () {
                videoContainer.classList.add("hidden");
            };
        });
    }

    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }
});