$(document).ready(function() {
    const labField = $("#id_lab"); // Original select element
    const labSelect2 = labField.siblings(".select2");
    const levelsField = $("#id_level");
    const tasksField = $("#id_tasks");

    const platoonsField = $("#id_platoons");
    const platoonsSelect2selection = platoonsField.siblings(".select2").find(".select2-selection__rendered");

    if (labSelect2.length) {
        const select2Selection = labSelect2.find(".select2-selection__rendered");
        const labSlug = select2Selection[0].getAttribute("title");
        if (labSlug === "---------") {
            levelsField.empty();
            tasksField.empty();
        }

        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === "attributes" && mutation.attributeName === "title") {
                    const labSlug = mutation.target.getAttribute("title");
                    loadLevels(labSlug); // Call loadLevels with the new labSlug
                    loadTasks(labSlug);
                }
            });
        });

        // Configure the observer to watch for attribute changes
        observer.observe(select2Selection[0], {
            attributes: true // Watch for attribute changes
        });
    }

    const observer = new MutationObserver((mutationsList, observer) => {
    // Get all selected platoon elements
    const choices = platoonsSelect2selection.find(".select2-selection__choice");

    // Extract their 'title' attributes which contain the platoon numbers
    const platoonNumbers = choices.map(function () {
    return $(this).attr("title");
    }).get();

    console.log("Platoon numbers:", platoonNumbers);
});

// Start observing the target node for DOM changes
observer.observe(platoonsSelect2selection[0], { childList: true, subtree: true });


    levelsField.siblings(".select2").css('width', '25vw');
    tasksField.siblings(".select2").css('width', '25vw');
});

// Define the loadLevels function to fetch and populate levels
function loadLevels(labSlug) {
    $.ajax({
        url: `/api/get_lab_levels/${encodeURIComponent(labSlug)}/`, // Dynamically insert labSlug into the URL
        type: 'GET',
        headers: {
            'Accept': 'application/json'  // Tell the server we expect JSON
        },
        success: function(response) {
            const levelsField = $("#id_level"); // Update with the correct ID of your levels field
            if (levelsField.length) {
                levelsField.empty(); // Clear existing options

                // Populate new options from response data
                levelsField.append($("<option value=\"\" selected=\"\">---------</option>"))
                $.each(response, function(index, level) {
                    levelsField.append(
                        $("<option></option>").val(level.id).text(`Вариант ${level.level_number} - ${level.description}`)
                    );
                });

                // Trigger change event for select2 to refresh
                levelsField.trigger('change.select2');
            }

            const userLevelFields = $("select[name^='competition_users-'][name$='-level']");

            userLevelFields.each(function() {
                const $select = $(this);
                $select.empty(); // Clear existing options
                $select.append($("<option value=\"\">---------</option>"));

                // Populate new options from the same response
                $.each(response, function(index, level) {
                    $select.append($("<option></option>").val(level.id).text(`Вариант ${level.level_number} - ${level.description}`));
                });

                // If using select2 for these fields, refresh them
                $select.trigger('change.select2');
            });

        },
        error: function(xhr, status, error) {
            console.error("Error loading levels:", error);
        }
    });
}

function loadTasks(labSlug) {
    $.ajax({
        url: `/api/lab_tasks/${encodeURIComponent(labSlug)}/`, // Dynamically insert labSlug into the URL
        type: 'GET',
        headers: {
            'Accept': 'application/json'  // Tell the server we expect JSON
        },
        success: function(response) {
            const tasksField = $("#id_tasks"); // Update with the correct ID of your levels field
            if (tasksField.length) {
                tasksField.empty(); // Clear existing options

                // Populate new options from response data
                $.each(response, function(index, task) {
                    tasksField.append(
                        $("<option></option>").val(task.id).text(task.description)
                    );
                });

                // Trigger change event for select2 to refresh
                tasksField.trigger('change.select2');
            }
        },
        error: function(xhr, status, error) {
            console.error("Error loading levels:", error);
        }
    });
}