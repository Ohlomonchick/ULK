// Контроллер для CMD режима

// Ограничение частоты обновлений консоли (1 минута)
let lastRefreshTime = 0;
const REFRESH_COOLDOWN = 60 * 1000; // 1 минута в миллисекундах

// ID загрузчика для CMD режима
const CMD_LOADER_ID = 'cmdConsoleLoader';

// CMD контроллер - использует общие утилиты из console_loader.js

// Функция создания сессии консоли для CMD режима
async function createCMDConsoleSession(slug) {
    // Показываем загрузчик с начальным сообщением
    showConsoleLoader(CMD_LOADER_ID, 'Инициализация консоли...', 'Создание сессии лаборатории');
    
    try {
        // Обновляем текст во время создания сессии
        updateLoaderText(CMD_LOADER_ID, 'Создание сессии...', 'Подключение к PNET');
        
        const result = await makeAPIRequest('/api/create_pnet_lab_session_with_console/', {
            body: JSON.stringify({ slug: slug })
        });
        
        if (result.success && result.data) {
            // Обновляем текст во время включения ВМ
            const nodeCount = result.data.all_nodes_started || 0;
            updateLoaderText(CMD_LOADER_ID, 'Включение виртуальных машин...', `Запуск ${nodeCount} нод в топологии`);
            
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to create console session');
        }
    } catch (error) {
        // Обновляем текст при ошибке
        updateLoaderText(CMD_LOADER_ID, 'Ошибка инициализации', error.message || 'Не удалось создать сессию');
        // Скрываем загрузчик через 3 секунды после ошибки
        setTimeout(() => {
            hideConsoleLoader(CMD_LOADER_ID);
        }, 3000);
        throw error;
    }
}

// Функция инициализации iframe для CMD режима
function initializeCMDIframe() {
    log('Initializing CMD iframe...');
    
    const iframe = document.getElementById('pnetFrame');
    if (!iframe) {
        console.error('PNET iframe not found!');
        hideConsoleLoader(CMD_LOADER_ID);
        return;
    }

    const competitionSlug = getCompetitionSlugFromURL();
    if (!competitionSlug) {
        console.error('Could not extract competition slug from URL:', window.location.pathname);
        hideConsoleLoader(CMD_LOADER_ID);
        return;
    }

    log('Competition slug:', competitionSlug);
    log('Creating new CMD console session...');
    
    createCMDConsoleSession(competitionSlug)
        .then(sessionData => {
            if (sessionData && sessionData.guacamole_url) {
                // Обновляем текст перед загрузкой консоли
                updateLoaderText(CMD_LOADER_ID, 'Загрузка консоли...', 'Подключение к SSH терминалу');
                
                // Устанавливаем обработчики ДО установки src
                iframe.onload = function() {
                    log('CMD console session created successfully');
                    // Скрываем загрузчик после успешной загрузки
                    setTimeout(() => {
                        hideConsoleLoader(CMD_LOADER_ID);
                    }, 500);
                };
                
                iframe.onerror = function() {
                    console.error('Failed to load console iframe');
                    updateLoaderText(CMD_LOADER_ID, 'Ошибка загрузки', 'Не удалось загрузить консоль');
                    setTimeout(() => {
                        hideConsoleLoader(CMD_LOADER_ID);
                    }, 3000);
                };
                
                // Устанавливаем src после установки обработчиков
                iframe.src = sessionData.guacamole_url;
            } else {
                console.error('Failed to create CMD console session - no guacamole_url in response');
                updateLoaderText(CMD_LOADER_ID, 'Ошибка', 'Не получена ссылка на консоль');
                setTimeout(() => {
                    hideConsoleLoader(CMD_LOADER_ID);
                }, 3000);
            }
        })
        .catch(error => {
            console.error('Error creating CMD console session:', error);
            // Загрузчик уже обновлён в createCMDConsoleSession при ошибке
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
