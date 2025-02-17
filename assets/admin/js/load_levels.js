$(document).ready(function() {
    const labField = $("#id_lab");
    const labSelect2 = labField.siblings(".select2");
    const levelsField = $("#id_level");
    const tasksField = $("#id_tasks");

    if (labSelect2.length) {
        const select2Selection = labSelect2.find(".select2-selection__rendered");
        if (select2Selection.length) {
            const labSlug = select2Selection[0].getAttribute("title");
            if (labSlug === "---------") {
                levelsField.empty();
                tasksField.empty();
            }
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === "attributes" && mutation.attributeName === "title") {
                        const labSlug = mutation.target.getAttribute("title");
                        loadLevels(labSlug, "#id_level");
                        loadTasks(labSlug, "#id_tasks");
                    }
                });
            });
            observer.observe(select2Selection[0], {
                attributes: true
            });
        }
    }

    levelsField.siblings(".select2").css('width', '25vw');
    tasksField.siblings(".select2").css('width', '25vw');


    $("select[id^='id_kkz_labs-'][id$='-lab']").each(function() {
        initLabSelect2Observer($(this));
    });
});


function initLabSelect2Observer($labField) {
    const $labSelect2 = $labField.siblings(".select2");
    if (!$labSelect2.length) {return;}

    const $rendered = $labSelect2.find(".select2-selection__rendered");
    if (!$rendered.length) {return;}

    // Смотрим текущее значение title
    const initialTitle = $rendered[0].getAttribute("title");
    if (initialTitle && initialTitle !== "---------") {
        loadTasks(initialTitle, "#" + $labField.attr("id").replace("-lab", "-tasks"));
    }

    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === "attributes" && mutation.attributeName === "title") {
                const newLabSlug = mutation.target.getAttribute("title");
                const tasksSelector = "#" + $labField.attr("id").replace("-lab", "-tasks");
                loadTasks(newLabSlug, tasksSelector);
            }
        });
    });
    observer.observe($rendered[0], {
        attributes: true
    });
}

function loadLevels(labSlug, levelsSelector) {
    $.ajax({
        url: `/api/get_lab_levels/${encodeURIComponent(labSlug)}/`,
        type: 'GET',
        headers: { 'Accept': 'application/json' },
        success: function(response) {
            const $levelsField = $(levelsSelector);
            if ($levelsField.length) {
                $levelsField.empty();
                $levelsField.append($("<option value=\"\" selected=\"\">---------</option>"));
                $.each(response, function(index, level) {
                    $levelsField.append(
                        $("<option></option>").val(level.id).text(`Вариант ${level.level_number} - ${level.description}`)
                    );
                });
                $levelsField.trigger('change.select2');
            }
        },
        error: function(xhr, status, error) {
            console.error("Error loading levels:", error);
        }
    });
}

function loadTasks(labSlug, tasksSelector) {
    $.ajax({
        url: `/api/lab_tasks/${encodeURIComponent(labSlug)}/`,
        type: 'GET',
        headers: { 'Accept': 'application/json' },
        success: function(response) {
            const $tasksField = $(tasksSelector);
            if ($tasksField.length) {
                $tasksField.empty();
                $.each(response, function(index, task) {
                    $tasksField.append(
                        $("<option></option>").val(task.id).text(task.description)
                    );
                });
                $tasksField.trigger('change.select2');
            }
        },
        error: function(xhr, status, error) {
            console.error("Error loading tasks:", error);
        }
    });
}