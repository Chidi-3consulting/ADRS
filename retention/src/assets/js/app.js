// ADRS unobtrusive behaviours — replaces inline on* handlers so a strict (nonce-based)
// Content-Security-Policy can be enforced without 'unsafe-inline' for scripts.
(function () {
  'use strict';

  // Confirmation guard: <form data-confirm="..."> or a submit <button data-confirm="...">.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    var msg = form.getAttribute('data-confirm');
    if (!msg && e.submitter) { msg = e.submitter.getAttribute('data-confirm'); }
    if (msg && !window.confirm(msg)) { e.preventDefault(); }
  }, true);

  // [data-print] -> window.print();  [data-select] -> select the field's text.
  document.addEventListener('click', function (e) {
    var p = e.target.closest('[data-print]');
    if (p) { e.preventDefault(); window.print(); return; }
    var s = e.target.closest('[data-select]');
    if (s && typeof s.select === 'function') { s.select(); }
  });
})();
