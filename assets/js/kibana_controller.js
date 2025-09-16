// Функция получения CSRF токена
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
           document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
           getCookie('csrftoken');
}


// Функция проверки статуса аутентификации в Kibana
async function checkKibanaAuthStatus() {
    try {
        const csrfToken = getCSRFToken();

        const statusResponse = await fetch('/api/check_kibana_auth_status/', {
            method: 'GET',
            credentials: 'include',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!statusResponse.ok) {
            return false;
        }

        const statusData = await statusResponse.json();
        return statusData.authenticated;

    } catch (error) {
        console.warn('Failed to check Kibana auth status:', error);
        return false;
    }
}

// Функция аутентификации в Kibana
async function authenticateKibana() {
    try {
        const csrfToken = getCSRFToken();

        const authResponse = await fetch('/api/get_kibana_auth/', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!authResponse.ok) {
            return false;
        }

        const authData = await authResponse.json();
        return authData.success;

    } catch (error) {
        return false;
    }
}

// Инициализируем iframe после аутентификации
async function initializeKibanaFrame() {
    const iframe = document.getElementById('kibanaFrame');
    if (!iframe) {
        return;
    }

    // Проверяем, есть ли сохраненный статус аутентификации в sessionStorage
    const sessionKey = 'kibana_auth_status';
    const lastAuthTime = sessionStorage.getItem(sessionKey + '_time');
    const isAuthCached = sessionStorage.getItem(sessionKey) === 'true';

    // Если есть кэшированный статус и он не старше 5 минут, используем его
    const now = Date.now();
    const cachedMinutes = 10 * 60 * 1000;
    let authSuccess = false;

    if (isAuthCached && lastAuthTime && (now - parseInt(lastAuthTime)) < cachedMinutes) {
        console.log('Using cached Kibana auth status');
        authSuccess = true;
    } else {
        // Проверяем текущий статус аутентификации
        console.log('Checking Kibana auth status...');
        const isAuthenticated = await checkKibanaAuthStatus();

        if (isAuthenticated) {
            console.log('User already authenticated in Kibana');
            authSuccess = true;
            // Сохраняем статус в sessionStorage
            sessionStorage.setItem(sessionKey, 'true');
            sessionStorage.setItem(sessionKey + '_time', now.toString());
        } else {
            console.log('Authenticating in Kibana...');
            // Выполняем аутентификацию
            authSuccess = await authenticateKibana();
            if (authSuccess) {
                // Сохраняем успешный статус в sessionStorage
                sessionStorage.setItem(sessionKey, 'true');
                sessionStorage.setItem(sessionKey + '_time', now.toString());
            } else {
                // Сохраняем неуспешный статус
                sessionStorage.setItem(sessionKey, 'false');
                sessionStorage.setItem(sessionKey + '_time', now.toString());
            }
        }
    }

    if (!authSuccess) {
        console.error('Failed to authenticate in Kibana');
        return;
    }

    // Загружаем iframe с Kibana
    const targetSrc = iframe.getAttribute('data-src') || '/kibana/';
    iframe.src = targetSrc + '?t=' + Date.now();
}

// Функция для очистки кэша аутентификации (можно вызвать при необходимости)
function clearKibanaAuthCache() {
    const sessionKey = 'kibana_auth_status';
    sessionStorage.removeItem(sessionKey);
    sessionStorage.removeItem(sessionKey + '_time');
    console.log('Kibana auth cache cleared');
}

// Запускаем после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeKibanaFrame);
} else {
    initializeKibanaFrame();
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

// Настройка контроля навигации iframe для Kibana
function setupKibanaIframeLocationControl(iframeElement) {
    iframeElement.addEventListener('load', () => {
        const win = iframeElement.contentWindow;
        const doc = iframeElement.contentDocument;

        if (doc && doc.head) {
            // Insert script to control iframe navigation within Kibana context
            const script = doc.createElement('script');
            script.textContent = `
                (function() {
                    const allowedPaths = ['/kibana/', '/app/', '/api/', '/internal/'];

                    function checkPath() {
                        const path = location.pathname;
                        // Allow Kibana-related paths
                        const isAllowed = allowedPaths.some(p => path.startsWith(p)) || path === '/';

                        if (!isAllowed) {
                            // Redirect back to Kibana dashboard if navigated to unauthorized path
                            parent.postMessage({ type: 'kibana-bad-path', path: path }, '*');
                        }
                    }

                    // Patch browser history methods
                    ['pushState', 'replaceState'].forEach(fn => {
                        const orig = history[fn];
                        history[fn] = function() {
                            orig.apply(this, arguments);
                            checkPath();
                        };
                    });

                    // Listen for back/forward navigation
                    window.addEventListener('popstate', checkPath);

                    // Check immediately after load
                    checkPath();
                })();
            `;
            // Добавляем nonce для CSP
            script.setAttribute('nonce', '');
            doc.head.appendChild(script);
        }
    });
}

// Управление полноэкранным режимом iframe для Kibana
$(document).ready(function() {
    let isFullscreen = false;
    let originalIframeStyles = null;
    let originalIframePosition = null;

    // Отключаем контроль навигации для Kibana из-за CSP ограничений
    // const originalIframe = document.getElementById('kibanaFrame');
    // if (originalIframe) {
    //     setupKibanaIframeLocationControl(originalIframe);
    // }

    function expandKibanaIframe() {
        if (isFullscreen) return;

        const iframe = $('#kibanaFrame');
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

        // Save original position for restoration
        originalIframePosition = {
            parent: iframeContainer.parent(),
            nextSibling: iframeContainer.next()
        };

        // Safely move container without reloading iframe
        const clonedContainer = iframeContainer.clone(true);
        iframeContainer.replaceWith(clonedContainer);
        clonedContainer.appendTo('body');
        clonedContainer.addClass('iframe-moved-up');

        // Update element references after cloning
        const newIframe = clonedContainer.find('#kibanaFrame');
        const newExpandBtn = clonedContainer.find('#expandIframeBtn');

        // Re-setup location control for the cloned iframe (отключено из-за CSP)
        // setupKibanaIframeLocationControl(newIframe[0]);

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

    function collapseKibanaIframe() {
        if (!isFullscreen) return;

        const iframeContainer = $('.iframe-container.iframe-moved-up');
        const iframe = iframeContainer.find('#kibanaFrame');
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

        // Safely return container to original position
        if (originalIframePosition) {
            iframeContainer.prependTo(originalIframePosition.parent);
        } else {
            iframeContainer.prependTo(contentContainer.find('.column.is-three-quarters'));
        }

        // Update expand button reference
        const newExpandBtn = iframeContainer.find('#expandIframeBtn');
        newExpandBtn.fadeIn(200);

        // Re-setup location control after return (отключено из-за CSP)
        // const returnedIframe = iframeContainer.find('#kibanaFrame')[0];
        // setupKibanaIframeLocationControl(returnedIframe);

        contentContainer.removeClass('content-collapsed');
        titleContainer.removeClass('content-collapsed');

        $('body, html').removeClass('iframe-fullscreen-active');

        $('html, body').animate({
            scrollTop: 0
        }, 500);

        isFullscreen = false;
    }

    // Event handlers for fullscreen functionality
    $('#expandIframeBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        expandKibanaIframe();
    });

    $('#collapseIframeBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        collapseKibanaIframe();
    });

    $('#iframeOverlay').on('click', function() {
        collapseKibanaIframe();
    });

    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && isFullscreen) {
            collapseKibanaIframe();
        }
    });

    $('#kibanaFrame').on('click', function(e) {
        e.stopPropagation();
    });

    // Message handler for iframe navigation control (отключено из-за CSP)
    // window.addEventListener('message', e => {
    //     if (e.data && e.data.type === 'kibana-bad-path') {
    //         const currentIframe = $('.iframe-container #kibanaFrame')[0] || document.getElementById('kibanaFrame');
    //         if (currentIframe && currentIframe.contentWindow) {
    //             currentIframe.contentWindow.location.replace('/kibana/');
    //         }
    //     }
    // });
});
