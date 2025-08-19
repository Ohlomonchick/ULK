document.addEventListener('DOMContentLoaded', function() {
    // Локализация TimeDurationWidget
    function localizeDurationWidget() {
        const durationWidget = document.querySelector('.durationwidget');
        if (!durationWidget) return;
        
        // Словарь переводов
        const translations = {
            'Days': 'дней',
            'Hours': 'часов', 
            'Minutes': 'минут',
            'Day': 'день',
            'Hour': 'час',
            'Minute': 'минута'
        };
        
        // Заменяем текст в span.help элементах
        const helpSpans = durationWidget.querySelectorAll('span.help');
        helpSpans.forEach(span => {
            let text = span.textContent.trim();
            // Убираем лишние пробелы и символы
            text = text.replace(/&nbsp;/g, '').replace(/\s+/g, ' ').trim();
            
            if (translations[text]) {
                span.textContent = translations[text];
                span.className = 'duration-label';
                // Убираем инлайн-стили, чтобы CSS работал корректно
                span.removeAttribute('style');
            }
        });
        
        // Заменяем summary текст (например "1 Hour 30 Minutes")
        const summaryP = durationWidget.querySelector('p.help');
        if (summaryP && summaryP.textContent.match(/(Hour|Minute|Day)/)) {
            summaryP.classList.add('duration-summary');
            summaryP.innerHTML = '<i class="fas fa-clock"></i> ' + formatDurationSummary();
        }
        
        // Добавляем обработчики для live update summary
        const inputs = durationWidget.querySelectorAll('input[type="number"]');
        inputs.forEach(input => {
            input.addEventListener('input', updateDurationSummary);
        });
    }
    
    function formatDurationSummary() {
        const durationWidget = document.querySelector('.durationwidget');
        const inputs = durationWidget.querySelectorAll('input[type="number"]');
        
        const days = parseInt(inputs[0]?.value || 0);
        const hours = parseInt(inputs[1]?.value || 0);
        const minutes = parseInt(inputs[2]?.value || 0);
        
        let parts = [];
        
        if (days > 0) {
            const dayWord = days === 1 ? 'день' : (days < 5 ? 'дня' : 'дней');
            parts.push(`${days} ${dayWord}`);
        }
        
        if (hours > 0) {
            const hourWord = hours === 1 ? 'час' : (hours < 5 ? 'часа' : 'часов');
            parts.push(`${hours} ${hourWord}`);
        }
        
        if (minutes > 0) {
            const minWord = minutes === 1 ? 'минута' : (minutes < 5 ? 'минуты' : 'минут');
            parts.push(`${minutes} ${minWord}`);
        }
        
        return parts.length > 0 ? parts.join(' ') : 'Время не указано';
    }
    
    function updateDurationSummary() {
        const summaryP = document.querySelector('.durationwidget .duration-summary');
        if (summaryP) {
            summaryP.innerHTML = '<i class="fas fa-clock"></i> ' + formatDurationSummary();
        }
    }
    
    // Запускаем локализацию
    localizeDurationWidget();
    
    // Управление видео при отправке формы
    setupVideoForm();
});

function setupVideoForm() {
    const submitButton = document.getElementById('create-lab-button');
    const form = submitButton?.closest('form');
    const loadingContainer = document.getElementById('loading-container');
    const loadingText = document.getElementById('loading-text');
    const videoContainer = document.getElementById('lab-video-container');
    const video = document.getElementById('lab-video');
    
    if (!form || !submitButton || !loadingContainer || !loadingText || !videoContainer || !video) {
        return;
    }
    
    let redirectUrl = null;
    let responseReceived = false;
    let videoFinished = false;
    let loadingInterval = null;
    
    // Ускоряем видео как в competition_detail
    video.playbackRate = 1.5;
    
    // Фразы загрузки
    const loadingPhrases = [
        'Создаём лабораторные работы',
        'Поднимаем виртуальные машины',
        'Настраиваем сеть'
    ];
    
    // Обработчик клика на кнопку
    submitButton.addEventListener('click', function(e) {
        if (form.checkValidity()) {
            e.preventDefault();
            showLoadingAndSubmitForm();
        }
    });
    
    // Дублируем обработчик на submit формы на случай других способов отправки
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        showLoadingAndSubmitForm();
    });
    
    function showLoadingAndSubmitForm() {
        // Показываем анимацию загрузки
        loadingContainer.classList.remove('hidden');
        startLoadingAnimation();
        
        // Отправляем форму
        const formData = new FormData(form);
        
        fetch(window.location.pathname, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (response.redirected) {
                redirectUrl = response.url;
                responseReceived = true;
                stopLoadingAnimation();
                showVideo();
                handleRedirect();
            } else {
                // Ошибка формы - заменяем содержимое страницы
                return response.text().then(html => {
                    document.documentElement.innerHTML = html;
                    stopLoadingAnimation();
                });
            }
        })
        .catch(() => {
            stopLoadingAnimation();
        });
    }
    
    // Обработчик окончания видео
    video.addEventListener('ended', function() {
        videoFinished = true;
        handleRedirect();
    });
    
    function startLoadingAnimation() {
        let phraseIndex = 0;
        let dotCount = 0;
        
        loadingInterval = setInterval(() => {
            const phrase = loadingPhrases[phraseIndex];
            const dots = '.'.repeat(dotCount + 1);
            loadingText.textContent = phrase + dots;
            
            dotCount++;
            if (dotCount >= 5) {
                dotCount = 0;
                phraseIndex = (phraseIndex + 1) % loadingPhrases.length;
            }
        }, 500); // Меняем каждые 500мс
    }
    
    function stopLoadingAnimation() {
        if (loadingInterval) {
            clearInterval(loadingInterval);
            loadingInterval = null;
        }
        loadingContainer.classList.add('hidden');
    }
    
    function showVideo() {
        // Скрываем загрузку и показываем видео
        loadingContainer.classList.add('hidden');
        videoContainer.classList.remove('hidden');
        video.play();
    }
    
    function handleRedirect() {
        if (redirectUrl && responseReceived) {
            if (videoFinished) {
                // Видео закончилось - делаем редирект
                window.location.href = redirectUrl;
            }
            // Убираем затухание - видео остаётся ярким
        }
    }
    
    function hideVideo() {
        videoContainer.classList.add('hidden');
        video.pause();
        video.currentTime = 0;
    }
    
    function getCsrfToken() {
        const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
        return csrfInput?.value || '';
    }
}