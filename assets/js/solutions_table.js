class SolutionsTable {
    constructor(containerElement) {
        this.container = containerElement;
        this.slug = containerElement.dataset.slug;
        this.type = containerElement.dataset.type; 
        this.showTeam = containerElement.dataset.showTeam === 'True';
        this.showMaxTasks = containerElement.dataset.showMaxTasks === 'True';
        this.tableBody = document.querySelector('#solutions-table');
        this.progressBar = document.querySelector('#total-progress-bar');
        
        this.init();
    }
    
    init() {
        if (typeof gsap !== 'undefined' && typeof Flip !== 'undefined') {
            gsap.registerPlugin(Flip);
        }
        
        this.refresh();
        this.intervalId = setInterval(() => this.refresh(), 10000);
    }
    
    refresh() {
        const url = this.type === 'kkz' 
            ? `/api/get_kkz_solutions/${this.slug}/`
            : `/api/get_competition_solutions/${this.slug}/`;
        
        $.ajax({
            url: url,
            type: 'GET',
            success: (response) => this.updateTable(response),
            error: (xhr, status, error) => {
                console.error(`Error loading ${this.type} solutions:`, error);
            }
        });
    }
    
    updateTable(response) {
        const oldState = Flip.getState(this.tableBody.querySelectorAll('tr[data-flip-id]'));
        const existingRows = {};
        this.tableBody.querySelectorAll('tr[data-flip-id]').forEach(row => {
            const id = row.getAttribute('data-flip-id');
            existingRows[id] = row;
        });
        
        const newRows = [];
        
        if (this.progressBar && response.total_progress !== undefined) {
            this.progressBar.value = response.total_progress;
            this.progressBar.max = response.max_total_progress || 100;
        }
        
        if (!response.solutions || response.solutions.length === 0) {
            const colSpan = this.calculateColSpan();
            this.tableBody.innerHTML = `
                <tr>
                    <td colspan="${colSpan}" style="text-align: center; color: gray;">
                        Пока никто не выполнил работу
                    </td>
                </tr>
            `;
            return;
        }

        response.solutions.forEach(solution => {
            const id = solution.user_id || solution.pos;
            let row = existingRows[id];
            
            if (!row) {
                row = document.createElement('tr');
                row.setAttribute('data-flip-id', id);
            }
            
            row.innerHTML = this.renderRow(solution, response);
            newRows.push(row);
        });

        this.tableBody.innerHTML = '';
        newRows.forEach(row => this.tableBody.appendChild(row));

        if (typeof Flip !== 'undefined') {
            Flip.from(oldState, {
                duration: 2,
                ease: "power1.inOut"
            });
        }
    }
    
    renderRow(solution, response) {
        const totalTasks = this.showMaxTasks 
            ? solution.max_tasks || solution.total_tasks || 1
            : solution.total_tasks || 1;
        
        let html = `
            <th>${solution.pos}</th>
            <td>${solution.user_first_name}</td>
            <td>${solution.user_last_name}</td>
            <td>${solution.user_platoon}</td>
        `;
        
        if (this.showTeam) {
            html += `<td>${solution.team_name || ''}</td>`;
        }
        
        html += `
            <td style="text-align: center;">${solution.progress}/${totalTasks}</td>
            <td>
                <progress class="progress is-success" 
                          value="${solution.progress}" 
                          max="${totalTasks}">
                    ${solution.progress}
                </progress>
            </td>
        `;

        if (this.type === 'kkz') {
            html += `<td>${solution.datetime || ''}</td>`;
        } else {
            html += `
                <td>${solution.spent || ''}</td>
                <td>${solution.datetime || ''}</td>
            `;
        }
        
        return html;
    }
    
    calculateColSpan() {
        let cols = 7; 
        if (this.showTeam) cols++;
        if (this.type === 'competition') cols++; 
        return cols;
    }
    
    destroy() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('solutions-container');
    if (container) {
        window.solutionsTable = new SolutionsTable(container);
    }
});