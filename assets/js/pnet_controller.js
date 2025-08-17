
// Функция получения CSRF токена
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
           document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
           getCookie('csrftoken');
}

// Функция извлечения slug из URL
function getCompetitionSlugFromURL() {
    const path = window.location.pathname;
    // Проверяем разные возможные паттерны URL
    let matches = path.match(/\/competitions\/([^\/]+)\//);  // /competitions/{slug}/
    if (!matches) {
        matches = path.match(/\/team_competitions\/([^\/]+)\//);  // /team_competitions/{slug}/
    }
    if (!matches) {
        matches = path.match(/\/competition\/([^\/]+)\//);  // /competition/{slug}/ (если есть такой паттерн)
    }
    
    return matches ? matches[1] : null;
}

// Функция аутентификации в PNET
async function authenticatePNET() {
    localStorage.setItem('html_console_mode', '1');

    try {
        const csrfToken = getCSRFToken();

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
            return false;
        }

        const authData = await authResponse.json();
        
        if (authData.success) {
            return true;
        }
        
    } catch (error) {
        console.error('Error during PNET authentication:', error);
    }
    return false;
}

// Функция создания сессии лабы в PNET
async function createLabSession(slug) {
    try {
        const csrfToken = getCSRFToken();

        const sessionResponse = await fetch('/api/create_pnet_lab_session/', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ slug: slug })
        });

        if (!sessionResponse.ok) {
            const errorData = await sessionResponse.json().catch(() => ({}));
            console.error('Lab session creation failed:', errorData.error || 'Unknown error');
            return null;
        }

        const sessionData = await sessionResponse.json();
        
        if (sessionData.success) {
            return sessionData;
        }
        
    } catch (error) {
        console.error('Error during lab session creation:', error);
    }
    return null;
}

// Функция перенаправления iframe на топологию
function redirectToTopology(iframe) {
    if (iframe && iframe.contentWindow) {
        iframe.contentWindow.location.href = '/legacy/topology';
    }
}

// Инициализируем iframe после аутентификации
async function initializePNETFrame() {
    const iframe = document.getElementById('pnetFrame');
    if (!iframe) {
        return;
    }

    // Получаем slug соревнования из URL
    const competitionSlug = getCompetitionSlugFromURL();
    if (!competitionSlug) {
        console.error('Could not extract competition slug from URL:', window.location.pathname);
        return;
    }

    // Аутентифицируемся в PNET
    const authSuccess = await authenticatePNET();
    if (!authSuccess) {
        console.error('PNET authentication failed');
        return;
    }

    // Создаем сессию лабы
    const sessionData = await createLabSession(competitionSlug);
    if (!sessionData) {
        console.error('Lab session creation failed');
        return;
    }

    // Загружаем iframe с базовым URL PNET
    const targetSrc = iframe.getAttribute('data-src');
    if (targetSrc) {
        iframe.src = targetSrc + '?t=' + Date.now();
        
        // После загрузки iframe перенаправляем на топологию
        iframe.addEventListener('load', function() {
            // Небольшая задержка для полной загрузки
            setTimeout(() => {
                redirectToTopology(iframe);
            }, 1000);
        }, { once: true });
    }
}

// Запускаем после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePNETFrame);
} else {
    initializePNETFrame();
}

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
    
    // Устанавливаем контроль location для исходного iframe
    const originalIframe = document.getElementById('pnetFrame');
    if (originalIframe) {
        setupIframeLocationControl(originalIframe);
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
            'border': 'none'
        });
        
        $('#iframeOverlay').fadeIn(300);
        $('#collapseIframeBtn').fadeIn(300);
        $('#expandIframeBtn').fadeOut(200);
        
        $('body, html').addClass('iframe-fullscreen-active');
        
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