$(document).ready(function() {
    const loadTasksPending = {};
    const Core = window.TaskDependencyCore;

    function normalizeMultiSelectVal(raw) {
        if (raw == null || raw === '') {
            return [];
        }
        if (Array.isArray(raw)) {
            return raw.map(String);
        }
        return [String(raw)];
    }

    /**
     * Синхронизация зависимостей для multiselect заданий в админке:
     * автодобавление разрешимых зависимостей + предупреждения (как на lab_detail).
     */
    const AdminTaskDependencyUi = (function dependencyUiFactory() {
        const ATTR_NS = 'taskDep';
        let warnedMissingCore = false;

        function ensureCore() {
            if (Core) {
                return true;
            }
            if (!warnedMissingCore) {
                console.warn('[admin task deps] Подключите js/task_dependency_core.js перед load_levels.js');
                warnedMissingCore = true;
            }
            return false;
        }

        function formatLabels(pks, index) {
            return pks.map(function(pk) {
                const rec = index.byPk.get(pk);
                if (!rec) {
                    return pk;
                }
                const code = rec.task_id ? ('№' + String(rec.task_id) + ' ') : '';
                const desc = (rec.description || '').slice(0, 80);
                return (code + desc).trim() || pk;
            });
        }

        function getNoticeHost($select) {
            let $host = $select.siblings('.select2-container').last();
            if (!$host.length) {
                $host = $select;
            }
            return $host;
        }

        function getOrCreateNotice($select) {
            const id = $select.attr('id');
            if (!id) {
                return $();
            }
            const noticeId = id + '-task-dep-notice';
            let el = document.getElementById(noticeId);
            if (!el) {
                el = document.createElement('div');
                el.id = noticeId;
                el.className = 'task-dep-admin-notice';
                el.setAttribute('role', 'status');
                const hostEl = getNoticeHost($select)[0] || $select[0];
                hostEl.insertAdjacentElement('afterend', el);
            }
            return $(el);
        }

        function setHighlight($select, level) {
            const $c = $select.siblings('.select2-container');
            $c.removeClass('admin-task-dep-select-highlight admin-task-dep-select-highlight--error');
            if (level === 'info') {
                $c.addClass('admin-task-dep-select-highlight');
            } else if (level === 'error') {
                $c.addClass('admin-task-dep-select-highlight--error');
            }
        }

        function flashHighlight($select, level, ms) {
            setHighlight($select, level);
            const t = $select.data(ATTR_NS + 'HighlightTimer');
            if (t) {
                clearTimeout(t);
            }
            $select.data(
                ATTR_NS + 'HighlightTimer',
                setTimeout(function() {
                    setHighlight($select, null);
                }, ms || 7000)
            );
        }

        function showNotice($select, html, variant) {
            const $n = getOrCreateNotice($select);
            if (!$n.length) {
                return;
            }
            $n.removeClass('task-dep-admin-notice--info task-dep-admin-notice--error');
            if (variant === 'error') {
                $n.addClass('task-dep-admin-notice--error');
                flashHighlight($select, 'error');
            } else if (variant === 'info') {
                $n.addClass('task-dep-admin-notice--info');
                flashHighlight($select, 'info');
            }
            $n.html(html);
        }

        function clearNotice($select) {
            const id = $select.attr('id');
            if (id) {
                const el = document.getElementById(id + '-task-dep-notice');
                if (el) {
                    el.remove();
                }
            }
            setHighlight($select, null);
        }

        function storeMetadata($select, tasksPayload, index) {
            $select.data(ATTR_NS + 'Index', index);
            $select.data(ATTR_NS + 'Payload', tasksPayload);
        }

        function applySync($select) {
            if (!ensureCore()) {
                return;
            }
            if ($select.data(ATTR_NS + 'Internal')) {
                return;
            }
            const index = $select.data(ATTR_NS + 'Index');
            if (!index) {
                return;
            }

            let selected = normalizeMultiSelectVal($select.val());
            const addedOrder = [];
            const seenAdded = new Set();
            let iterations = 0;
            const maxIterations = 100;

            while (iterations < maxIterations) {
                iterations += 1;
                const expanded = Core.expandSelectionWithDependencies(selected, index);
                if (!expanded.changed) {
                    break;
                }
                expanded.added.forEach(function(pk) {
                    if (!seenAdded.has(pk)) {
                        seenAdded.add(pk);
                        addedOrder.push(pk);
                    }
                });
                selected = expanded.nextSelected;
            }

            if (addedOrder.length) {
                $select.data(ATTR_NS + 'Internal', true);
                try {
                    $select.val(selected).trigger('change');
                } finally {
                    $select.removeData(ATTR_NS + 'Internal');
                }
            }

            const unresolved = Core.listUnresolvedDependencyKeys(selected, index);
            const chunks = [];

            if (addedOrder.length) {
                const labels = formatLabels(addedOrder, index);
                const lines = labels
                    .map(function(l) {
                        return '• ' + $('<div>').text(l).html();
                    })
                    .join('<br>');
                chunks.push(
                    '<strong>Зависимости заданий.</strong> Автоматически добавлены в выбор:<br>' + lines
                );
            }

            if (unresolved.length) {
                const keys = unresolved
                    .map(function(k) {
                        return $('<div>').text(k).html();
                    })
                    .join(', ');
                chunks.push(
                    '<strong>Нет заданий в этой лабораторной работе с идентификаторами:</strong> ' +
                        keys +
                        '. Проверьте поле «Идентификаторы заданий-зависимостей» в карточке задания.'
                );
            }

            if (chunks.length) {
                showNotice($select, chunks.join('<br><br>'), unresolved.length ? 'error' : 'info');
            } else {
                clearNotice($select);
            }
        }

        function bind($select) {
            if (!ensureCore() || !$select.is('select[multiple]')) {
                return;
            }
            $select.off('.taskDepSync');
            const run = function() {
                applySync($select);
            };
            $select.on(
                'change.taskDepSync select2:select.taskDepSync select2:unselect.taskDepSync',
                run
            );
        }

        return {
            storeMetadata: storeMetadata,
            bind: bind,
            applySync: applySync,
            clearNotice: clearNotice,
        };
    })();

    initMainLabObserver();

    $("select[id^='id_kkz_labs-'][id$='-lab']").each(function() {
        initInlineLabObserver($(this));
    });

    function initLabHandlers() {
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

    $(document).on('formset:added', function() {
        setTimeout(function() {
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
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
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
        if (!$labSelect2.length) {
            return;
        }

        const $rendered = $labSelect2.find(".select2-selection__rendered");
        if (!$rendered.length) {
            return;
        }

        const prefix = $labField.attr("id").replace("-lab", "");
        const tasksSelector = "#" + prefix + "-tasks";

        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
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

    function handleLabChange(labSlug, levelsSelector, tasksSelector, setNumTasks) {
        if (setNumTasks === undefined) {
            setNumTasks = true;
        }
        if (labSlug && labSlug !== "---------") {
            if (levelsSelector) {
                loadLevels(labSlug, levelsSelector);
            }
            if (tasksSelector) {
                loadTasks(labSlug, tasksSelector, setNumTasks);
            }
        }
    }

    $(document).on('formset:added', function(event, $row, formsetName) {
        if (formsetName === 'kkz_labs') {
            setTimeout(function() {
                $row.find('select[id$="-lab"]').each(function() {
                    $(this).attr('id').replace('-lab', '-tasks');
                });
            }, 100);
        }
    });

    function loadLevels(labSlug, levelsSelector) {
        const parts = labSlug.split(' - ');
        const labName = parts.slice(0, -1).join(' - ');
        const labTypeDisplay = parts[parts.length - 1];

        $.ajax({
            url: '/api/get_lab_levels/' + encodeURIComponent(labName) + '/',
            type: 'GET',
            data: {
                lab_type_display: labTypeDisplay,
            },
            success: function(response) {
                const $field = $(levelsSelector);
                $field.empty().append('<option value="">---------</option>');
                response.forEach(function(level) {
                    $field.append(
                        $('<option>', {
                            value: level.id,
                            text: 'Вариант ' + level.level_number + ' - ' + level.description,
                        })
                    );
                });
                $field.trigger('change.select2');
            },
        });
    }

    function dedupeTasksById(tasks) {
        const out = [];
        const seen = new Set();
        for (let i = 0; i < tasks.length; i += 1) {
            const t = tasks[i];
            if (seen.has(t.id)) {
                continue;
            }
            seen.add(t.id);
            out.push(t);
        }
        return out;
    }

    function loadTasks(labSlug, tasksSelector, setNumTasks) {
        const $tasksField = $(tasksSelector);
        if (!$tasksField.length) {
            return;
        }

        const parts = labSlug.split(' - ');
        const labName = parts.slice(0, -1).join(' - ');
        const labTypeDisplay = parts[parts.length - 1];

        if (loadTasksPending[tasksSelector]) {
            loadTasksPending[tasksSelector].abort();
        }

        AdminTaskDependencyUi.clearNotice($tasksField);

        const xhr = $.ajax({
            url: '/api/lab_tasks/' + encodeURIComponent(labName) + '/',
            type: 'GET',
            data: {
                lab_type_display: labTypeDisplay,
            },
            success: function(response) {
                if (loadTasksPending[tasksSelector] !== xhr) {
                    return;
                }
                delete loadTasksPending[tasksSelector];

                const selectedTasks = normalizeMultiSelectVal($tasksField.val());
                const tasksPayload = dedupeTasksById(response);
                const index = Core ? Core.buildLabTaskDependencyIndex(tasksPayload) : null;

                const uniqueTasks = new Map();
                tasksPayload.forEach(function(task) {
                    if (!uniqueTasks.has(task.id)) {
                        uniqueTasks.set(task.id, task.description);
                    }
                });

                const allowedIds = new Set(Array.from(uniqueTasks.keys(), String));
                const toSelect = selectedTasks.filter(function(id) {
                    return allowedIds.has(String(id));
                });

                $tasksField.empty();
                uniqueTasks.forEach(function(description, id) {
                    $tasksField.append($('<option></option>').val(id).text(description));
                });

                $tasksField.val(toSelect).trigger('change');

                if (setNumTasks) {
                    const numTasksSelector = tasksSelector.replace(/-tasks$/, '-num_tasks');
                    const $numTasks = $(numTasksSelector);
                    if ($numTasks.length) {
                        $numTasks.val(uniqueTasks.size);
                    }
                }

                if (index) {
                    AdminTaskDependencyUi.storeMetadata($tasksField, tasksPayload, index);
                    AdminTaskDependencyUi.bind($tasksField);
                    AdminTaskDependencyUi.applySync($tasksField);
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
            },
        });
        loadTasksPending[tasksSelector] = xhr;
    }
});
