// Контроллер для CMD режима

// Кэш для хранения ссылок на Guacamole консоль (с localStorage)
const consoleCache = {
    CACHE_DURATION: 5 * 60 * 1000, // 5 минут в миллисекундах
    STORAGE_KEY: 'cmd_console_cache',
    
    // Сохранить в кэш
    set(slug, data) {
        try {
            const cacheData = this.getAll();
            cacheData[slug] = {
                data: data,
                timestamp: Date.now()
            };
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(cacheData));
            console.log('Console session cached in localStorage');
        } catch (error) {
            console.error('Failed to save to localStorage:', error);
        }
    },
    
    // Получить из кэша
    get(slug) {
        try {
            const cacheData = this.getAll();
            const cached = cacheData[slug];
            if (!cached) return null;
            
            // Проверяем, не истек ли кэш
            if (Date.now() - cached.timestamp > this.CACHE_DURATION) {
                delete cacheData[slug];
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify(cacheData));
                return null;
            }
            
            return cached.data;
        } catch (error) {
            console.error('Failed to read from localStorage:', error);
            return null;
        }
    },
    
    // Получить все данные кэша
    getAll() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            return stored ? JSON.parse(stored) : {};
        } catch (error) {
            console.error('Failed to parse localStorage data:', error);
            return {};
        }
    },
    
    // Очистить кэш
    clear() {
        try {
            localStorage.removeItem(this.STORAGE_KEY);
            console.log('Console cache cleared from localStorage');
        } catch (error) {
            console.error('Failed to clear localStorage:', error);
        }
    }
};

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

    // Проверяем кэш
    const cachedData = consoleCache.get(competitionSlug);
    if (cachedData) {
        log('✅ Using cached console session');
        iframe.src = cachedData.guacamole_url;
        return;
    }

    log('Creating new CMD console session...');
    
    createCMDConsoleSession(competitionSlug)
        .then(sessionData => {
            if (sessionData && sessionData.guacamole_url) {
                consoleCache.set(competitionSlug, sessionData);
                log('Console session cached for 5 minutes');
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

// Функция для принудительного обновления консоли (очистка кэша и перезагрузка)
function refreshConsoleSession() {
    const competitionSlug = getCompetitionSlugFromURL();
    if (competitionSlug) {
        log('Refreshing console session...');
        consoleCache.clear();
        initializeCMDIframe();
    }
}


// Функция очистки устаревших записей из кэша
function cleanupExpiredCache() {
    try {
        const cacheData = consoleCache.getAll();
        let hasExpired = false;
        
        for (const slug in cacheData) {
            const cached = cacheData[slug];
            if (Date.now() - cached.timestamp > consoleCache.CACHE_DURATION) {
                delete cacheData[slug];
                hasExpired = true;
            }
        }
        
        if (hasExpired) {
            localStorage.setItem(consoleCache.STORAGE_KEY, JSON.stringify(cacheData));
            console.log('Cleaned up expired cache entries');
        }
    } catch (error) {
        console.error('Failed to cleanup expired cache:', error);
    }
}

// Инициализация при загрузке DOM
$(document).ready(function() {
    log('CMD controller loaded, initializing...');
    
    // Очищаем устаревшие записи из кэша
    cleanupExpiredCache();
    
    initializeCMDIframe();
});
