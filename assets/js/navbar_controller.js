document.addEventListener('DOMContentLoaded', function() {  
    // Проверяем, что URL определены
    if (!window.navbarUrls) {
        console.warn('navbarUrls не определены. Проверьте, что скрипт с URL загружен перед navbar_controller.js');
        return;
    }
    
    // Определение текущей страницы и подсветка активного элемента
    function highlightCurrentPage() {
        const currentPath = window.location.pathname;
        const urlParams = new URLSearchParams(window.location.search);
        const utmSource = urlParams.get('utm_source');
        const navbarItems = document.querySelectorAll('.navbar-item');
        
        // Маппинг текста ссылки к путям и utm_source
        const pageMapping = {
            'экзамен': {
                paths: [window.navbarUrls['competition-list'] || ''],
                utm_sources: ['competitions']
            },
            'соревнован': {
                paths: [window.navbarUrls['team-competition-list'] || ''],
                utm_sources: ['team_competitions']
            },
            'истори': {
                paths: [window.navbarUrls['competition-history-list'] || ''],
                utm_sources: ['history']
            },
            'лабораторн': {
                paths: [window.navbarUrls['lab-menu'] || '', window.navbarUrls['lab-list'] || ''],
                utm_sources: ['labs', 'lab-menu']
            },
            'взвод': {
                paths: [window.navbarUrls['platoon-list'] || ''],
                utm_sources: ['platoons']
            },
            'войти': {
                paths: [window.navbarUrls['reg'] || '', window.navbarUrls['login'] || ''],
                utm_sources: ['reg', 'login']
            }
        };
        
        navbarItems.forEach(item => {
            const linkText = item.textContent.trim().toLowerCase();
            
            // Проверяем каждый тип страницы
            for (const [key, mapping] of Object.entries(pageMapping)) {
                if (linkText.includes(key)) {
                    let isActive = false;
                    
                    // Если есть utm_source - проверяем только его
                    if (utmSource) {
                        isActive = mapping.utm_sources.includes(utmSource);
                    } else {
                        // Fallback на проверку пути только если нет utm_source
                        isActive = mapping.paths.some(path => currentPath.includes(path));
                    }
                    
                    if (isActive) {
                        item.classList.add('active');
                        break;
                    }
                }
            }
        });
    }
    
    // Запуск функции подсветки
    highlightCurrentPage();
    
    // Дополнительная анимация при наведении
    $('.navbar-item').hover(
        function() {
            $(this).addClass('hover-effect');
        },
        function() {
            $(this).removeClass('hover-effect');
        }
    );
});