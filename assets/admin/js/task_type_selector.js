(function($) {
    $(document).ready(function() {
        
        function updateTaskTypeSelectors() {
            const taskTypes = [];
            
            $('.dynamic-task_types').each(function(index) {
                const $row = $(this);
                if ($row.hasClass('empty-form')) return;

                const $deleteCheckbox = $row.find('input[name$="-DELETE"]');
                if ($deleteCheckbox.is(':checked')) return;

                const $nameInput = $row.find('input[name$="-name"]');
                const $idInput = $row.find('input[name$="-id"]');
                
                const name = $nameInput.val();
                if (!name) return;

                const id = $idInput.val();
                const value = id ? id : 'name:' + name; 

                taskTypes.push({
                    value: value,
                    text: name
                });
            });

            $('select[name$="-task_type"]').each(function() {
                const $select = $(this);
                const currentValue = $select.val();

                $select.empty();
                $select.append('<option value="">---------</option>');

                taskTypes.forEach(function(type) {
                    const $option = $('<option></option>')
                        .attr('value', type.value)
                        .text(type.text);
                    
                    if (currentValue === type.value) {
                        $option.prop('selected', true);
                    }
                    
                    $select.append($option);
                });
            });
        }

        $(document).on('input', 'input[name^="task_types-"][name$="-name"]', updateTaskTypeSelectors);
        $(document).on('change', 'input[name$="-DELETE"]', updateTaskTypeSelectors);
        $(document).on('formset:added', function() { setTimeout(updateTaskTypeSelectors, 200); });
        $(document).on('formset:removed', function() { setTimeout(updateTaskTypeSelectors, 200); });

        setTimeout(updateTaskTypeSelectors, 500);
    });
})(django.jQuery);