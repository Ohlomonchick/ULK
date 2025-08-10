$(document).ready(function() {
    // Конфигурация для разных типов кнопок
    const buttonConfigs = {
        'start-now': {
            action: 'start',
            showVideo: true,
            videoDelay: 4000
        },
        'end-now': {
            action: 'end',
            showVideo: false,
            videoDelay: 0
        },
        'resume': {
            action: 'resume',
            showVideo: false,
            videoDelay: 0
        }
    };

    // Инициализация видео для кнопки start-now
    const $video = $('#exam-video');
    if ($video.length) {
        $video[0].playbackRate = 1.5;
        
        $video.on('ended', function() {
            $('#video-container').addClass('hidden');
        });
    }

    // Универсальный обработчик для всех кнопок
    function handleButtonClick(buttonId, config) {
        const $button = $('#' + buttonId);
        
        if (!$button.length) return;

        $button.on('click', function() {
            const slug = $(this).data('slug');
            
            console.log(`${config.action} button clicked for slug:`, slug);
            
            // Показываем видео только для кнопки start-now
            if (config.showVideo) {
                $('#video-container').removeClass('hidden');
                $video.removeClass('is-hidden').get(0).play();
            }
            
            // Отключаем кнопку на время запроса
            $button.prop('disabled', true);
            
            // Отправляем запрос на сервер
            $.ajax({
                url: `/api/press_button/${config.action}/`,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                data: JSON.stringify({
                    slug: slug,
                    action: config.action
                }),
                success: function(data) {
                    console.log("Server Response:", data);
                    localStorage.setItem("reloadCompetitions", "true");
                    
                    // Перенаправляем с задержкой или сразу
                    const delay = config.videoDelay;
                    setTimeout(function() {
                        if (data.redirect_url) {
                            window.location.href = data.redirect_url;
                        }
                    }, delay);
                },
                error: function(xhr, status, error) {
                    console.error(`${config.action} Error:`, error);
                    $button.prop('disabled', false);
                }
            });
        });
    }

    // Инициализируем обработчики для всех кнопок
    Object.keys(buttonConfigs).forEach(buttonId => {
        handleButtonClick(buttonId, buttonConfigs[buttonId]);
    });

    // Утилитарные функции
    function getCsrfToken() {
        return $('meta[name="csrf-token"]').attr('content');
    }
});
