/* ═══════════════════════════════════════════════════
   ChimneyCare — Admin Dashboard JavaScript
   Responsive Sidebar, Modals, Search & Realtime Alerts
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Sidebar Active State ─────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.admin-sidebar__link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('admin-sidebar__link--active');
    }
  });

  // ── Mobile Sidebar Toggle & Backdrop ─────
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('admin-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  const sidebarClose = document.getElementById('sidebar-close');

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    if (backdrop) backdrop.classList.add('active');
    if (sidebarClose) sidebarClose.style.display = 'block';
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      if (sidebar && sidebar.classList.contains('open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (sidebarClose) {
    sidebarClose.addEventListener('click', closeSidebar);
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeSidebar);
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
      closeSidebar();
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

  // ── Admin Toast Notification Helper ─────
  window.showAdminToast = function(title, message, icon = '🔔') {
    const container = document.getElementById('admin-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'admin-toast';
    toast.innerHTML = `
      <span style="font-size:1.4rem;">${icon}</span>
      <div>
        <strong style="display:block; font-size:0.9rem;">${title}</strong>
        <span style="font-size:0.8rem; opacity:0.9;">${message}</span>
      </div>
    `;
    container.appendChild(toast);

    // Audio chime (gentle beep)
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 659.25; // E5
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.35);
    } catch(e) {}

    setTimeout(() => {
      toast.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 400);
    }, 5000);
  };

  // ── Realtime Supabase Subscriptions for Admin ─────
  if (typeof window.supabase !== 'undefined' && window.__SUPABASE_URL__ && window.__SUPABASE_ANON_KEY__) {
    try {
      const sbClient = window.supabase.createClient(window.__SUPABASE_URL__, window.__SUPABASE_ANON_KEY__);

      // 1. New Service Bookings
      sbClient.channel('admin-services')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'services' }, (payload) => {
          const rec = payload.new || {};
          showAdminToast('New Booking Received', `Order ID: ${rec.order_id || 'New Service'}`, '📅');
        })
        .subscribe();

      // 2. New Repair Requests
      sbClient.channel('admin-repairs')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'repair_jobs' }, (payload) => {
          const rec = payload.new || {};
          showAdminToast('New Repair Request', `Service ID: ${rec.service_id || 'Diagnostic Job'}`, '🔧');
        })
        .subscribe();

      // 3. New Marketplace Orders
      sbClient.channel('admin-orders')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'orders' }, (payload) => {
          const rec = payload.new || {};
          showAdminToast('New Chimney Order Placed', `Order: ${rec.order_id || 'Store Purchase'}`, '📦');
        })
        .subscribe();

      console.log('[Admin Realtime] Active listening for bookings, repairs & orders.');
    } catch(e) {
      console.warn('[Admin Realtime] Failed to initialize:', e);
    }
  }

});
