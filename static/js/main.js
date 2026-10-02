/**
 * NET Evangelistic Team Platform — Main JS
 * ==========================================
 * Handles: mobile sidebar, flash auto-dismiss,
 *          date defaults, general UI helpers
 */

// ── Progressive Web App ─────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

// ── Mobile Sidebar ──────────────────────────────────────────────────────────
document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  // Close sidebar when clicking outside on mobile
  if (window.innerWidth <= 768 &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(e.target) &&
      !e.target.closest('.hamburger')) {
    sidebar.classList.remove('open');
  }
});

// ── Flash Auto-Dismiss ──────────────────────────────────────────────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity .5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  }, 5000);
});

// ── Set today's date on date inputs that have placeholder "today" ───────────
document.querySelectorAll('input[type="date"]').forEach(input => {
  if (!input.value && !input.dataset.noDefault) {
    input.value = new Date().toISOString().split('T')[0];
  }
});

// ── Confirm before destructive forms ───────────────────────────────────────
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', e => {
    if (!confirm(form.dataset.confirm)) e.preventDefault();
  });
});

// ── Active nav highlighting ─────────────────────────────────────────────────
const path = window.location.pathname;
document.querySelectorAll('.nav-item').forEach(link => {
  if (link.href && link.href.includes(path) && path !== '/') {
    link.classList.add('active');
  }
});
