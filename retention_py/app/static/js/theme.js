/* SafeData theme: Light / Dark / System. Mirrors the 3Consulting theme kit and also drives Bootstrap 5.3 (data-bs-theme). */
(function () {
  var KEY = 'tc-theme', root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : { matches: true };
  function saved() { try { return localStorage.getItem(KEY) || 'system'; } catch (e) { return 'system'; } }
  function resolve(m) { return m === 'system' ? (mq.matches ? 'dark' : 'light') : m; }
  function apply(m) {
    var t = resolve(m);
    root.setAttribute('data-theme', t); root.setAttribute('data-bs-theme', t); root.setAttribute('data-theme-mode', m);
    var btns = document.querySelectorAll('.tc-theme-switch button');
    for (var i = 0; i < btns.length; i++) btns[i].setAttribute('aria-pressed', String(btns[i].getAttribute('data-mode') === m));
  }
  function set(m) { try { localStorage.setItem(KEY, m); } catch (e) {} apply(m); }
  apply(saved());
  if (mq.addEventListener) mq.addEventListener('change', function () { if (saved() === 'system') apply('system'); });
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.tc-theme-switch button') : null;
    if (b) set(b.getAttribute('data-mode'));
  });
  document.addEventListener('DOMContentLoaded', function () { apply(saved()); });
  window.TCTheme = { set: set, get: saved };
})();
