/* ═══════════════════════════════════════════════════
   ChimneyCare — Marketplace JavaScript
   Product filtering, promo code validation
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Seamless AJAX Product Filtering (No Page Reload) ──────────────
  const filterForm = document.getElementById('filter-form');
  const resultsContainer = document.getElementById('marketplace-results');

  async function applyFilters(pushHistory = true) {
    if (!filterForm || !resultsContainer) return;

    const formData = new FormData(filterForm);
    const params = new URLSearchParams();
    for (const [key, value] of formData.entries()) {
      if (value) params.append(key, value);
    }

    const targetUrl = `${filterForm.action || window.location.pathname}?${params.toString()}`;

    // Visual loading state
    resultsContainer.style.opacity = '0.4';
    resultsContainer.style.pointerEvents = 'none';

    try {
      const response = await fetch(targetUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (response.ok) {
        const htmlText = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, 'text/html');
        const newResults = doc.getElementById('marketplace-results');

        if (newResults) {
          resultsContainer.innerHTML = newResults.innerHTML;
        }

        if (pushHistory) {
          window.history.pushState({ path: targetUrl }, '', targetUrl);
        }
      } else {
        window.location.href = targetUrl;
      }
    } catch (err) {
      console.error('Filter fetch error:', err);
      filterForm.submit(); // Graceful fallback
    } finally {
      resultsContainer.style.opacity = '1';
      resultsContainer.style.pointerEvents = 'auto';
    }
  }

  if (filterForm) {
    filterForm.querySelectorAll('select').forEach(select => {
      select.addEventListener('change', () => {
        applyFilters(true);
      });
    });

    filterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      applyFilters(true);
    });
  }

  // Handle browser Back/Forward navigation smoothly
  window.addEventListener('popstate', () => {
    // Sync select dropdowns with URL params
    const urlParams = new URLSearchParams(window.location.search);
    if (filterForm) {
      filterForm.querySelectorAll('select').forEach(select => {
        select.value = urlParams.get(select.name) || '';
      });
      applyFilters(false);
    }
  });

  // Dynamic delegate for "Reset Filters" button
  document.addEventListener('click', (e) => {
    if (e.target && e.target.id === 'reset-filters-btn') {
      e.preventDefault();
      if (filterForm) {
        filterForm.querySelectorAll('select').forEach(select => {
          select.value = '';
        });
        applyFilters(true);
      }
    }
  });

  // ── Price Range Inputs ───────────────────
  const priceInputs = document.querySelectorAll('.filter-bar input[type="number"]');
  let priceTimeout;
  priceInputs.forEach(input => {
    input.addEventListener('input', () => {
      clearTimeout(priceTimeout);
      priceTimeout = setTimeout(() => {
        applyFilters(true);
      }, 500);
    });
  });


  // ── Promo Code Validation (AJAX) ─────────
  const promoInput = document.getElementById('promo-code');
  const promoBtn = document.getElementById('apply-promo');
  const promoResult = document.getElementById('promo-result');
  const subtotalEl = document.getElementById('order-subtotal');
  const totalEl = document.getElementById('order-total');
  const discountRow = document.getElementById('discount-row');
  const discountAmount = document.getElementById('discount-amount');
  const promoHidden = document.getElementById('promo-code-hidden');

  if (promoBtn && promoInput) {
    promoBtn.addEventListener('click', async () => {
      const code = promoInput.value.trim();
      if (!code) {
        showPromoError('Please enter a promo code.');
        return;
      }

      const subtotal = parseFloat(subtotalEl?.dataset?.value || '0');
      promoBtn.disabled = true;
      promoBtn.textContent = 'Checking...';

      try {
        const response = await fetchWithCSRF('/marketplace/validate-promo', {
          method: 'POST',
          body: JSON.stringify({ code, subtotal }),
        });

        const data = await response.json();

        if (data.valid) {
          showPromoSuccess(data);
          // Update totals
          if (discountRow) discountRow.style.display = 'flex';
          if (discountAmount) discountAmount.textContent = `−₹${data.discount_amount.toLocaleString()}`;
          if (totalEl) totalEl.textContent = `₹${data.final_total.toLocaleString()}`;
          if (promoHidden) promoHidden.value = code;
        } else {
          showPromoError(data.error);
        }
      } catch (err) {
        showPromoError('Network error. Please try again.');
      }

      promoBtn.disabled = false;
      promoBtn.textContent = 'Apply';
    });
  }

  function showPromoSuccess(data) {
    if (!promoResult) return;
    const label = data.discount_type === 'percentage'
      ? `${data.value}% off`
      : `₹${data.value} off`;
    promoResult.innerHTML = `<span class="text-success">✓ Code applied! ${label} — you save ₹${data.discount_amount.toLocaleString()}</span>`;
  }

  function showPromoError(message) {
    if (!promoResult) return;
    promoResult.innerHTML = `<span class="text-error">✗ ${message}</span>`;
    if (discountRow) discountRow.style.display = 'none';
  }

  // ── Exchange Offer Toggle ────────────────
  const exchangeToggle = document.getElementById('has-exchange');
  const exchangeFields = document.getElementById('exchange-fields');

  if (exchangeToggle && exchangeFields) {
    exchangeToggle.addEventListener('change', () => {
      exchangeFields.style.display = exchangeToggle.checked ? 'block' : 'none';
    });
  }

});
