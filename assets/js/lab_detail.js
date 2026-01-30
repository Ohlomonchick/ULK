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
            'Minute': 'минута',
            'Seconds': 'секунд',
            'Second': 'секунда'
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
        if (summaryP && summaryP.textContent.match(/(Hour|Minute|Second|Day)/)) {
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
        const seconds = parseInt(inputs[3]?.value || 0);
        let parts = [];
        
        function getPluralForm(num, forms) {
            const mod10 = num % 10;
            const mod100 = num % 100;
            if (mod10 === 1 && mod100 !== 11) {
                return forms[0]; 
            } else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
                return forms[1]; 
            } else {
                return forms[2];
            }
        }
        
        if (days > 0) {
            const dayWord = getPluralForm(days, ['день', 'дня', 'дней']);
            parts.push(`${days} ${dayWord}`);
        }
        
        if (hours > 0) {
            const hourWord = getPluralForm(hours, ['час', 'часа', 'часов']);
            parts.push(`${hours} ${hourWord}`);
        }
        
        if (minutes > 0) {
            const minWord = getPluralForm(minutes, ['минута', 'минуты', 'минут']);
            parts.push(`${minutes} ${minWord}`);
        }
        
        if (seconds > 0) {
            const secWord = getPluralForm(seconds, ['секунда', 'секунды', 'секунд']);
            parts.push(`${seconds} ${secWord}`);
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
    
    // Запускаем логику выбора заданий
    // Небольшая задержка на случай, если DOM еще не полностью готов
    setTimeout(function() {
        setupTaskSelectionLogic();
    }, 100);
});

