$(document).ready(function() {
    /** Отмена устаревших ответов / параллельных запросов для одного и того же селектора заданий */
    const loadTasksPending = {};

    function normalizeMultiSelectVal(raw) {
        if (raw == null || raw === '') {
            return [];
        }
        if (Array.isArray(raw)) {
            return raw.map(String);
        }
        return [String(raw)];
    }

    initMainLabObserver();

    // Инициализация для существующих
    $("select[id^='id_kkz_labs-'][id$='-lab']").each(function() {
        initInlineLabObserver($(this));
    });

    function initLabHandlers() {
        // #id_lab обрабатывается в initMainLabObserver (Select2 + MutationObserver); повторная
        // привязка давала второй AJAX на то же поле «Задания» и перезаписывала выбор (в т.ч. после «Выбрать всё»).
        $('select[id$="-lab"]').not('#id_lab').each(function() {
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
        if (!$labField.length) {
            return;
        }
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
        } else {
            $labField.off('change.labmain').on('change.labmain', function(event, setNumTasks) {
                if (setNumTasks === undefined) {
                    setNumTasks = true;
                }
                const labSlug = $(this).find('option:selected').text();
                if (labSlug && labSlug !== "---------") {
                    handleLabChange(labSlug, "#id_level", "#id_tasks", setNumTasks);
                }
            });
            const initialLabSlug = $labField.find('option:selected').text();
            if (initialLabSlug && initialLabSlug !== "---------") {
                handleLabChange(initialLabSlug, "#id_level", "#id_tasks", false);
            }
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
        // Извлекаем lab_type_display из labSlug (формат: "Name - LabTypeDisplay")
        const parts = labSlug.split(' - ');
        const labName = parts.slice(0, -1).join(' - '); // Всё до последнего " - "
        const labTypeDisplay = parts[parts.length - 1]; // Последний элемент
        
        $.ajax({
            url: `/api/get_lab_levels/${encodeURIComponent(labName)}/`,
            type: 'GET',
            data: {
                lab_type_display: labTypeDisplay
            },
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
        if (!$tasksField.length) {
            return;
        }

        // Извлекаем lab_type_display из labSlug (формат: "Name - LabTypeDisplay")
        const parts = labSlug.split(' - ');
        const labName = parts.slice(0, -1).join(' - '); // Всё до последнего " - "
        const labTypeDisplay = parts[parts.length - 1]; // Последний элемент

        if (loadTasksPending[tasksSelector]) {
            loadTasksPending[tasksSelector].abort();
        }

        const xhr = $.ajax({
            url: `/api/lab_tasks/${encodeURIComponent(labName)}/`,
            type: 'GET',
            data: {
                lab_type_display: labTypeDisplay
            },
            success: function(response) {
                if (loadTasksPending[tasksSelector] !== xhr) {
                    return;
                }
                delete loadTasksPending[tasksSelector];

                // Важно: читать выбор не в начале запроса, а здесь — иначе «Выбрать всё» и быстрый выбор
                // во время ответа сети теряются при перерисовке <option>.
                const selectedTasks = normalizeMultiSelectVal($tasksField.val());

                const uniqueTasks = new Map();
                response.forEach(task => {
                    if (!uniqueTasks.has(task.id)) {
                        uniqueTasks.set(task.id, task.description);
                    }
                });

                const allowedIds = new Set([...uniqueTasks.keys()].map(String));
                const toSelect = selectedTasks.filter(id => allowedIds.has(String(id)));

                $tasksField.empty();
                uniqueTasks.forEach((description, id) => {
                    $tasksField.append($('<option></option>').val(id).text(description));
                });

                // Select2 (Jet и др.) ожидает обновление через .val(); одних selected на option мало.
                $tasksField.val(toSelect).trigger('change');

                if (setNumTasks) {
                    const numTasksSelector = tasksSelector.replace(/-tasks$/, '-num_tasks');
                    const $numTasks = $(numTasksSelector);
                    if ($numTasks.length) {
                        $numTasks.val(uniqueTasks.size);
                    }
                }
            },
            error: function(xhrReq, status) {
                if (loadTasksPending[tasksSelector] !== xhrReq) {
                    return;
                }
                delete loadTasksPending[tasksSelector];
                if (status === 'abort') {
                    return;
                }
                console.error('Ошибка загрузки задач:', xhrReq.responseText);
            }
        });
        loadTasksPending[tasksSelector] = xhr;
    }
});