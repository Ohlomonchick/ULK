document.addEventListener("DOMContentLoaded", function () {
    const startButton = document.getElementById("start-now");
    const videoContainer = document.getElementById("video-container");
    const video = document.getElementById("exam-video");
    video.playbackRate = 1.5;

    if (startButton) {
        startButton.addEventListener("click", function () {
            videoContainer.classList.remove("hidden");
            const slug = startButton.dataset.slug;
            console.log("slug", slug);
            fetch('/api/press_button/start/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    slug: slug,
                    action: 'start'
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP Error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Server Response:", data);
                localStorage.setItem("reloadCompetitions", "true");
                video.classList.remove("is-hidden");
                video.play();

                setTimeout(function () {
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else if (data.error) {
                        console.error("Server Error:", data.error);
                    }
                }, 4000);
            })
            .catch(error => {
                console.error("Fetch Error:", error.message);
            });

            video.onended = function () {
                videoContainer.classList.add("hidden");
            };
        });
    }

    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }
});
