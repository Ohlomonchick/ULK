// Общие утилиты для PNET и CMD контроллеров

// Функция получения CSRF токена
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
           document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
           getCookie('csrftoken');
}

// Функция извлечения slug из URL
function getCompetitionSlugFromURL() {
    const path = window.location.pathname;
    console.log('Current path:', path);
    
    // Проверяем разные возможные паттерны URL
    let matches = path.match(/\/competitions\/([^\/]+)\//);  // /competitions/{slug}/
    if (!matches) {
        matches = path.match(/\/team_competitions\/([^\/]+)\//);  // /team_competitions/{slug}/
    }
    if (!matches) {
        matches = path.match(/\/competition\/([^\/]+)\//);  // /competition/{slug}/ (если есть такой паттерн)
    }
    
    console.log('URL matches:', matches);
    return matches ? matches[1] : null;
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

// Общая функция для API запросов
async function makeAPIRequest(url, options = {}) {
    const csrfToken = getCSRFToken();
    
    const defaultOptions = {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        }
    };
    
    const finalOptions = { ...defaultOptions, ...options };
    
    try {
        const response = await fetch(url, finalOptions);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('API request failed:', errorData.error || 'Unknown error');
            return { success: false, error: errorData.error || 'Unknown error' };
        }
        
        const data = await response.json();
        return { success: true, data };
    } catch (error) {
        console.error('Error during API request:', error);
        return { success: false, error: error.message };
    }
}

// Функция для логирования (можно отключить в продакшене)
function log(message, ...args) {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log(message, ...args);
    }
}
