
(async () => {
    // Всегда просим HTML-консоль
    localStorage.setItem('html_console_mode', '1');

    try {
        // 1) Получаем CSRF токен Django для нашего API
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                         document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                         getCookie('csrftoken');

        // 2) Аутентифицируемся через наш API
        const authResponse = await fetch('/api/get_pnet_auth/', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!authResponse.ok) {
            const errorData = await authResponse.json().catch(() => ({}));
            console.error('PNET authentication failed:', errorData.error || 'Unknown error');
            return;
        }

        const authData = await authResponse.json();
        
        // 3) Устанавливаем полученные cookies
        if (authData.success && authData.cookies) {
            Object.entries(authData.cookies).forEach(([name, value]) => {
                document.cookie = `${name}=${value}; path=/; SameSite=Lax`;
            });
            
            if (authData.xsrf_token) {
                document.cookie = `XSRF-TOKEN=${authData.xsrf_token}; path=/; SameSite=Lax`;
            }
        }

        // 4) Перезагружаем iframe с аутентифицированной сессией
        const iframe = document.getElementById('pnetFrame');
        iframe.src = '/pnetlab/?t=' + Date.now();
        
    } catch (error) {
        console.error('Error during PNET authentication:', error);
    }
})();

// Вспомогательная функция для получения cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Функция для установки обработчика контроля location
function setupIframeLocationControl(iframeElement) {
    iframeElement.addEventListener('load', () => {
        const win = iframeElement.contentWindow;
        const doc = iframeElement.contentDocument;
        
        if (doc && doc.head) {
            // Вставляем в контекст iframe скрипт-заглушку
            const script = doc.createElement('script');
            script.textContent = `
                (function() {
                    const allowed = ['/store/', '/legacy/'];
                    function check() {
                        const path = location.pathname;
                        if (!allowed.some(p => path.startsWith(p))) {
                            parent.postMessage({ type: 'pnet-bad-path' }, '*');
                        }
                    }
                    
                    // Патчим history
                    ['pushState','replaceState'].forEach(fn => {
                        const orig = history[fn];
                        history[fn] = function() {
                            orig.apply(this, arguments);
                            check();
                        };
                    });
                    
                    // Отлавливаем back/forward
                    window.addEventListener('popstate', check);
                    
                    // И проверяем сразу после загрузки
                    check();
                })();
            `;
            doc.head.appendChild(script);
        }
    });
}

// Управление полноэкранным режимом iframe
$(document).ready(function() {
    let isFullscreen = false;
    let originalIframeStyles = null;
    let originalIframePosition = null;
    
    // Устанавливаем контроль location для исходного iframe
    const originalIframe = document.getElementById('pnetFrame');
    if (originalIframe) {
        setupIframeLocationControl(originalIframe);
    }
    
    function expandIframe() {
        if (isFullscreen) return;
        
        const iframe = $('#pnetFrame');
        const iframeContainer = $('.iframe-container');
        const contentContainer = $('.columns.is-centered').last();
        const titleContainer = $('.columns.is-centered').first();
        
        originalIframeStyles = {
            height: iframe.css('height'),
            width: iframe.css('width'),
            marginBottom: iframe.css('margin-bottom'),
            borderRadius: iframe.css('border-radius'),
            boxShadow: iframe.css('box-shadow'),
            border: iframe.css('border')
        };
        
        // Сохраняем оригинальную позицию для возврата
        originalIframePosition = {
            parent: iframeContainer.parent(),
            nextSibling: iframeContainer.next()
        };
        
        // Безопасно перемещаем контейнер без перезагрузки iframe
        const clonedContainer = iframeContainer.clone(true);
        iframeContainer.replaceWith(clonedContainer);
        clonedContainer.appendTo('body');
        clonedContainer.addClass('iframe-moved-up');
        
        // Обновляем ссылки на элементы после клонирования
        const newIframe = clonedContainer.find('#pnetFrame');
        const newExpandBtn = clonedContainer.find('#expandIframeBtn');
        
        // Переустанавливаем обработчик load для контроля location
        setupIframeLocationControl(newIframe[0]);
        
        newIframe.addClass('iframe-fullscreen');
        newIframe.css({
            'height': '100vh',
            'width': '100vw',
            'margin-bottom': '0',
            'border-radius': '0',
            'box-shadow': 'none',
            'border': 'none'
        });
        
        $('#iframeOverlay').fadeIn(300);
        $('#collapseIframeBtn').fadeIn(300);
        newExpandBtn.fadeOut(200);
        
        contentContainer.addClass('content-collapsed');
        titleContainer.addClass('content-collapsed');
        
        $('body, html').addClass('iframe-fullscreen-active');
        
        $('html, body').animate({
            scrollTop: iframe.offset().top
        }, 500);
        
        isFullscreen = true;
    }
    
    function collapseIframe() {
        if (!isFullscreen) return;
        
        const iframeContainer = $('.iframe-container.iframe-moved-up');
        const iframe = iframeContainer.find('#pnetFrame');
        const contentContainer = $('.columns.is-centered').last();
        const titleContainer = $('.columns.is-centered').first();
        
        iframe.removeClass('iframe-fullscreen');
        
        if (originalIframeStyles) {
            iframe.css({
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
        
        iframeContainer.removeClass('iframe-moved-up');
        
        // Безопасно возвращаем контейнер на оригинальное место
        if (originalIframePosition) {
            iframeContainer.prependTo(originalIframePosition.parent);
        } else {
            iframeContainer.prependTo(contentContainer.find('.column.is-three-quarters'));
        }
        
        // Обновляем ссылку на кнопку разворачивания
        const newExpandBtn = iframeContainer.find('#expandIframeBtn');
        newExpandBtn.fadeIn(200);
        
        // Переустанавливаем обработчик load для контроля location после возврата
        const returnedIframe = iframeContainer.find('#pnetFrame')[0];
        setupIframeLocationControl(returnedIframe);
        
        contentContainer.removeClass('content-collapsed');
        titleContainer.removeClass('content-collapsed');
        
        $('body, html').removeClass('iframe-fullscreen-active');
        
        $('html, body').animate({
            scrollTop: 0
        }, 500);
        
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
    
    $('#pnetFrame').on('click', function(e) {
        e.stopPropagation();
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
});