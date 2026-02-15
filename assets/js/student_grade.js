(function() {
    var COLORS = { 5: '#48c774', 4: '#3273dc', 3: '#ffdd57', 2: '#f14668' };
    function textColor(g) { return g === 3 ? '#363636' : '#fff'; }

    function showGrade($panel, grade) {
        var $box = $panel.find('#student-grade-box');
        var $val = $panel.find('#student-grade-value');
        var g = parseInt(grade, 10);
        if (g >= 2 && g <= 5) {
            $box.css({ background: COLORS[g], color: textColor(g) });
            $val.text(g);
            $panel.show();
        }
    }

    $(document).ready(function() {
        var $panel = $('#student-grade-panel');
        if (!$panel.length) return;
        var slug = $panel.data('competition-slug') || $panel.attr('data-competition-slug');
        if (!slug) return;

        var initial = $panel.attr('data-initial-grade');
        if (initial) showGrade($panel, initial);

        function poll() {
            $.ajax({
                url: '/api/my_grade/' + encodeURIComponent(slug) + '/?t=' + Date.now(),
                type: 'GET',
                dataType: 'json',
                cache: false,
                success: function(data) {
                    if (data && (data.grade === 2 || data.grade === 3 || data.grade === 4 || data.grade === 5)) {
                        showGrade($panel, data.grade);
                    }
                }
            });
        }
        poll();
        setInterval(poll, 3000);
    });
})();
