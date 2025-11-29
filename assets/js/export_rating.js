class ExportRating {
    constructor(containerElement) {
        this.$container = $(containerElement);
        this.slug = this.$container.data('slug');
        this.type = this.$container.data('type');
        this.solutions = [];
        this.grades = [];
        this.maxTasks = 0;

        this.init();
    }

    init() {
        // Tab switching
        this.$container.find('.tabs li').on('click', (e) => {
            const $tab = $(e.currentTarget);
            const tabName = $tab.data('tab');
            
            this.$container.find('.tabs li').removeClass('is-active');
            $tab.addClass('is-active');
            
            $('.tab-content').hide();
            $(`#tab-${tabName}`).show();
            
            // Hide download buttons and preview on tab change
            $('#preview-section').hide();
            this.$container.find('.download-xlsx-btn').hide();
        });

        // Button handlers
        $('#generate-grades-by-tasks').on('click', () => this.generateGradesByTasks());
        $('#generate-grades-by-position').on('click', () => this.generateGradesByPosition());
        
        // Add click handlers to all download buttons
        this.$container.find('.download-xlsx-btn').on('click', () => this.downloadXlsx());
        
        // Hide download buttons by default
        this.$container.find('.download-xlsx-btn').hide();

        // Load solutions data
        this.loadSolutions();
    }

    loadSolutions() {
        const url = this.type === 'kkz'
            ? `/api/get_kkz_solutions/${this.slug}/`
            : `/api/get_competition_solutions/${this.slug}/`;

        $.ajax({
            url: url,
            type: 'GET',
            success: (response) => {
                this.solutions = response.solutions || [];
                this.maxTasks = Math.max(...this.solutions.map(s => s.total_tasks || s.max_tasks || 1), 1);
            },
            error: (xhr, status, error) => {
                this.showError(`Ошибка загрузки данных: ${error}`);
            }
        });
    }

    validateTasksInputs() {
        const grade5 = parseInt($('#grade-5-tasks').val()) || 0;
        const grade4 = parseInt($('#grade-4-tasks').val()) || 0;
        const grade3 = parseInt($('#grade-3-tasks').val()) || 0;

        if (grade5 < 0 || grade4 < 0 || grade3 < 0) {
            this.showError('Количество заданий не может быть отрицательным');
            return false;
        }

        if (grade5 > this.maxTasks || grade4 > this.maxTasks || grade3 > this.maxTasks) {
            this.showError(`Количество заданий не может превышать максимальное (${this.maxTasks})`);
            return false;
        }

        if (grade5 < grade4 || grade4 < grade3) {
            this.showError('Оценка "5" должна требовать не меньше заданий, чем оценка "4", а оценка "4" - не меньше, чем оценка "3"');
            return false;
        }

        return { grade5, grade4, grade3 };
    }

    validatePositionInputs() {
        const grade5 = parseInt($('#grade-5-position').val()) || 0;
        const grade4 = parseInt($('#grade-4-position').val()) || 0;
        const grade3 = parseInt($('#grade-3-position').val()) || 0;

        if (grade5 < 0 || grade4 < 0 || grade3 < 0) {
            this.showError('Количество студентов не может быть отрицательным');
            return false;
        }

        const total = grade5 + grade4 + grade3;
        if (total > this.solutions.length) {
            this.showError(`Общее количество студентов (${total}) превышает количество студентов (${this.solutions.length})`);
            return false;
        }

        return { grade5, grade4, grade3 };
    }

    generateGradesByTasks() {
        this.hideError();

        if (this.solutions.length === 0) {
            this.showError('Данные еще не загружены. Пожалуйста, подождите.');
            return;
        }

        const inputs = this.validateTasksInputs();
        if (!inputs) return;

        const { grade5, grade4, grade3 } = inputs;

        // Sort solutions by progress (descending) and then by last name (ascending)
        const sortedSolutions = [...this.solutions].sort((a, b) => {
            if (b.progress !== a.progress) {
                return b.progress - a.progress;
            }
            return a.user_last_name.localeCompare(b.user_last_name, 'ru');
        });

        // Assign grades based on tasks solved
        this.grades = sortedSolutions.map(solution => {
            let grade = 2;
            const tasksSolved = solution.progress || 0;

            if (grade5 > 0 && tasksSolved >= grade5) {
                grade = 5;
            } else if (grade4 > 0 && tasksSolved >= grade4) {
                grade = 4;
            } else if (grade3 > 0 && tasksSolved >= grade3) {
                grade = 3;
            }

            return { ...solution, grade };
        });

        // Sort by last name alphabetically for display
        this.grades.sort((a, b) => a.user_last_name.localeCompare(b.user_last_name, 'ru'));

        this.showPreview();
    }

    generateGradesByPosition() {
        this.hideError();

        if (this.solutions.length === 0) {
            this.showError('Данные еще не загружены. Пожалуйста, подождите.');
            return;
        }

        const inputs = this.validatePositionInputs();
        if (!inputs) return;

        const { grade5, grade4, grade3 } = inputs;

        // Sort solutions by position (ascending)
        const sortedSolutions = [...this.solutions].sort((a, b) => {
            if (a.pos !== b.pos) {
                return a.pos - b.pos;
            }
            return a.user_last_name.localeCompare(b.user_last_name, 'ru');
        });

        // Assign grades based on position
        this.grades = sortedSolutions.map((solution, index) => {
            let grade = 2;
            const position = index + 1;

            if (position <= grade5) {
                grade = 5;
            } else if (position <= grade5 + grade4) {
                grade = 4;
            } else if (position <= grade5 + grade4 + grade3) {
                grade = 3;
            }

            return { ...solution, grade };
        });

        // Sort by last name alphabetically for display
        this.grades.sort((a, b) => a.user_last_name.localeCompare(b.user_last_name, 'ru'));

        this.showPreview();
    }

    showPreview() {
        const $previewSection = $('#preview-section');
        const $tableBody = $('#preview-table-body');
        
        // Find the download button in the currently visible tab
        const $tabByTasks = $('#tab-by-tasks');
        const $tabByPosition = $('#tab-by-position');
        let $downloadButton = null;
        
        if ($tabByTasks.is(':visible')) {
            $downloadButton = $tabByTasks.find('.download-xlsx-btn');
        } else if ($tabByPosition.is(':visible')) {
            $downloadButton = $tabByPosition.find('.download-xlsx-btn');
        }

        // Clear and populate table
        $tableBody.empty();
        
        this.grades.forEach(item => {
            const $row = $('<tr>').html(`
                <td>${this.escapeHtml(item.user_last_name)}</td>
                <td>${this.escapeHtml(item.user_first_name)}</td>
                <td><strong>${item.grade}</strong></td>
                <td>${item.pos}</td>
                <td>${item.progress || 0}</td>
            `);
            $tableBody.append($row);
        });

        // Animate preview appearance
        if (typeof gsap !== 'undefined') {
            gsap.fromTo($previewSection[0],
                { opacity: 0, y: 20 },
                { opacity: 1, y: 0, duration: 1, ease: "power2.out" }
            );
        }

        $previewSection.show();
        if ($downloadButton) {
            $downloadButton.show();
        }
        
        // Scroll to preview
        $('html, body').animate({
            scrollTop: $previewSection.offset().top - 20
        }, 500);
    }

    downloadXlsx() {
        if (this.grades.length === 0) {
            this.showError('Нет данных для экспорта');
            return;
        }

        const exportData = {
            type: this.type,
            slug: this.slug,
            grades: this.grades.map(item => ({
                last_name: item.user_last_name,
                first_name: item.user_first_name,
                grade: item.grade,
                position: item.pos,
                tasks_solved: item.progress || 0
            }))
        };

        const csrftoken = $('[name=csrf-token]').attr('content') || 
            $('meta[name=csrf-token]').attr('content');

        $.ajax({
            url: '/api/export_grades_xlsx/',
            type: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            },
            data: JSON.stringify(exportData),
            contentType: 'application/json',
            xhrFields: {
                responseType: 'blob'
            },
            success: (data, status, xhr) => {
                // Get filename from Content-Disposition header
                const contentDisposition = xhr.getResponseHeader('Content-Disposition');
                let filename = 'grades.xlsx';
                
                if (contentDisposition) {
                    // Try RFC 5987 format first
                    const rfc5987Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
                    if (rfc5987Match && rfc5987Match[1]) {
                        try {
                            filename = decodeURIComponent(rfc5987Match[1]);
                        } catch (e) {
                            console.error('Error decoding RFC 5987 filename:', e);
                        }
                    }
                    
                    // Fallback to regular format
                    if (filename === 'grades.xlsx') {
                        let filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
                        if (!filenameMatch) {
                            filenameMatch = contentDisposition.match(/filename=([^;]+)/);
                        }
                        if (filenameMatch && filenameMatch[1]) {
                            filename = filenameMatch[1].trim().replace(/^["']|["']$/g, '');
                        }
                    }
                }

                // Create download link
                const url = window.URL.createObjectURL(data);
                const $a = $('<a>').attr({
                    href: url,
                    download: filename
                }).hide();
                
                $('body').append($a);
                $a[0].click();
                $a.remove();
                window.URL.revokeObjectURL(url);
            },
            error: (xhr, status, error) => {
                console.error('Export error:', error);
                this.showError(`Ошибка при экспорте: ${error}`);
            }
        });
    }

    showError(message) {
        const $errorDiv = $('#error-message');
        $errorDiv.text(message).show();
        
        // Scroll to error
        $('html, body').animate({
            scrollTop: $errorDiv.offset().top - 20
        }, 500);
    }

    hideError() {
        $('#error-message').hide();
    }

    escapeHtml(text) {
        return $('<div>').text(text).html();
    }
}

$(document).ready(function() {
    const $container = $('#export-rating-container');
    if ($container.length) {
        window.exportRating = new ExportRating($container[0]);
    }
});
