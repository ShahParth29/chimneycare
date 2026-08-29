/* ═══════════════════════════════════════════════════
   ChimneyCare — Admin Dashboard JavaScript
   Tab switching, modals, CRUD interactions
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Sidebar Active State ─────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.admin-sidebar__link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('admin-sidebar__link--active');
    }
  });

  // ── Mobile Sidebar Toggle ────────────────
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.admin-sidebar');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }

  // ── Modal System ─────────────────────────
  window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  };

  // Close modal on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
  });

  // Close modal on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(overlay => {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
      });
    }
  });

  // ── Confirm Delete ───────────────────────
  document.querySelectorAll('[data-confirm]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const message = btn.dataset.confirm || 'Are you sure?';
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });

  // ── File Upload Preview ──────────────────
  document.querySelectorAll('input[type="file"][data-preview]').forEach(input => {
    input.addEventListener('change', (e) => {
      const previewId = input.dataset.preview;
      const preview = document.getElementById(previewId);
      if (preview && e.target.files[0]) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          preview.src = ev.target.result;
          preview.style.display = 'block';
        };
        reader.readAsDataURL(e.target.files[0]);
      }
    });
  });

  // ── Status Update Forms ──────────────────
  document.querySelectorAll('.status-select').forEach(select => {
    select.addEventListener('change', function() {
      const form = this.closest('form');
      if (form && confirm('Update status to "' + this.value + '"?')) {
        form.submit();
      }
    });
  });

  // ── Search/Filter in Admin Tables ────────
  const tableSearch = document.getElementById('table-search');
  if (tableSearch) {
    tableSearch.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      const rows = document.querySelectorAll('.data-table tbody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }

});
