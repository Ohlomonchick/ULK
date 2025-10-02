(function($) {
    $(function() {
        let currentInline = null;

        function ensurePreviewContainer() {
            let $c = $('#kkz-random-preview');
            if (!$c.length) {
                $c = $('<div id="kkz-random-preview" style="margin:1rem 0; padding:0.8rem; border:1px solid #e6e6e6; background:#fff;"></div>');
                const $inlines = $('.dynamic-kkz_labs, .inline-group').first();
                if ($inlines.length) $inlines.after($c);
                else $('form').first().append($c);
            }
            return $c;
        }

        const $preview = ensurePreviewContainer();

        function collectGlobalSelection() {
            const kkzId = $('#id').val() || null;
            const platoonVals = $('#id_platoons').val() || [];
            const nonPlatoonVals = $('#id_non_platoon_users').val() || [];

            return {
                kkz_id: kkzId,
                platoon_ids: platoonVals.join(','),
                user_ids: nonPlatoonVals.join(',')
            };
        }

        function renderPreview(data) {
            const tasksById = {};
            data.tasks.forEach(t => tasksById[t.id] = t.description);

            let html = '<h4 style="margin-top:0;">Просмотр распределения (обновляется автоматически)</h4>';
            html += `<p style="margin:0 0 .5rem 0;"><strong>Лабораторная работа:</strong> ${data.lab.name || ''} — <strong>Студентов:</strong> ${data.users.length}</p>`;
            html += '<button type="button" id="kkz-regen" style="margin-bottom:1rem;">Перегенерировать случайно</button>';
            html += '<div class="kkz-preview-grid">';

            if (!data.users.length) {
                html += '<div class="help">Студенты не найдены (выберите взвода или студентов на первой вкладке).</div>';
            } else {
                data.users.forEach(u => {
                    const assigned = data.assignments[u.id] || [];
                    html += '<div class="kkz-preview-user" style="margin-bottom:.7rem; padding:.3rem; border-bottom:1px solid #f0f0f0;">';
                    html += `<div style="font-weight:600">${u.display || u.username}</div>`;
                    html += '<select multiple class="kkz-edit-tasks" data-user-id="' + u.id + '" style="width:100%; height:100px;">';
                    data.tasks.forEach(t => {
                        const sel = assigned.includes(t.id) ? ' selected' : '';
                        html += `<option value="${t.id}"${sel}>${t.description}</option>`;
                    });
                    html += '</select>';
                    html += '</div>';
                });
            }

            html += '</div>';
            $preview.html(html);
        }

        function updateAssignmentForUser(userId, taskIds) {
            if (!currentInline) {
                console.warn('No currentInline set');
                return;
            }

            const $assignInput = currentInline.find('input[id$="-assignments"]');
            if (!$assignInput.length) {
                console.warn('No assignments input found');
                return;
            }
            console.log('Found assignments input:', $assignInput.attr('id'));

            // Читаем существующие assignments
            let assignments = {};
            const existingValue = $assignInput.val();
            if (existingValue) {
                try {
                    assignments = JSON.parse(existingValue);
                } catch (e) {
                    console.error('Failed to parse existing assignments:', e);
                }
            }

            // Обновляем только для конкретного пользователя
            assignments[userId] = taskIds;

            // Сохраняем обратно
            $assignInput.val(JSON.stringify(assignments));
            console.log('Updated assignment for user', userId, ':', taskIds);
        }

        function syncAllVisibleAssignments() {
            if (!currentInline) return;

            const $assignInput = currentInline.find('input[id$="-assignments"]');
            if (!$assignInput.length) return;

            // Читаем существующие assignments
            let assignments = {};
            const existingValue = $assignInput.val();
            if (existingValue) {
                try {
                    assignments = JSON.parse(existingValue);
                } catch (e) {
                    console.error('Failed to parse existing assignments:', e);
                }
            }

            // Обновляем все видимые селекты
            $('.kkz-edit-tasks').each(function() {
                const $sel = $(this);
                const uid = String($sel.data('user-id'));
                const selected = $sel.val() || [];
                assignments[uid] = selected.map(id => parseInt(id));
            });

            $assignInput.val(JSON.stringify(assignments));
            console.log('Synced all visible assignments:', assignments);
        }

        $(document).on('change', '.kkz-edit-tasks', function() {
            const $select = $(this);
            const userId = String($select.data('user-id'));
            const taskIds = ($select.val() || []).map(id => parseInt(id));
            const labId = currentInline ? currentInline.find('select[id$="-lab"]').val() : null;
            const kkzId = $('#id').val();

            updateAssignmentForUser(userId, taskIds);

            if (kkzId && labId) {
                const payload = {
                    kkz_id: kkzId,
                    lab_id: labId,
                    assignments: {
                        [userId]: taskIds
                    }
                };

                $.ajax({
                    url: '/api/kkz_save_preview/',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(payload),
                    success: function(resp) {
                        console.log('Saved preview to server for user', userId);
                    },
                    error: function(err) {
                        console.error('Error saving preview', err);
                    }
                });
            }
        });

        $(document).on('click', '#kkz-regen', function() {
            if (currentInline) {
                fetchPreviewForInline(currentInline, true);
            }
        });

        function fetchPreviewForInline($inlineRow, forceRegen = false) {
            const labId = $inlineRow.find('select[id$="-lab"]').val();
            const numTasks = $inlineRow.find('input[id$="-num_tasks"]').val() || 0;
            const unified = $('#id_unified_tasks').is(':checked') || false;

            const selectedTasks = $inlineRow.find('select[id$="-tasks"]').val() || [];
            console.log('Selected tasks:', selectedTasks);

            const globals = collectGlobalSelection();

            const $assignInput = $inlineRow.find('input[id$="-assignments"]');
            console.log('Looking for assignments input in inline:', $inlineRow.attr('id'));
            console.log('Found assignments inputs:', $inlineRow.find('input[type="hidden"]').map(function() {
                return $(this).attr('id');
            }).get());
            console.log('Assignments input exists:', $assignInput.length > 0, $assignInput.attr('id'));

            const params = {
                lab_id: labId,
                num_tasks: numTasks,
                unified: unified ? 'true' : 'false'
            };

            if (selectedTasks.length > 0) {
                params.selected_tasks = selectedTasks.join(',');
            }
            if (forceRegen) {
                params.force_regen = 'true';
            }
            if (globals.kkz_id) params.kkz_id = globals.kkz_id;
            else {
                if (globals.platoon_ids) params.platoon_ids = globals.platoon_ids;
                if (globals.user_ids) params.user_ids = globals.user_ids;
            }

            const url = '/api/kkz_preview_random/';

            $.getJSON(url, params)
                .done(function(data) {
                    currentInline = $inlineRow;
                    renderPreview(data);

                    // Сохраняем assignments в hidden поле
                    const $assignInput = $inlineRow.find('input[id$="-assignments"]');
                    if ($assignInput.length) {
                        $assignInput.val(JSON.stringify(data.assignments));
                        console.log('Set initial assignments:', data.assignments);
                    }

                    if (globals.kkz_id) {
                        const payload = {
                            kkz_id: globals.kkz_id,
                            lab_id: data.lab.id,
                            assignments: data.assignments
                        };
                        $.ajax({
                            url: '/api/kkz_save_preview/',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify(payload),
                            success: function(resp) {
                                console.log('Saved preview to server', resp);
                            },
                            error: function(err) {
                                console.error('Error saving preview', err);
                            }
                        });
                    }
                })
                .fail(function() {
                    $preview.html('<div class="error">Ошибка получения превью.</div>');
                });
        }

        function handleChangeEvent(e) {
            const $target = $(e.target);
            const $inline = $target.closest('.inline-related');
            if ($inline.length) {
                fetchPreviewForInline($inline);
            } else {
                const $first = $('.dynamic-kkz_labs .inline-related').first();
                if ($first.length) fetchPreviewForInline($first);
            }
        }

        $(document).on('change', '.dynamic-kkz_labs select[id$="-lab"], .dynamic-kkz_labs input[id$="-num_tasks"], .dynamic-kkz_labs select[id$="-tasks"]', handleChangeEvent);
        $(document).on('change', '#id_unified_tasks, #id_platoons, #id_non_platoon_users', handleChangeEvent);
        $(document).on('formset:added', function(event, $row, formsetName) {
            if (formsetName && formsetName.indexOf('kkz_labs') !== -1) {
                setTimeout(function() {
                    fetchPreviewForInline($row);
                }, 120);
            }
        });

        // Перед отправкой формы собираем все видимые выборы
        $('form').on('submit', function(e) {
            console.log('Form submitting, syncing all visible assignments...');
            syncAllVisibleAssignments();
        });

        const $firstInline = $('.dynamic-kkz_labs .inline-related').first();
        if ($firstInline.length) {
            fetchPreviewForInline($firstInline);
        } else {
            $preview.html('<div class="help">Добавьте лабораторную, чтобы увидеть превью.</div>');
        }
    });
})(django.jQuery);