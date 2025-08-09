gsap.registerPlugin(Flip);
function refreshSolutions() {
    if (!document.getElementById('competition-slug')) { return; }
    var competitionSlug = document.getElementById('competition-slug').getAttribute('data-slug');
    $.ajax({
        url: `/api/get_competition_solutions/${competitionSlug}/`,
        type: 'GET',
        success: function(response) {
            var tableBody = document.querySelector('#solutions-table');
            var oldState = Flip.getState(tableBody.querySelectorAll('tr[data-flip-id]'));
            console.log("Old state:", oldState);
            const existingRows = {};
            tableBody.querySelectorAll('tr[data-flip-id]').forEach(row => {
              const id = row.getAttribute('data-flip-id');
              existingRows[id] = row;
            });
            const newRows = [];
            {#tableBody.innerHTML = '';#}

            var totalProgressBar = document.querySelector('#total-progress-bar');

            if (totalProgressBar) {
                totalProgressBar.value = response.total_progress;
                totalProgressBar.max = response.max_total_progress;
                totalProgressBar.textContent = response.total_progress + '%';
            }


            if (response.solutions.length === 0) {
                const row = document.createElement('tr');
                tableBody.innerHTML = `
                        <td colspan = 6 style="text-align: center; color: gray;">Пока никто не выполнил работу</td>
                `;
                newRows.push(row);
            } else {
                response.solutions.forEach(function(solution) {
                    const id = solution.user_id || solution.pos;
                    let row = existingRows[id];
                    if (!row) {
                      row = document.createElement('tr');
                      row.setAttribute('data-flip-id', id);
                    }
                    row.innerHTML = `
                        <th>${solution.pos}</th>
                        <td>${solution.user_first_name}</td>
                        <td>${solution.user_last_name}</td>
                        <td>${solution.user_platoon}</td>
                        {% if is_team_competition %}
                            <td>${solution.team_name}</td>
                        {% endif %}
                        {% if object.tasks %}
                            <td>${solution.progress}/${response.total_tasks}</td>
                            <td><progress class="progress is-success" value="${solution.progress}" max="${response.total_tasks}">${solution.progress}</progress></td>
                        {% endif %}
                        <td>${solution.spent}</td>
                        <td>${solution.datetime}</td>
                        `;
                    {#tableBody.appendChild(row);#}
                    newRows.push(row);
                });
            }
            // Clear the table body (but not remove rows that might be reused elsewhere)
            tableBody.innerHTML = '';
            // Append each row in the new order
            newRows.forEach(function(row) {
              tableBody.appendChild(row);
            });
            Flip.from(oldState, {
                duration: 2,
                ease: "power1.inOut"
            });
        },
        error: function(xhr, status, error) {
            console.error("Error loading solutions:", error);
        }
    });
}

setInterval(refreshSolutions, 10000);