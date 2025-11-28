class ExportRating {
    constructor(containerElement) {
        this.container = containerElement;
        this.slug = containerElement.dataset.slug;
        this.type = containerElement.dataset.type;
        this.solutions = [];
        this.grades = [];
        this.maxTasks = 0;

        this.init();
    }

    init() {
        // Tab switching
        const tabs = this.container.querySelectorAll('.tabs li');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('is-active'));
                tab.classList.add('is-active');

                const tabName = tab.dataset.tab;
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.style.display = 'none';
                });

                if (tabName === 'by-tasks') {
                    document.getElementById('tab-by-tasks').style.display = 'block';
                } else {
                    document.getElementById('tab-by-position').style.display = 'block';
                }

                // Hide download buttons and preview on tab change
                const previewSection = document.getElementById('preview-section');
                if (previewSection) previewSection.style.display = 'none';
                this.container.querySelectorAll('.download-xlsx-btn').forEach(btn => {
                    btn.style.display = 'none';
                });
            });
        });

        // Button handlers
        document.getElementById('generate-grades-by-tasks').addEventListener('click', () => {
            this.generateGradesByTasks();
        });

        document.getElementById('generate-grades-by-position').addEventListener('click', () => {
            this.generateGradesByPosition();
        });

        // Add click handlers to all download buttons
        this.container.querySelectorAll('.download-xlsx-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.downloadXlsx();
            });
        });

        // Hide download buttons by default
        this.container.querySelectorAll('.download-xlsx-btn').forEach(btn => {
            btn.style.display = 'none';
        });

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
                // Find max tasks
                this.maxTasks = Math.max(...this.solutions.map(s => s.total_tasks || s.max_tasks || 1), 1);
            },
            error: (xhr, status, error) => {
                this.showError(`Ошибка загрузки данных: ${error}`);
            }
        });
    }

    validateTasksInputs() {
        const grade5 = parseInt(document.getElementById('grade-5-tasks').value) || 0;
        const grade4 = parseInt(document.getElementById('grade-4-tasks').value) || 0;
        const grade3 = parseInt(document.getElementById('grade-3-tasks').value) || 0;

        if (grade5 < 0 || grade4 < 0 || grade3 < 0) {
            this.showError('Количество заданий не может быть отрицательным');
            return false;
        }

        if (grade5 > this.maxTasks || grade4 > this.maxTasks || grade3 > this.maxTasks) {
            this.showError(`Количество заданий не может превышать максимальное (${this.maxTasks})`);
            return false;
        }

        // Validate that grade5 >= grade4 >= grade3 (higher grade should require more or equal tasks)
        if (grade5 < grade4 || grade4 < grade3) {
            this.showError('Оценка "5" должна требовать не меньше заданий, чем оценка "4", а оценка "4" - не меньше, чем оценка "3"');
            return false;
        }

        return { grade5, grade4, grade3 };
    }

    validatePositionInputs() {
        const grade5 = parseInt(document.getElementById('grade-5-position').value) || 0;
        const grade4 = parseInt(document.getElementById('grade-4-position').value) || 0;
        const grade3 = parseInt(document.getElementById('grade-3-position').value) || 0;

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

        // Sort solutions by progress (descending) and then by last name (ascending) for tie-breaking
        const sortedSolutions = [...this.solutions].sort((a, b) => {
            if (b.progress !== a.progress) {
                return b.progress - a.progress;
            }
            return a.user_last_name.localeCompare(b.user_last_name, 'ru');
        });

        // Assign grades based on tasks solved
        // Use descending order: check highest grade first
        this.grades = sortedSolutions.map(solution => {
            let grade = 2; // Default grade
            const tasksSolved = solution.progress || 0;

            // Check from highest to lowest
            if (grade5 > 0 && tasksSolved >= grade5) {
                grade = 5;
            } else if (grade4 > 0 && tasksSolved >= grade4) {
                grade = 4;
            } else if (grade3 >= 0 && tasksSolved >= grade3) {
                grade = 3;
            }

            return {
                ...solution,
                grade: grade
            };
        });

        // Sort by last name alphabetically for display
        this.grades.sort((a, b) => {
            return a.user_last_name.localeCompare(b.user_last_name, 'ru');
        });

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

        // Sort solutions by position (ascending) - they already have positions from API
        const sortedSolutions = [...this.solutions].sort((a, b) => {
            if (a.pos !== b.pos) {
                return a.pos - b.pos;
            }
            return a.user_last_name.localeCompare(b.user_last_name, 'ru');
        });

        // Assign grades based on position
        this.grades = sortedSolutions.map((solution, index) => {
            let grade = 2; // Default grade
            const position = index + 1;

            if (position <= grade5) {
                grade = 5;
            } else if (position <= grade5 + grade4) {
                grade = 4;
            } else if (position <= grade5 + grade4 + grade3) {
                grade = 3;
            }

            return {
                ...solution,
                grade: grade
            };
        });

        // Sort by last name alphabetically for display
        this.grades.sort((a, b) => {
            return a.user_last_name.localeCompare(b.user_last_name, 'ru');
        });

        this.showPreview();
    }

    showPreview() {
        const previewSection = document.getElementById('preview-section');
        const tableBody = document.getElementById('preview-table-body');
        
        // Find the download button in the currently visible tab
        let downloadButton = null;
        const tabByTasks = document.getElementById('tab-by-tasks');
        const tabByPosition = document.getElementById('tab-by-position');
        
        if (tabByTasks && tabByTasks.style.display !== 'none') {
            downloadButton = tabByTasks.querySelector('.download-xlsx-btn');
        } else if (tabByPosition && tabByPosition.style.display !== 'none') {
            downloadButton = tabByPosition.querySelector('.download-xlsx-btn');
        }

        // Clear previous content
        tableBody.innerHTML = '';

        // Populate table
        this.grades.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.escapeHtml(item.user_last_name)}</td>
                <td>${this.escapeHtml(item.user_first_name)}</td>
                <td><strong>${item.grade}</strong></td>
                <td>${item.pos}</td>
                <td>${item.progress || 0}</td>
            `;
            tableBody.appendChild(row);
        });

        // Animate preview appearance
        if (typeof gsap !== 'undefined') {
            gsap.fromTo(previewSection,
                { opacity: 0, y: 20 },
                { opacity: 1, y: 0, duration: 1, ease: "power2.out" }
            );
        }

        previewSection.style.display = 'block';
        // Show download button when preview is shown (for both methods)
        if (downloadButton) {
            downloadButton.style.display = 'block';
        }
        // Scroll to preview
        previewSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

        // Send request to export endpoint using fetch for better header handling
        const csrftoken = document.querySelector('[name=csrf-token]')?.content ||
            document.querySelector('meta[name=csrf-token]')?.content;

        fetch('/api/export_grades_xlsx/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(exportData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // Get filename from Content-Disposition header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'grades.xlsx';
            
            if (contentDisposition) {
                console.log('Content-Disposition:', contentDisposition);
                
                // Try RFC 5987 format first (filename*=UTF-8''encoded) - this is the modern standard
                const rfc5987Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
                if (rfc5987Match && rfc5987Match[1]) {
                    try {
                        filename = decodeURIComponent(rfc5987Match[1]);
                        console.log('Parsed filename from RFC 5987:', filename);
                    } catch (e) {
                        console.error('Error decoding RFC 5987 filename:', e);
                    }
                }
                
                // If not found in RFC 5987 format, try regular format (fallback)
                if (filename === 'grades.xlsx') {
                    // Try with quotes first
                    let filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
                    if (!filenameMatch) {
                        // Try without quotes but before semicolon
                        filenameMatch = contentDisposition.match(/filename=([^;]+)/);
                    }
                    if (filenameMatch && filenameMatch[1]) {
                        filename = filenameMatch[1].trim();
                        // Remove any remaining quotes
                        filename = filename.replace(/^["']|["']$/g, '');
                        console.log('Parsed filename from regular format:', filename);
                    }
                }
            } else {
                console.warn('Content-Disposition header not found');
            }

            console.log('Final filename:', filename);
            
            // Get blob from response
            return response.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        })
        .catch(error => {
            console.error('Export error:', error);
            this.showError(`Ошибка при экспорте: ${error.message}`);
        });
    }

    showError(message) {
        const errorDiv = document.getElementById('error-message');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';

        // Scroll to error
        errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    hideError() {
        document.getElementById('error-message').style.display = 'none';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('export-rating-container');
    if (container) {
        window.exportRating = new ExportRating(container);
    }
});
