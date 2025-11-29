// Общий модуль для управления загрузчиком консоли (PNET и CMD режимы)

/**
 * Показывает загрузчик консоли с указанным текстом
 * @param {string} loaderId - ID элемента загрузчика (например, 'cmdConsoleLoader' или 'pnetConsoleLoader')
 * @param {string} mainText - Основной текст
 * @param {string} subText - Дополнительный текст
 */
function showConsoleLoader(loaderId, mainText, subText) {
    const loader = document.getElementById(loaderId);
    if (!loader) return;
    
    const mainTextEl = loader.querySelector('.cmd-console-loader-text, .pnet-console-loader-text');
    const subTextEl = loader.querySelector('.cmd-console-loader-subtext, .pnet-console-loader-subtext');
    
    if (mainTextEl && mainText) {
        mainTextEl.textContent = mainText;
    }
    if (subTextEl && subText) {
        subTextEl.textContent = subText;
    }
    
    loader.classList.add('active');
}

/**
 * Скрывает загрузчик консоли
 * @param {string} loaderId - ID элемента загрузчика
 */
function hideConsoleLoader(loaderId) {
    const loader = document.getElementById(loaderId);
    if (loader) {
        loader.classList.remove('active');
    }
}

/**
 * Обновляет текст загрузчика
 * @param {string} loaderId - ID элемента загрузчика
 * @param {string} mainText - Основной текст
 * @param {string} subText - Дополнительный текст
 */
function updateLoaderText(loaderId, mainText, subText) {
    const loader = document.getElementById(loaderId);
    if (!loader) return;
    
    const mainTextEl = loader.querySelector('.cmd-console-loader-text, .pnet-console-loader-text');
    const subTextEl = loader.querySelector('.cmd-console-loader-subtext, .pnet-console-loader-subtext');
    
    if (mainTextEl && mainText) {
        mainTextEl.textContent = mainText;
    }
    if (subTextEl && subText) {
        subTextEl.textContent = subText;
    }
}

