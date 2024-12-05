document.addEventListener("DOMContentLoaded", function () {
    const startButton = document.getElementById("start-now");
    const videoContainer = document.getElementById("video-container");
    const video = document.getElementById("exam-video");

    if (startButton) {
        startButton.addEventListener("click", function () {
            videoContainer.classList.remove("hidden");
            const labName = startButton.dataset.lab;
            const startTimeRaw = startButton.dataset.start;
            const finishTimeRaw = startButton.dataset.finish;

            let startTime, finishTime;
            try {
                startTime = parseLocalizedDate(startTimeRaw);
                finishTime = parseLocalizedDate(finishTimeRaw);
            } catch (error) {
                console.error("Date parsing error:", error.message);
                return;
            }

            console.log("Parsed Start Time:", startTime);
            console.log("Parsed Finish Time:", finishTime);

            fetch('/api/press_button/start/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    lab: labName,
                    action: 'start',
                    start: luxon.DateTime.fromJSDate(startTime).toUTC().toISO(),
                    finish: luxon.DateTime.fromJSDate(finishTime).toUTC().toISO(),
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
                }, 6200);
            })
            .catch(error => {
                console.error("Fetch Error:", error.message);
            });

            video.onended = function () {
                videoContainer.classList.add("hidden");
            };
        });
    }

    function parseLocalizedDate(dateStr) {
        const { DateTime } = luxon;

        if (!DateTime) {
            throw new Error("Luxon is not loaded");
        }

        const parsedDate = DateTime.fromFormat(dateStr, "d MMMM yyyy г. HH:mm", { locale: "ru" });
        if (!parsedDate.isValid) {
            throw new Error(`Invalid date format. Input: ${dateStr}`);
        }

        return parsedDate.toJSDate();
    }

    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }
});
