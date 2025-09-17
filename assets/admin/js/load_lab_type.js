(function($) {
    $(document).ready(function() {
        var programSelect = $('#id_program');
        var labTypeSelect = $('#id_lab_type');
        var allLabTypes = labTypeSelect.html();

        function updateLabTypeOptions() {
            var selectedProgram = programSelect.val();
            labTypeSelect.html(allLabTypes);
            var emptyOption = labTypeSelect.children('option[value=""]');

            if (selectedProgram === 'COMPETITION') {
                labTypeSelect.children('option').each(function() {
                    var val = $(this).val();
                    if (val !== '' && val !== 'COMPETITION') $(this).remove();
                });
            } else if (selectedProgram === 'INFOBOR') {
                labTypeSelect.children('option').each(function() {
                    var val = $(this).val();
                    if (val !== '' && val === 'COMPETITION') $(this).remove();
                });
            }

            if (labTypeSelect.children('option[value=""]').length === 0) {
                labTypeSelect.prepend(emptyOption);
                labTypeSelect.prepend(emptyOption);
            }

            if (!labTypeSelect.find('option[value="' + labTypeSelect.val() + '"]').length) {
                labTypeSelect.val('');
            }
        }

        programSelect.on('change', updateLabTypeOptions);

        updateLabTypeOptions();
    });
})(django.jQuery);
