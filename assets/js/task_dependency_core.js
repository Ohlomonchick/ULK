/**
 * Общая логика графа зависимостей LabTask (id PK, task_id как ключ, поле dependencies CSV).
 * Используется админкой (select) и может подключаться на lab_detail для парсинга CSV.
 */
(function (global) {
    'use strict';

    function normalizeKey(raw) {
        if (raw === null || raw === undefined) {
            return null;
        }
        const s = String(raw).trim();
        return s.length ? s : null;
    }

    function parseDependencyKeysCsv(raw) {
        if (!raw) {
            return [];
        }
        return String(raw)
            .split(',')
            .map(normalizeKey)
            .filter(Boolean);
    }

    /**
     * @param {Array<{id: number, task_id?: string|null, description?: string, dependencies?: string|null}>} tasks
     */
    function buildLabTaskDependencyIndex(tasks) {
        const byPk = new Map();
        const keyToPk = new Map();

        for (let i = 0; i < tasks.length; i += 1) {
            const t = tasks[i];
            const pk = normalizeKey(t.id);
            if (!pk) {
                continue;
            }
            const deps = parseDependencyKeysCsv(t.dependencies);
            byPk.set(pk, {
                pk: pk,
                task_id: t.task_id,
                description: t.description || '',
                dependencies: deps,
            });
            keyToPk.set(pk, pk);
            const code = normalizeKey(t.task_id);
            if (code) {
                keyToPk.set(code, pk);
            }
        }

        return { byPk: byPk, keyToPk: keyToPk };
    }

    /**
     * Транзитивное замыкание: все разрешимые по keyToPk зависимости попадают в выбор.
     * @param {string[]} selectedPks
     * @returns {{ nextSelected: string[], added: string[], changed: boolean }}
     */
    function expandSelectionWithDependencies(selectedPks, index) {
        const sel = new Set();
        for (let i = 0; i < selectedPks.length; i += 1) {
            sel.add(String(selectedPks[i]));
        }
        const added = [];
        let changed = false;
        const stack = Array.from(sel);
        while (stack.length) {
            const pk = stack.pop();
            const rec = index.byPk.get(pk);
            if (!rec) {
                continue;
            }
            for (let j = 0; j < rec.dependencies.length; j += 1) {
                const depKey = rec.dependencies[j];
                const depPk = index.keyToPk.get(depKey);
                if (depPk && !sel.has(depPk)) {
                    sel.add(depPk);
                    added.push(depPk);
                    stack.push(depPk);
                    changed = true;
                }
            }
        }
        return {
            nextSelected: Array.from(sel),
            added: added,
            changed: changed,
        };
    }

    /**
     * Ключи из поля dependencies, для которых нет задания в текущем наборе лабы.
     * @param {string[]} selectedPks
     */
    function listUnresolvedDependencyKeys(selectedPks, index) {
        const unresolved = [];
        const seen = new Set();
        const sel = new Set();
        for (let i = 0; i < selectedPks.length; i += 1) {
            sel.add(String(selectedPks[i]));
        }
        sel.forEach(function (pk) {
            const rec = index.byPk.get(pk);
            if (!rec) {
                return;
            }
            for (let j = 0; j < rec.dependencies.length; j += 1) {
                const depKey = rec.dependencies[j];
                if (!index.keyToPk.has(depKey) && !seen.has(depKey)) {
                    seen.add(depKey);
                    unresolved.push(depKey);
                }
            }
        });
        return unresolved;
    }

    global.TaskDependencyCore = {
        normalizeKey: normalizeKey,
        parseDependencyKeysCsv: parseDependencyKeysCsv,
        buildLabTaskDependencyIndex: buildLabTaskDependencyIndex,
        expandSelectionWithDependencies: expandSelectionWithDependencies,
        listUnresolvedDependencyKeys: listUnresolvedDependencyKeys,
    };
})(typeof window !== 'undefined' ? window : this);
