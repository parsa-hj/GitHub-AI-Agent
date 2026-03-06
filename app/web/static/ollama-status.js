(function () {
    var el = document.getElementById('ollama-status-nav');
    if (!el) return;
    function render(connected, message) {
        el.innerHTML = '';
        var span = document.createElement('span');
        span.className = 'ollama-status ' + (connected ? 'ollama-ok' : 'ollama-fail');
        span.setAttribute('title', message || (connected ? 'Ollama connected' : 'Ollama not connected'));
        span.textContent = connected ? 'Ollama: connected' : 'Ollama: disconnected';
        el.appendChild(span);
    }
    render(false, 'Checking…');
    fetch('/api/ollama-status')
        .then(function (r) { return r.json(); })
        .then(function (d) {
            var ok = d.reachable && d.model_available;
            render(ok, d.message || (ok ? 'Connected' : 'Not connected'));
        })
        .catch(function () {
            render(false, 'Could not check status');
        });
})();
