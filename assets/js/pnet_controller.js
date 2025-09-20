
// PNET контроллер - использует общие утилиты

// Функция аутентификации в PNET
async function authenticatePNET() {
    localStorage.setItem('html_console_mode', '1');
    
    const result = await makeAPIRequest('/api/get_pnet_auth/');
    return result.success && result.data.success;
}

// Функция создания сессии лабы в PNET
async function createLabSession(slug) {
    const result = await makeAPIRequest('/api/create_pnet_lab_session/', {
        body: JSON.stringify({ slug: slug })
    });
    
    return result.success ? result.data : null;
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
        log('PNET iframe not found');
        return;
    }

    const competitionSlug = getCompetitionSlugFromURL();
    if (!competitionSlug) {
        console.error('Could not extract competition slug from URL:', window.location.pathname);
        return;
    }

    log('Initializing PNET frame for slug:', competitionSlug);

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

    // Устанавливаем контроль location для PNET iframe
    setupIframeLocationControl(iframe);

    // Загружаем iframe с базовым URL PNET
    const targetSrc = iframe.getAttribute('data-src');
    if (targetSrc) {
        iframe.src = targetSrc + '?t=' + Date.now();
        
        // После загрузки iframe перенаправляем на топологию
        iframe.addEventListener('load', function() {
            setTimeout(() => {
                redirectToTopology(iframe);
            }, 1000);
        }, { once: true });
    }
}

// Функция инициализации будет вызвана в $(document).ready()

// Функция для установки обработчика контроля location (только для PNET)
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

// Инициализация PNET iframe после аутентификации
$(document).ready(function() {
    // Инициализируем iframe для PNET режима
    initializePNETFrame();
});