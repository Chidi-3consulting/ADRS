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

  // Mobile sidebar hamburger menu helper
  document.addEventListener('DOMContentLoaded', function() {
    // Add hamburger button to topbar if on mobile
    var topbar = document.querySelector('.topbar');
    if (topbar && window.innerWidth < 992) {
      var burger = document.createElement('button');
      burger.className = 'btn btn-outline-secondary btn-sm me-3 border-0';
      burger.innerHTML = '<i class="bi bi-list fs-4"></i>';
      burger.id = 'sidebarToggleMobile';
      topbar.insertBefore(burger, topbar.firstChild);

      var sidebar = document.querySelector('.sidebar');
      burger.addEventListener('click', function(e) {
        e.stopPropagation();
        sidebar.classList.toggle('show');
      });

      // Close sidebar when clicking outside
      document.addEventListener('click', function(e) {
        if (sidebar && sidebar.classList.contains('show') && !sidebar.contains(e.target) && e.target !== burger) {
          sidebar.classList.remove('show');
        }
      });
    }

    // Scroll to top button helper
    var scrollBtn = document.createElement('button');
    scrollBtn.className = 'btn btn-primary rounded-circle shadow-lg position-fixed d-none no-print';
    scrollBtn.style.bottom = '20px';
    scrollBtn.style.right = '20px';
    scrollBtn.style.width = '45px';
    scrollBtn.style.height = '45px';
    scrollBtn.style.zIndex = '1000';
    scrollBtn.innerHTML = '<i class="bi bi-arrow-up"></i>';
    document.body.appendChild(scrollBtn);

    window.addEventListener('scroll', function() {
      if (window.scrollY > 300) {
        scrollBtn.classList.remove('d-none');
      } else {
        scrollBtn.classList.add('d-none');
      }
    });

    scrollBtn.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
})();
