// Контроллер для CMD режима

// Ограничение частоты обновлений консоли (1 минута)
let lastRefreshTime = 0;
const REFRESH_COOLDOWN = 60 * 1000; // 1 минута в миллисекундах

// CMD контроллер - использует общие утилиты

// Функция создания сессии консоли для CMD режима
async function createCMDConsoleSession(slug) {
    const result = await makeAPIRequest('/api/create_pnet_lab_session_with_console/', {
        body: JSON.stringify({ slug: slug })
    });
    
    return result.success ? result.data : null;
}

// Функция инициализации iframe для CMD режима
function initializeCMDIframe() {
    log('Initializing CMD iframe...');
    
    const iframe = document.getElementById('pnetFrame');
    if (!iframe) {
        console.error('PNET iframe not found!');
        return;
    }

    const competitionSlug = getCompetitionSlugFromURL();
    if (!competitionSlug) {
        console.error('Could not extract competition slug from URL:', window.location.pathname);
        return;
    }

    log('Competition slug:', competitionSlug);
    log('Creating new CMD console session...');
    
    createCMDConsoleSession(competitionSlug)
        .then(sessionData => {
            if (sessionData && sessionData.guacamole_url) {
                iframe.src = sessionData.guacamole_url;
                log('CMD console session created successfully');
            } else {
                console.error('Failed to create CMD console session - no guacamole_url in response');
            }
        })
        .catch(error => {
            console.error('Error creating CMD console session:', error);
        });
}

// Функция для принудительного обновления консоли с ограничением частоты
function refreshConsoleSession() {
    const now = Date.now();
    const timeSinceLastRefresh = now - lastRefreshTime;
    
    if (timeSinceLastRefresh < REFRESH_COOLDOWN) {
        const remainingSeconds = Math.ceil((REFRESH_COOLDOWN - timeSinceLastRefresh) / 1000);
        log(`Обновление консоли доступно через ${remainingSeconds} секунд`);
        return;
    }
    
    const competitionSlug = getCompetitionSlugFromURL();
    if (competitionSlug) {
        log('Refreshing console session...');
        lastRefreshTime = now;
        initializeCMDIframe();
    }
}

// Инициализация при загрузке DOM
$(document).ready(function() {
    log('CMD controller loaded, initializing...');
    initializeCMDIframe();
});
