// Контроллер кнопок VM сегмента топологии

// ID загрузчиков
const LOADER_ID_CMD = 'cmdConsoleLoader';
const LOADER_ID_PNET = 'pnetConsoleLoader';

/**
 * Определяет актуальный ID загрузчика по наличию DOM-элемента.
 */
function _getActiveLoaderId() {
    if (document.getElementById(LOADER_ID_CMD)) return LOADER_ID_CMD;
    if (document.getElementById(LOADER_ID_PNET)) return LOADER_ID_PNET;
    return LOADER_ID_CMD;
}

/**
 * Переключает iframe на консоль выбранной VM в сегменте.
 */
async function switchSegmentVM(btn, vmName, slug) {
    const loaderId = _getActiveLoaderId();

    // Визуальная обратная связь: сразу помечаем кнопку активной
    document.querySelectorAll('.vm-segment-slider').forEach(b => {
        b.classList.remove('vm-segment-slider--active');
    });
    btn.classList.add('vm-segment-slider--active');

    showConsoleLoader(loaderId, 'Переключение VM...', vmName);

    try {
        const result = await makeAPIRequest('/api/create_pnet_lab_session_with_console/', {
            body: JSON.stringify({ slug: slug, node_name: vmName })
        });

        if (result.success && result.data && result.data.guacamole_url) {
            const iframe = document.getElementById('pnetFrame');
            if (!iframe) {
                console.error('pnetFrame не найден');
                hideConsoleLoader(loaderId);
                return;
            }

            updateLoaderText(loaderId, 'Загрузка консоли...', vmName);

            iframe.onload = function () {
                iframe.onload = null;
                setTimeout(() => hideConsoleLoader(loaderId), 500);
            };
            iframe.onerror = function () {
                iframe.onerror = null;
                updateLoaderText(loaderId, 'Ошибка загрузки', 'Не удалось загрузить консоль ' + vmName);
                setTimeout(() => hideConsoleLoader(loaderId), 3000);
            };

            iframe.src = result.data.guacamole_url;
        } else {
            const errMsg = (result.data && result.data.error) || result.error || 'Не удалось переключить VM';
            console.error('switchSegmentVM error:', errMsg);
            updateLoaderText(loaderId, 'Ошибка', errMsg);
            setTimeout(() => hideConsoleLoader(loaderId), 3000);
            // Сбрасываем подсветку при ошибке — возвращаем предыдущую активную
            btn.classList.remove('vm-segment-slider--active');
        }
    } catch (error) {
        console.error('switchSegmentVM exception:', error);
        updateLoaderText(loaderId, 'Ошибка', error.message || 'Неизвестная ошибка');
        setTimeout(() => hideConsoleLoader(loaderId), 3000);
        btn.classList.remove('vm-segment-slider--active');
    }
}

