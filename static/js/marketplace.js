/* ═══════════════════════════════════════════════════
   ChimneyCare — Marketplace JavaScript
   Product filtering, promo code validation
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Filter Form Auto-Submit ──────────────
  const filterForm = document.getElementById('filter-form');
  if (filterForm) {
    filterForm.querySelectorAll('select').forEach(select => {
      select.addEventListener('change', () => {
        filterForm.submit();
      });
    });
  }

  // ── Price Range Inputs ───────────────────
  const priceInputs = document.querySelectorAll('.filter-bar input[type="number"]');
  let priceTimeout;
  priceInputs.forEach(input => {
    input.addEventListener('input', () => {
      clearTimeout(priceTimeout);
      priceTimeout = setTimeout(() => {
        if (filterForm) filterForm.submit();
      }, 800);
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
