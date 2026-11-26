(function () {
    const BRIDGE = 'http://127.0.0.1:18499';
    function send(path) {
        try {
            fetch(BRIDGE + path, { mode: 'no-cors', keepalive: true }).catch(() => {});
        } catch (e) {}
    }
    try {
        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
        document.hasFocus = () => true;
        window.addEventListener('blur', e => e.stopImmediatePropagation(), true);
        document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
    } catch (e) {}

    window.close = function () {
        send('/aurora_exit_prompt');
    };

    function pollNowPlaying() {
        try {
            const h = location.hash || '';
            const q = h.indexOf('?') >= 0 ? h.slice(h.indexOf('?') + 1) : (location.search ? location.search.slice(1) : '');
            const params = new URLSearchParams(q);
            const vid = params.get('v') || '';
            const v = document.querySelector('video');
            const prog = (v && v.duration > 0) ? Math.min(99, Math.max(2, Math.round((v.currentTime / v.duration) * 100))) : 100;
            if (vid) {
                send('/aurora_yt?vid=' + encodeURIComponent(vid) + '&prog=' + prog);
            }
        } catch (e) {}
    }

    setInterval(pollNowPlaying, 4000);

    window.addEventListener('keydown', function (e) {
        const tag = (document.activeElement && document.activeElement.tagName) ? document.activeElement.tagName.toLowerCase() : '';
        const isInput = (tag === 'input' || tag === 'textarea');
        if (!isInput && (e.key === 'm' || e.key === 'M')) {
            e.preventDefault();
            e.stopPropagation();
            pollNowPlaying();
            send('/aurora_menu');
        }
    }, true);
})();
