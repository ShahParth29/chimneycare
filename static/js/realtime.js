/* ═══════════════════════════════════════════════════
   ChimneyCare — Supabase Realtime Notifications
   Uses Supabase JS client (CDN) for WebSocket subscriptions
   ═══════════════════════════════════════════════════ */

(function() {
  'use strict';

  // Config is injected via a <script> tag in the template
  const SUPABASE_URL = window.__SUPABASE_URL__ || '';
  const SUPABASE_ANON_KEY = window.__SUPABASE_ANON_KEY__ || '';
  const CURRENT_USER_ID = window.__CURRENT_USER_ID__ || '';

  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !CURRENT_USER_ID) {
    return; // No config — skip realtime
  }

  let supabase;

  async function initRealtime() {
    // Wait for Supabase JS to load from CDN
    if (typeof window.supabase === 'undefined') {
      console.warn('[Realtime] Supabase JS not loaded');
      return;
    }

    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

    // Subscribe to service booking changes
    supabase
      .channel('services-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'services',
          filter: `customer_id=eq.${CURRENT_USER_ID}`,
        },
        (payload) => {
          handleServiceUpdate(payload);
        }
      )
      .subscribe();

    // Subscribe to repair job changes
    supabase
      .channel('repair-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'repair_jobs',
          filter: `customer_id=eq.${CURRENT_USER_ID}`,
        },
        (payload) => {
          handleRepairUpdate(payload);
        }
      )
      .subscribe();

    // Subscribe to order changes
    supabase
      .channel('order-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'orders',
          filter: `customer_id=eq.${CURRENT_USER_ID}`,
        },
        (payload) => {
          handleOrderUpdate(payload);
        }
      )
      .subscribe();

    console.log('[Realtime] Subscribed to updates');
  }

  function handleServiceUpdate(payload) {
    const record = payload.new;
    const eventType = payload.eventType;

    let title = 'Booking Update';
    let message = '';

    if (eventType === 'INSERT') {
      title = '🎉 Booking Confirmed!';
      message = `Your service booking ${record.order_id || ''} has been confirmed. We'll take care of the rest.`;
    } else if (eventType === 'UPDATE') {
      const statusMap = {
        confirmed: 'Your booking has been confirmed.',
        in_progress: 'A technician is on the way!',
        completed: 'Your service has been completed. Thank you!',
        cancelled: 'Your booking has been cancelled.',
      };
      message = statusMap[record.status] || `Status updated to: ${record.status}`;
    }

    showRealtimeToast(title, message);
  }

  function handleRepairUpdate(payload) {
    const record = payload.new;
    const eventType = payload.eventType;

    let title = 'Repair Update';
    let message = '';

    if (eventType === 'INSERT') {
      title = '🔧 Repair Request Received';
      message = 'Your repair request has been received. We will contact you within 24 hours.';
    } else if (eventType === 'UPDATE') {
      const statusMap = {
        confirmed: 'Your repair has been confirmed after telephonic verification.',
        in_progress: 'Repair work is in progress.',
        completed: 'Your repair has been completed!',
        cancelled: 'Your repair request has been cancelled.',
      };
      message = statusMap[record.confirmation_status] || `Status: ${record.confirmation_status}`;
    }

    showRealtimeToast(title, message);
  }

  function handleOrderUpdate(payload) {
    const record = payload.new;
    const eventType = payload.eventType;

    let title = 'Order Update';
    let message = '';

    if (eventType === 'INSERT') {
      title = '📦 Order Placed!';
      message = `Your order ${record.order_id || ''} has been placed successfully.`;
    } else if (eventType === 'UPDATE') {
      const statusMap = {
        processing: 'Your order is being processed.',
        shipped: 'Your order has been shipped!',
        delivered: 'Your order has been delivered!',
        cancelled: 'Your order has been cancelled.',
      };
      message = statusMap[record.status] || `Status: ${record.status}`;
    }

    showRealtimeToast(title, message);
  }

  function showRealtimeToast(title, message) {
    let toast = document.querySelector('.realtime-toast');

    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'realtime-toast';
      toast.innerHTML = `
        <div class="realtime-toast__title"></div>
        <div class="realtime-toast__message"></div>
      `;
      document.body.appendChild(toast);
    }

    toast.querySelector('.realtime-toast__title').textContent = title;
    toast.querySelector('.realtime-toast__message').textContent = message;

    // Show
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    // Auto-hide after 8 seconds
    clearTimeout(toast._hideTimeout);
    toast._hideTimeout = setTimeout(() => {
      toast.classList.remove('show');
    }, 8000);

    // Click to dismiss
    toast.onclick = () => {
      toast.classList.remove('show');
    };
  }

  // Init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRealtime);
  } else {
    initRealtime();
  }

})();
