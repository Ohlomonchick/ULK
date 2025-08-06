
(async () => {
    // Всегда просим HTML-консоль
    localStorage.setItem('html_console_mode', '1');

    // 1) Префлайт, чтобы получить XSRF-TOKEN + сессию
    await fetch('/store/public/auth/login/login', { method: 'GET', credentials: 'include' }).catch(()=>{});

    // 2) Достаём XSRF-TOKEN из cookie
    const xsrf = decodeURIComponent(
    (document.cookie.split('; ').find(r => r.startsWith('XSRF-TOKEN=')) || '').split('=')[1] || ''
    );

    // 3) Логинимся
    const res = await fetch('/store/public/auth/login/login', {
    method: 'POST',
    credentials: 'include',
    headers: {
        'Content-Type': 'application/json;charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'X-XSRF-TOKEN': xsrf
    },
    body: JSON.stringify({
        username: 'admin',
        password: 'pnet',
        html: '1',     // <<--- ключевая правка
        captcha: ''
    })
    });

    const data = await res.json().catch(() => ({}));
    const iframe = document.getElementById('pnetFrame');
    iframe.src = '/pnetlab/?t=' + Date.now(); // перезагрузим iframe уже авторизованным
})();

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