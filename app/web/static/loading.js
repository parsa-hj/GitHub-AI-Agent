(function () {
    var overlay = document.getElementById('loading-overlay');
    var messageEl = document.getElementById('loading-message');
    if (!overlay || !messageEl) return;

    var messages = {
        '/review': 'Reviewing changes…',
        '/draft': 'Drafting issue/PR…',
        '/improve': 'Improving issue/PR…',
        '/approve': 'Creating on GitHub…'
    };

    function showLoading(action) {
        messageEl.textContent = messages[action] || 'Working…';
        overlay.classList.add('is-visible');
        overlay.setAttribute('aria-hidden', 'false');
    }

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (form.method && form.method.toLowerCase() !== 'post') return;
        var action = (form.getAttribute('action') || form.action || '').split('?')[0];
        var path = action.indexOf('/review') !== -1 ? '/review' : action.indexOf('/draft') !== -1 ? '/draft' : action.indexOf('/improve') !== -1 ? '/improve' : action.indexOf('/approve') !== -1 ? '/approve' : null;
        if (path) showLoading(path);
    }, true);
})();
