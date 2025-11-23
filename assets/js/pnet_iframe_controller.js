// Контроллер для управления iframe в PNET и CMD режимах


// Управление полноэкранным режимом iframe
function initializeIframeControls() {
    let isFullscreen = false;
    let originalIframeStyles = null;
    let sidebarExpanded = false;
    
    /**
     * Клонирует содержимое правой панели в выдвижную панель
     * Использует глубокое клонирование для сохранения всех элементов и атрибутов
     */
    function cloneSidebarContent() {
        const originalSidebar = $('.column.is-one-quarter');
        const sidebarPanelContent = $('#sidebarPanelContent');
        
        if (originalSidebar.length === 0 || sidebarPanelContent.length === 0) {
            return;
        }
        
        // Очищаем предыдущее содержимое
        sidebarPanelContent.empty();
        
        // Глубоко клонируем содержимое с сохранением всех атрибутов и обработчиков
        const clonedContent = originalSidebar.clone(true, true);
        
        // Удаляем классы, которые могут конфликтовать
        clonedContent.removeClass('is-one-quarter column');
        
        // Изменяем ID элементов, чтобы избежать конфликтов
        // Особенно важно для таймера и других элементов с уникальными ID
        clonedContent.find('[id]').each(function() {
            const originalId = $(this).attr('id');
            if (originalId) {
                $(this).attr('id', originalId + '-clone');
                $(this).attr('data-original-id', originalId);
            }
        });
        
        // Добавляем клонированное содержимое в панель
        sidebarPanelContent.append(clonedContent);
        
        // Восстанавливаем обработчики событий для динамически созданных элементов
        // Это важно для элементов, которые были созданы после загрузки страницы
        restoreEventHandlers();
        
        // Синхронизируем таймер
        syncTimer();
    }
    
    /**
     * Синхронизирует таймер между оригинальной и клонированной панелью
     */
    function syncTimer() {
        const originalCountdown = $('#countdown');
        const clonedCountdown = $('#countdown-clone');
        
        if (originalCountdown.length && clonedCountdown.length) {
            // Используем интервал для синхронизации таймера каждую секунду
            if (window.timerSyncInterval) {
                clearInterval(window.timerSyncInterval);
            }
            
            window.timerSyncInterval = setInterval(function() {
                if (sidebarExpanded && clonedCountdown.length) {
                    clonedCountdown.text(originalCountdown.text());
                }
            }, 1000);
            
            // Синхронизируем сразу
            clonedCountdown.text(originalCountdown.text());
        }
    }
    
    /**
     * Восстанавливает обработчики событий для элементов в выдвижной панели
     * Использует делегирование событий для обеспечения работоспособности
     */
    function restoreEventHandlers() {
        const sidebarPanel = $('#sidebarPanel');
        
        // Восстанавливаем обработчики для кнопок проверки заданий
        sidebarPanel.off('click', '#check-tasks-btn-clone').on('click', '#check-tasks-btn-clone', function() {
            const originalBtn = $('.column.is-one-quarter #check-tasks-btn');
            if (originalBtn.length) {
                originalBtn.trigger('click');
            }
        });
        
        // Восстанавливаем обработчики для полей ввода ответов на задания
        sidebarPanel.off('input change', '.task-answer-input').on('input change', '.task-answer-input', function() {
            const taskId = $(this).data('task-id');
            const originalInput = $(`.column.is-one-quarter .task-answer-input[data-task-id="${taskId}"]`);
            if (originalInput.length) {
                originalInput.val($(this).val());
                originalInput.trigger('input');
            }
        });
        
        // Восстанавливаем обработчики для форм
        sidebarPanel.off('submit', 'form').on('submit', 'form', function(e) {
            e.preventDefault();
            const form = $(this);
            const originalForm = $('.column.is-one-quarter form');
            if (originalForm.length) {
                // Копируем значения из клонированной формы в оригинальную
                form.find('input, select, textarea').each(function() {
                    const name = $(this).attr('name');
                    const value = $(this).val();
                    const originalField = originalForm.find(`[name="${name}"]`);
                    if (originalField.length) {
                        originalField.val(value);
                    }
                });
                // Отправляем оригинальную форму
                originalForm.submit();
            }
        });
        
        // Синхронизируем обновления UI заданий
        syncTasksUI();
    }
    
    /**
     * Синхронизирует обновления UI заданий между оригинальной и клонированной панелью
     */
    function syncTasksUI() {
        // Используем MutationObserver для отслеживания изменений в оригинальной панели
        const originalTasksContainer = $('.column.is-one-quarter #tasks-container');
        const clonedTasksContainer = $('#sidebarPanel #tasks-container-clone');
        
        if (originalTasksContainer.length && clonedTasksContainer.length) {
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'childList' || mutation.type === 'attributes') {
                        // Клонируем обновленное содержимое
                        const updatedContent = originalTasksContainer.clone(true, true);
                        updatedContent.find('[id]').each(function() {
                            const originalId = $(this).attr('id');
                            if (originalId) {
                                $(this).attr('id', originalId + '-clone');
                            }
                        });
                        clonedTasksContainer.html(updatedContent.html());
                    }
                });
            });
            
            observer.observe(originalTasksContainer[0], {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class']
            });
            
            // Сохраняем наблюдатель
            if (!window.tasksObserver) {
                window.tasksObserver = observer;
            }
        }
    }
    
    /**
     * Показывает выдвижную панель
     */
    function expandSidebar() {
        if (sidebarExpanded) return;
        
        const sidebarPanel = $('#sidebarPanel');
        sidebarPanel.addClass('active');
        sidebarExpanded = true;
        
        // Скрываем кнопку разворачивания
        $('#sidebarExpandBtn').fadeOut(200);
        
        // Обновляем содержимое при каждом открытии (на случай изменений)
        cloneSidebarContent();
    }
    
    /**
     * Скрывает выдвижную панель
     */
    function collapseSidebar() {
        if (!sidebarExpanded) return;
        
        const sidebarPanel = $('#sidebarPanel');
        sidebarPanel.removeClass('active');
        sidebarExpanded = false;
        
        // Показываем кнопку разворачивания обратно
        if (isFullscreen) {
            $('#sidebarExpandBtn').fadeIn(200);
        }
    }
    
    function expandIframe() {
        if (isFullscreen) return;
        
        const iframe = $('#pnetFrame');
        const iframeContainer = $('.iframe-container');
        
        // Сохраняем оригинальные стили
        originalIframeStyles = {
            position: iframe.css('position'),
            top: iframe.css('top'),
            left: iframe.css('left'),
            zIndex: iframe.css('z-index'),
            height: iframe.css('height'),
            width: iframe.css('width'),
            marginBottom: iframe.css('margin-bottom'),
            borderRadius: iframe.css('border-radius'),
            boxShadow: iframe.css('box-shadow'),
            border: iframe.css('border')
        };
        
        // Переводим iframe в полноэкранный режим
        iframe.css({
            'position': 'fixed',
            'top': '0',
            'left': '0',
            'z-index': '9999',
            'height': '100vh',
            'width': '100vw',
            'margin-bottom': '0',
            'border-radius': '0',
            'box-shadow': 'none',
            'border': 'none',
            'outline': 'none'  // Убираем outline для лучшего фокуса
        });
        
        $('#iframeOverlay').fadeIn(300);
        $('#collapseIframeBtn').fadeIn(300);
        $('#expandIframeBtn').fadeOut(200);
        
        // Показываем кнопку разворачивания панели
        $('#sidebarExpandBtn').fadeIn(300);
        
        $('body, html').addClass('iframe-fullscreen-active');
        
        // Принудительно устанавливаем фокус на iframe в полноэкранном режиме
        setTimeout(() => {
            iframe[0].focus();
            // Также пытаемся установить фокус через contentWindow
            try {
                if (iframe[0].contentWindow) {
                    iframe[0].contentWindow.focus();
                }
            } catch (e) {
                // Игнорируем ошибки CORS
            }
        }, 100);
        
        isFullscreen = true;
    }
    
    function collapseIframe() {
        if (!isFullscreen) return;
        
        const iframe = $('#pnetFrame');
        
        // Скрываем выдвижную панель, если она открыта
        collapseSidebar();
        
        // Очищаем интервалы и наблюдатели
        if (window.timerSyncInterval) {
            clearInterval(window.timerSyncInterval);
            window.timerSyncInterval = null;
        }
        if (window.tasksObserver) {
            window.tasksObserver.disconnect();
            window.tasksObserver = null;
        }
        
        // Восстанавливаем оригинальные стили
        if (originalIframeStyles) {
            iframe.css({
                'position': originalIframeStyles.position,
                'top': originalIframeStyles.top,
                'left': originalIframeStyles.left,
                'z-index': originalIframeStyles.zIndex,
                'height': originalIframeStyles.height,
                'width': originalIframeStyles.width,
                'margin-bottom': originalIframeStyles.marginBottom,
                'border-radius': originalIframeStyles.borderRadius,
                'box-shadow': originalIframeStyles.boxShadow,
                'border': originalIframeStyles.border
            });
        }
        
        $('#iframeOverlay').fadeOut(300);
        $('#collapseIframeBtn').fadeOut(300);
        $('#expandIframeBtn').fadeIn(200);
        
        // Скрываем кнопку разворачивания панели
        $('#sidebarExpandBtn').fadeOut(300);
        
        $('body, html').removeClass('iframe-fullscreen-active');
        
        // Восстанавливаем фокус на iframe после выхода из полноэкранного режима
        setTimeout(() => {
            iframe[0].focus();
            try {
                if (iframe[0].contentWindow) {
                    iframe[0].contentWindow.focus();
                }
            } catch (e) {
                // Игнорируем ошибки CORS
            }
        }, 100);
        
        isFullscreen = false;
    }
    
    // Обработчики событий для iframe
    $('#expandIframeBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        expandIframe();
    });
    
    $('#collapseIframeBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        collapseIframe();
    });
    
    $('#iframeOverlay').on('click', function() {
        collapseIframe();
    });
    
    // Обработчики событий для выдвижной панели
    $('#sidebarExpandBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        expandSidebar();
    });
    
    $('#sidebarCollapseBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        collapseSidebar();
    });
    
    // Предотвращаем закрытие панели при клике внутри неё
    $('#sidebarPanel').on('click', function(e) {
        e.stopPropagation();
    });
    
    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && isFullscreen) {
            collapseIframe();
        }
    });
    
    // Обработчик для восстановления фокуса в полноэкранном режиме
    $(document).on('click', function(e) {
        if (isFullscreen && !$(e.target).closest('#pnetFrame, #collapseIframeBtn, #iframeOverlay, #sidebarPanel, #sidebarExpandBtn').length) {
            // Если клик не по iframe, кнопкам или панели, восстанавливаем фокус на iframe
            setTimeout(() => {
                const iframe = $('#pnetFrame')[0];
                if (iframe) {
                    iframe.focus();
                    try {
                        if (iframe.contentWindow) {
                            iframe.contentWindow.focus();
                        }
                    } catch (err) {
                        // Игнорируем ошибки CORS
                    }
                }
            }, 10);
        }
    });
    
    $('#pnetFrame').on('click', function(e) {
        e.stopPropagation();
        
        // Принудительно восстанавливаем фокус на iframe при клике
        const iframe = this;
        setTimeout(() => {
            iframe.focus();
            try {
                if (iframe.contentWindow) {
                    iframe.contentWindow.focus();
                }
            } catch (err) {
                // Игнорируем ошибки CORS
            }
        }, 10);
    });
    
    // Восстанавливаем фокус при наведении мыши на iframe
    $('#pnetFrame').on('mouseenter', function(e) {
        const iframe = this;
        setTimeout(() => {
            iframe.focus();
            try {
                if (iframe.contentWindow) {
                    iframe.contentWindow.focus();
                }
            } catch (err) {
                // Игнорируем ошибки CORS
            }
        }, 50);
    });
    
    // Дополнительная защита - восстанавливаем фокус при любом взаимодействии с iframe
    $('#pnetFrame').on('mousedown mouseup keydown keyup touchstart touchend', function(e) {
        const iframe = this;
        setTimeout(() => {
            iframe.focus();
            try {
                if (iframe.contentWindow) {
                    iframe.contentWindow.focus();
                }
            } catch (err) {
                // Игнорируем ошибки CORS
            }
        }, 5);
    });
    
    // Предотвращаем скролл при фокусе на iframe
    $('#pnetFrame').on('focus', function(e) {
        e.preventDefault();
        // Сохраняем текущую позицию скролла
        const currentScrollTop = $(window).scrollTop();
        // Восстанавливаем позицию скролла после небольшой задержки
        setTimeout(() => {
            $(window).scrollTop(currentScrollTop);
        }, 10);
    });
    
    // Предотвращаем скролл при загрузке iframe
    $('#pnetFrame').on('load', function(e) {
        const currentScrollTop = $(window).scrollTop();
        setTimeout(() => {
            $(window).scrollTop(currentScrollTop);
        }, 100);
    });
    
    // Обновленный обработчик сообщений от iframe
    window.addEventListener('message', e => {
        if (e.data && e.data.type === 'pnet-bad-path') {
            const currentIframe = $('.iframe-container #pnetFrame')[0] || document.getElementById('pnetFrame');
            if (currentIframe && currentIframe.contentWindow) {
                currentIframe.contentWindow.location.replace('/pnetlab/');
            }
        }
    });
}


// Инициализация при загрузке DOM
$(document).ready(function() {
    initializeIframeControls();
});
