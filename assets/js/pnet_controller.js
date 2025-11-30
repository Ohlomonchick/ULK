
// PNET контроллер - использует общие утилиты

// ID загрузчика для PNET режима
const PNET_LOADER_ID = 'pnetConsoleLoader';

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

// Флаг для отслеживания, была ли выполнена первая загрузка и перенаправление
let pnetFrameInitialized = false;

// Инициализируем iframe после аутентификации
async function initializePNETFrame() {
    const iframe = document.getElementById('pnetFrame');
    if (!iframe) {
        log('PNET iframe not found');
        hideConsoleLoader(PNET_LOADER_ID);
        return;
    }

    const competitionSlug = getCompetitionSlugFromURL();
    if (!competitionSlug) {
        console.error('Could not extract competition slug from URL:', window.location.pathname);
        hideConsoleLoader(PNET_LOADER_ID);
        return;
    }

    log('Initializing PNET frame for slug:', competitionSlug);

    try {
        // Показываем загрузчик
        showConsoleLoader(PNET_LOADER_ID, 'Инициализация PNET...', 'Аутентификация в системе');
        
        // Аутентифицируемся в PNET
        updateLoaderText(PNET_LOADER_ID, 'Аутентификация...', 'Подключение к PNET');
        const authSuccess = await authenticatePNET();
        if (!authSuccess) {
            console.error('PNET authentication failed');
            updateLoaderText(PNET_LOADER_ID, 'Ошибка аутентификации', 'Не удалось войти в систему');
            setTimeout(() => {
                hideConsoleLoader(PNET_LOADER_ID);
            }, 3000);
            return;
        }

        // Создаем сессию лабы
        updateLoaderText(PNET_LOADER_ID, 'Создание сессии...', 'Инициализация лаборатории');
        const sessionData = await createLabSession(competitionSlug);
        if (!sessionData) {
            console.error('Lab session creation failed');
            updateLoaderText(PNET_LOADER_ID, 'Ошибка создания сессии', 'Не удалось создать сессию лаборатории');
            setTimeout(() => {
                hideConsoleLoader(PNET_LOADER_ID);
            }, 3000);
            return;
        }

        // Устанавливаем контроль location для PNET iframe
        setupIframeLocationControl(iframe);

        // Загружаем iframe с базовым URL PNET
        updateLoaderText(PNET_LOADER_ID, 'Загрузка интерфейса...', 'Подключение к топологии');
        const targetSrc = iframe.getAttribute('data-src');
        if (targetSrc) {
            // Устанавливаем обработчик только один раз при первой инициализации
            if (!pnetFrameInitialized) {
                const initialLoadHandler = function() {
                    // Удаляем обработчик сразу, чтобы он не срабатывал при последующих загрузках
                    iframe.onload = null;
                    pnetFrameInitialized = true;
                    
                    log('PNET iframe loaded, redirecting to topology');
                    setTimeout(() => {
                        redirectToTopology(iframe);
                        // Скрываем загрузчик после успешной загрузки
                        setTimeout(() => {
                            hideConsoleLoader(PNET_LOADER_ID);
                        }, 500);
                    }, 1000);
                };
                
                iframe.onload = initialLoadHandler;
                
                iframe.onerror = function() {
                    iframe.onerror = null; // Удаляем обработчик ошибок тоже
                    console.error('Failed to load PNET iframe');
                    updateLoaderText(PNET_LOADER_ID, 'Ошибка загрузки', 'Не удалось загрузить интерфейс');
                    setTimeout(() => {
                        hideConsoleLoader(PNET_LOADER_ID);
                    }, 3000);
                };
            }
            
            iframe.src = targetSrc + '?t=' + Date.now();
        } else {
            hideConsoleLoader(PNET_LOADER_ID);
        }
    } catch (error) {
        console.error('Error initializing PNET frame:', error);
        updateLoaderText(PNET_LOADER_ID, 'Ошибка инициализации', error.message || 'Не удалось инициализировать PNET');
        setTimeout(() => {
            hideConsoleLoader(PNET_LOADER_ID);
        }, 3000);
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