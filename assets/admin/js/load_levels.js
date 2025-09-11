$(document).ready(function() {
    initMainLabObserver();

    // Инициализация для существующих
    $("select[id^='id_kkz_labs-'][id$='-lab']").each(function() {
        initInlineLabObserver($(this));
    });

    function initLabHandlers() {
        $('select[id$="-lab"]').each(function() {
            const $labSelect = $(this);
            const tasksId = $labSelect.attr('id').replace('-lab', '-tasks');

            $labSelect.off('change.lab').on('change.lab', function(event, setNumTasks = true) {
                const labSlug = $(this).find('option:selected').text();
                if (labSlug && labSlug !== "---------") {
                    loadTasks(labSlug, '#' + tasksId, setNumTasks);
                }
            }).trigger('change.lab', [false]);
        });
    }

    initLabHandlers();
    // Обработчик для новых
    $(document).on('formset:added', function(event, $row) {
        setTimeout(() => {
            $(".dynamic-kkz_labs select[id$='-lab']").each(function() {
                initInlineLabObserver($(this));
            });
        }, 100);
    });

    function initMainLabObserver() {
        const $labField = $("#id_lab");
        const $labSelect2 = $labField.siblings(".select2");

        if ($labSelect2.length) {
            const $rendered = $labSelect2.find(".select2-selection__rendered");
            if ($rendered.length) {
                const observer = new MutationObserver(mutations => {
                    mutations.forEach(mutation => {
                        if (mutation.attributeName === "title") {
                            const labSlug = $rendered.attr("title");
                            handleLabChange(labSlug, "#id_level", "#id_tasks", true);
                        }
                    });
                });
                observer.observe($rendered[0], { attributes: true });
            }
            const initialLabSlug = $rendered.attr("title");
            handleLabChange(initialLabSlug, "#id_level", "#id_tasks", false);
        }
    }

    function initInlineLabObserver($labField) {
        const $labSelect2 = $labField.siblings(".select2");
        if (!$labSelect2.length) return;

        const $rendered = $labSelect2.find(".select2-selection__rendered");
        if (!$rendered.length) return;

        const prefix = $labField.attr("id").replace("-lab", "");
        const tasksSelector = `#${prefix}-tasks`;

        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.attributeName === "title") {
                    const labSlug = $rendered.attr("title");
                    handleLabChange(labSlug, null, tasksSelector, true);
                }
            });
        });
        observer.observe($rendered[0], { attributes: true });

        const initialLabSlug = $rendered.attr("title");
        if (initialLabSlug && initialLabSlug !== "---------") {
            handleLabChange(initialLabSlug, null, tasksSelector, false);
        }
    }

    // Общая обработка изменений
    function handleLabChange(labSlug, levelsSelector, tasksSelector, setNumTasks = true) {
        if (labSlug && labSlug !== "---------") {
            if (levelsSelector) loadLevels(labSlug, levelsSelector);
            if (tasksSelector) loadTasks(labSlug, tasksSelector, setNumTasks);
        }
    }

    $(document).on('formset:added', function(event, $row, formsetName) {
        if (formsetName === 'kkz_labs') {
            setTimeout(() => {
                $row.find('select[id$="-lab"]').each(function() {
                    const $labSelect = $(this);
                    const tasksId = $labSelect.attr('id').replace('-lab', '-tasks');
                });
            }, 100);
        }
    });


    function loadLevels(labSlug, levelsSelector) {
        $.ajax({
            url: `/api/get_lab_levels/${encodeURIComponent(labSlug)}/`,
            type: 'GET',
            success: function(response) {
                const $field = $(levelsSelector);
                $field.empty().append('<option value="">---------</option>');
                response.forEach(level => {
                    $field.append($('<option>', {
                        value: level.id,
                        text: `Вариант ${level.level_number} - ${level.description}`
                    }));
                });
                $field.trigger('change.select2');
            }
        });
    }

    function loadTasks(labSlug, tasksSelector, setNumTasks = true) {
        const $tasksField = $(tasksSelector);
        const selectedTasks = $tasksField.val() || [];

        $.ajax({
            url: `/api/lab_tasks/${encodeURIComponent(labSlug)}/`,
            type: 'GET',
            success: function(response) {
                $tasksField.html('');
                const uniqueTasks = new Map();
                response.forEach(task => {
                    if (!uniqueTasks.has(task.id)) {
                        uniqueTasks.set(task.id, task.description);
                    }
                });

                uniqueTasks.forEach((description, id) => {
                    const $option = $('<option></option>').val(id).text(description);
                    if (selectedTasks.includes(String(id))) {
                        $option.prop('selected', true);
                    }
                    $tasksField.append($option);
                });
                $tasksField.trigger('change.select2');

                if (setNumTasks) {
                    const numTasksSelector = tasksSelector.replace(/-tasks$/, '-num_tasks');
                    const $numTasks = $(numTasksSelector);
                    if ($numTasks.length) {
                        $numTasks.val(uniqueTasks.size);
                    }
                }
            },
            error: function(xhr) {
                console.error('Ошибка загрузки задач:', xhr.responseText);
            }
        });
    }
});