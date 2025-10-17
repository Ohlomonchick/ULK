$(document).ready(function() {
    // Функция для подсчета выбранных элементов в Select2
    function getSelect2SelectedCount($field) {
        if ($field.data('select2')) {
            const data = $field.select2('data');
            return data ? data.length : 0;
        }
        return $field.find('option:selected').length;
    }
    
    // Функция для обновления поля num_tasks на основе выбранных tasks
    function updateNumTasks() {
        const $tasksField = $('select[name="tasks"]');
        const $numTasksField = $("#id_num_tasks");
        
        if ($tasksField.length && $numTasksField.length) {
            const selectedCount = getSelect2SelectedCount($tasksField);
            $numTasksField.val(selectedCount);
        }
    }
    
    // Функция инициализации обработчиков
    function initHandlers() {
        const $tasksField = $('select[name="tasks"]');
        
        if (!$tasksField.length) {
            return;
        }
        
        const $select2Container = $tasksField.siblings(".select2-container");
        
        // Удаляем старые обработчики, чтобы избежать дублирования
        $tasksField.off('change.numtasks select2:select.numtasks select2:unselect.numtasks select2:clear.numtasks');
        
        if ($select2Container.length || $tasksField.data('select2')) {
            // Обработчики событий Select2
            $tasksField.on('select2:select.numtasks select2:unselect.numtasks select2:clear.numtasks', function() {
                setTimeout(updateNumTasks, 100);
            });
            
            // Также отслеживаем стандартное событие change
            $tasksField.on('change.numtasks', function() {
                setTimeout(updateNumTasks, 100);
            });
            
            // Наблюдатель за изменениями в Select2 контейнере
            const observer = new MutationObserver(function(mutations) {
                const hasRelevantChanges = mutations.some(mutation => {
                    return mutation.type === 'childList' && 
                           (mutation.addedNodes.length > 0 || mutation.removedNodes.length > 0);
                });
                
                if (hasRelevantChanges) {
                    setTimeout(updateNumTasks, 100);
                }
            });
            
            // Наблюдаем за контейнером с выбранными элементами
            const $selectedContainer = $select2Container.find('.select2-selection__rendered');
            if ($selectedContainer.length) {
                observer.observe($selectedContainer[0], { 
                    childList: true, 
                    subtree: false
                });
            }
        } else {
            // Для стандартного select
            $tasksField.on('change.numtasks', function() {
                updateNumTasks();
            });
        }
        
        // Устанавливаем начальное значение
        updateNumTasks();
    }
    
    // Инициализация с задержкой, чтобы дать время Select2 загрузиться
    setTimeout(initHandlers, 500);
    
    // Дополнительная проверка через 2 секунды
    setTimeout(function() {
        initHandlers();
        updateNumTasks();
    }, 2000);
});

