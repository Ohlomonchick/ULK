// Контроллер для управления iframe в PNET и CMD режимах


// Управление полноэкранным режимом iframe
function initializeIframeControls() {
    let isFullscreen = false;
    let originalIframeStyles = null;
    
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
    
    // Обработчики событий
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
    
    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && isFullscreen) {
            collapseIframe();
        }
    });
    
    // Обработчик для восстановления фокуса в полноэкранном режиме
    $(document).on('click', function(e) {
        if (isFullscreen && !$(e.target).closest('#pnetFrame, #collapseIframeBtn, #iframeOverlay').length) {
            // Если клик не по iframe или кнопкам, восстанавливаем фокус на iframe
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