// --- Логика для выбора заданий по группам ---
function setupTaskSelectionLogic() {
    const hiddenInput = document.getElementById('id_task_type_counts');
    const totalBadge = document.getElementById('total-tasks-badge');
    const groupBlocks = document.querySelectorAll('.task-group-block:not(.task-subtype-block)');

    if (!groupBlocks.length) return;

    // --- Функция обновления состояния ---
    function updateGlobalState() {
        let totalCount = 0;
        let totalSeconds = 0;
        let jsonData = {};
        
        // 1. Считаем обычные группы и подтипы 
        const subtypeBlocks = document.querySelectorAll('.task-subtype-block');
        const regularBlocks = document.querySelectorAll('.task-group-block:not(.task-parent-block):not(.task-subtype-block)');
        
        // Обрабатываем подтипы
        subtypeBlocks.forEach(block => {
            const groupId = block.getAttribute('data-group-id');
            const durationPerTask = parseFloat(block.getAttribute('data-duration')) || 0;
            
            const input = block.querySelector('.subtype-count-input');
            const count = parseInt(input?.value) || 0;

            totalCount += count;
            totalSeconds += (count * durationPerTask);
            
            const key = (groupId === 'null') ? null : parseInt(groupId);
            jsonData[key] = count;
        });
        
        // Обрабатываем обычные группы (не вложенные)
        regularBlocks.forEach(block => {
            const groupId = block.getAttribute('data-group-id');
            const durationPerTask = parseFloat(block.getAttribute('data-duration')) || 0;
            
            const input = block.querySelector('.task-count-input');
            const count = parseInt(input?.value) || 0;

            totalCount += count;
            totalSeconds += (count * durationPerTask);
            
            const key = (groupId === 'null') ? null : parseInt(groupId);
            jsonData[key] = count;
        });

        // 2. Обновляем UI
        if (totalBadge) totalBadge.innerText = `Всего: ${totalCount}`;
        if (hiddenInput) hiddenInput.value = JSON.stringify(jsonData);

        // 3. Обновляем виджет времени
        updateDurationWidget(totalSeconds);
    }
    
    // --- Обновление счетчика родителя на основе подтипов ---
    function updateParentCounter(parentBlock) {
        const parentId = parentBlock.getAttribute('data-parent-id');
        const subtypeBlocks = parentBlock.querySelectorAll('.task-subtype-block');
        
        let totalCount = 0;
        subtypeBlocks.forEach(subtypeBlock => {
            const input = subtypeBlock.querySelector('.subtype-count-input');
            totalCount += parseInt(input?.value) || 0;
        });
        
        const parentInput = parentBlock.querySelector('.parent-count-input');
        if (parentInput) {
            parentInput.value = totalCount;
        }
    }
    
    // --- Обновление счетчиков подтипов на основе родителя ---
    function updateSubtypesFromParent(parentBlock, count) {
        const subtypeBlocks = parentBlock.querySelectorAll('.task-subtype-block');
        const totalSubtypes = subtypeBlocks.length;
        if (totalSubtypes === 0) return;

        const maxValues = Array.from(subtypeBlocks).map(block => {
            const input = block.querySelector('.subtype-count-input');
            return parseInt(input?.getAttribute('max'), 10) || 0;
        });
        const totalMax = maxValues.reduce((sum, m) => sum + m, 0);
        const targetCount = Math.min(Math.max(0, parseInt(count, 10) || 0), totalMax);

        const assigned = maxValues.map(() => 0);
        let remaining = targetCount;
        let idx = 0;
        while (remaining > 0) {
            if (assigned[idx] < maxValues[idx]) {
                assigned[idx]++;
                remaining--;
            }
            idx = (idx + 1) % totalSubtypes;
        }

        subtypeBlocks.forEach((subtypeBlock, index) => {
            const input = subtypeBlock.querySelector('.subtype-count-input');
            const val = assigned[index] || 0;
            input.value = val;
            updateCheckboxesFromCount(subtypeBlock, val);
        });

        const parentInput = parentBlock.querySelector('.parent-count-input');
        if (parentInput) parentInput.value = targetCount;
    }

    // --- Обновление виджета времени ---
    function updateDurationWidget(totalSeconds) {
        const durationWidget = document.querySelector('.durationwidget');
        if (!durationWidget) return;

        const inputs = durationWidget.querySelectorAll('input[type="number"]');
        if (inputs.length < 3) return;
        
        const daysInput = inputs[0];
        const hoursInput = inputs[1];
        const minutesInput = inputs[2];
        const secondsInput = inputs.length > 3 ? inputs[3] : null;

        if (totalSeconds > 0) {
            const days = Math.floor(totalSeconds / (3600 * 24));
            let remainder = totalSeconds % (3600 * 24);
            
            const hours = Math.floor(remainder / 3600);
            remainder = remainder % 3600;
            
            const minutes = Math.floor(remainder / 60);
            const seconds = Math.round(remainder % 60);

            daysInput.value = days;
            hoursInput.value = hours;
            minutesInput.value = minutes;
            
            if (secondsInput) {
                secondsInput.value = seconds;
            } else if (seconds > 0) {
                minutesInput.value = minutes + 1;
            }
        } else {
            daysInput.value = 0;
            hoursInput.value = 0;
            minutesInput.value = 0;
            if (secondsInput) {
                secondsInput.value = 0;
            }
        }
        
        // Триггерим событие, чтобы обновился текстовый summary
        daysInput.dispatchEvent(new Event('input'));
    }

    // --- Обновление чекбоксов на основе количества ---
    function updateCheckboxesFromCount(block, count) {
        const checkboxes = Array.from(block.querySelectorAll('.task-checkbox'));
        checkboxes.forEach(cb => cb.checked = false);
        if (count > 0) {
            const shuffled = [...checkboxes].sort(() => 0.5 - Math.random());
            shuffled.slice(0, count).forEach(cb => cb.checked = true);
        }
    }

    // --- Обработчики для типов ---
    const parentBlocks = document.querySelectorAll('.task-parent-block');
    parentBlocks.forEach(parentBlock => {
        const parentInput = parentBlock.querySelector('.parent-count-input');
        const parentSelectAll = parentBlock.querySelector('.parent-select-all-checkbox');
        const subtypeBlocks = parentBlock.querySelectorAll('.task-subtype-block');
        
        // Обработчик для чекбокса типа
        if (parentSelectAll) {
            parentSelectAll.addEventListener('change', function() {
                if (this.checked) {
                    // Выбираем все задания всех подтипов
                    subtypeBlocks.forEach(subtypeBlock => {
                        const input = subtypeBlock.querySelector('.subtype-count-input');
                        const max = parseInt(input?.getAttribute('max')) || 0;
                        input.value = max;
                        updateCheckboxesFromCount(subtypeBlock, max);
                    });
                    updateParentCounter(parentBlock);
                } else {
                    // Снимаем выбор со всех подтипов
                    subtypeBlocks.forEach(subtypeBlock => {
                        const input = subtypeBlock.querySelector('.subtype-count-input');
                        input.value = 0;
                        updateCheckboxesFromCount(subtypeBlock, 0);
                    });
                    updateParentCounter(parentBlock);
                }
                updateGlobalState();
            });
        }
        
        // Синхронизация чекбокса типа с состоянием подтипов
        function syncParentCheckbox() {
            const allSubtypesSelected = Array.from(subtypeBlocks).every(subtypeBlock => {
                const input = subtypeBlock.querySelector('.subtype-count-input');
                const max = parseInt(input?.getAttribute('max')) || 0;
                return parseInt(input?.value) === max && max > 0;
            });
            const anySubtypeSelected = Array.from(subtypeBlocks).some(subtypeBlock => {
                const input = subtypeBlock.querySelector('.subtype-count-input');
                return parseInt(input?.value) > 0;
            });
            
            if (parentSelectAll) {
                parentSelectAll.checked = allSubtypesSelected;
                parentSelectAll.indeterminate = anySubtypeSelected && !allSubtypesSelected;
            }
        }
        
        // Родительский счётчик
        function applyParentCount() {
            var val = parseInt(parentInput.value, 10);
            var max = parseInt(parentInput.getAttribute('max'), 10) || 0;
            if (isNaN(val) || val < 0) val = 0;
            if (val > max) val = max;
            parentInput.value = val;
            updateSubtypesFromParent(parentBlock, val);
            updateGlobalState();
        }
        if (parentInput) {
            parentInput.addEventListener('input', applyParentCount);
            parentInput.addEventListener('change', applyParentCount);
        }
        
        // Обработчики для каждого подтипа
        subtypeBlocks.forEach(subtypeBlock => {
            const subtypeInput = subtypeBlock.querySelector('.subtype-count-input');
            const checkboxes = Array.from(subtypeBlock.querySelectorAll('.task-checkbox'));
            const subtypeSelectAll = subtypeBlock.querySelector('.subtype-select-all-checkbox');
            
            if (!subtypeInput) return;
            
            // Обработчик для чекбокса подтипа (выбрать все задания подтипа)
            if (subtypeSelectAll) {
                subtypeSelectAll.addEventListener('change', function() {
                    const max = parseInt(subtypeInput?.getAttribute('max')) || 0;
                    if (this.checked) {
                        // Выбираем все задания подтипа
                        subtypeInput.value = max;
                        updateCheckboxesFromCount(subtypeBlock, max);
                    } else {
                        // Снимаем выбор со всех заданий подтипа
                        subtypeInput.value = 0;
                        updateCheckboxesFromCount(subtypeBlock, 0);
                    }
                    updateParentCounter(parentBlock);
                    syncParentCheckbox();
                    updateGlobalState();
                });
            }
            
            // Функция синхронизации чекбокса подтипа
            function syncSubtypeCheckbox() {
                if (subtypeSelectAll) {
                    const checkedCount = checkboxes.filter(c => c.checked).length;
                    const max = parseInt(subtypeInput?.getAttribute('max')) || 0;
                    subtypeSelectAll.checked = checkedCount === max && max > 0;
                    subtypeSelectAll.indeterminate = checkedCount > 0 && checkedCount < max;
                }
            }
            
            // Обработчик для чекбоксов заданий подтипа
            checkboxes.forEach(cb => {
                cb.addEventListener('change', function() {
                    const checkedCount = checkboxes.filter(c => c.checked).length;
                    subtypeInput.value = checkedCount;
                    syncSubtypeCheckbox();
                    updateParentCounter(parentBlock);
                    syncParentCheckbox();
                    updateGlobalState();
                });
            });
            
            // Счётчик подтипа
            function applySubtypeCount() {
                var val = parseInt(subtypeInput.value, 10);
                var max = parseInt(subtypeInput.getAttribute('max'), 10) || 0;
                if (isNaN(val) || val < 0) val = 0;
                if (val > max) val = max;
                subtypeInput.value = val;
                updateCheckboxesFromCount(subtypeBlock, val);
                syncSubtypeCheckbox();
                updateParentCounter(parentBlock);
                syncParentCheckbox();
                updateGlobalState();
            }
            subtypeInput.addEventListener('input', applySubtypeCount);
            subtypeInput.addEventListener('change', applySubtypeCount);

            // Инициализация синхронизации чекбокса подтипа
            syncSubtypeCheckbox();
        });
    });

    // --- Обработчики для обычных групп (не вложенных) ---
    const regularBlocks = document.querySelectorAll('.task-group-block:not(.task-parent-block):not(.task-subtype-block)');
    regularBlocks.forEach(block => {
        const numberInput = block.querySelector('.task-count-input');
        const checkboxes = Array.from(block.querySelectorAll('.task-checkbox'));
        
        if (!numberInput) return;
        
        checkboxes.forEach(cb => {
            cb.addEventListener('change', function() {
                const checkedCount = checkboxes.filter(c => c.checked).length;
                numberInput.value = checkedCount;
                updateGlobalState();
            });
        });

        numberInput.addEventListener('input', function() {
            let val = parseInt(this.value);
            const max = parseInt(this.getAttribute('max')) || 0;

            if (isNaN(val) || val < 0) val = 0;
            if (val > max) val = max;
            this.value = val;

            updateCheckboxesFromCount(block, val);
            updateGlobalState();
        });
    });

    // Инициализация
    updateGlobalState();
}


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