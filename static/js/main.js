/* ═══════════════════════════════════════════════════
   ChimneyCare — Main JavaScript
   Navigation, flash messages, scroll reveals, AJAX
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Mobile Nav Toggle ────────────────────
  const navToggle = document.querySelector('.nav__toggle');
  const navLinks = document.querySelector('.nav__links');

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('open');
      navToggle.classList.toggle('active');
    });

    // Close on link click
    navLinks.querySelectorAll('.nav__link').forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('open');
        navToggle.classList.remove('active');
      });
    });
  }

  // ── Flash Message Auto-Dismiss ───────────
  const flashMessages = document.querySelectorAll('.flash');
  flashMessages.forEach((flash, index) => {
    // Auto dismiss after 5 seconds
    setTimeout(() => {
      flash.classList.add('fade-out');
      setTimeout(() => flash.remove(), 300);
    }, 5000 + index * 500);

    // Click to dismiss
    flash.addEventListener('click', () => {
      flash.classList.add('fade-out');
      setTimeout(() => flash.remove(), 300);
    });
  });

  // ── Scroll Reveal Animations ─────────────
  const revealElements = document.querySelectorAll('.reveal');

  if (revealElements.length > 0) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    );

    revealElements.forEach(el => observer.observe(el));
  }

  // ── Navbar Scroll Effect ─────────────────
  const nav = document.querySelector('.nav');
  if (nav) {
    let lastScroll = 0;
    window.addEventListener('scroll', () => {
      const currentScroll = window.pageYOffset;
      if (currentScroll > 50) {
        nav.style.background = 'rgba(15, 15, 15, 0.98)';
      } else {
        nav.style.background = 'rgba(15, 15, 15, 0.92)';
      }
      lastScroll = currentScroll;
    });
  }

  // ── CSRF Token Helper ────────────────────
  window.getCSRFToken = function() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  };

  // ── AJAX Helper with CSRF ────────────────
  window.fetchWithCSRF = async function(url, options = {}) {
    const defaults = {
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
      },
    };
    const merged = {
      ...defaults,
      ...options,
      headers: { ...defaults.headers, ...options.headers },
    };
    return fetch(url, merged);
  };

  // ── Client-side Form Validation ──────────
  document.querySelectorAll('form[data-validate]').forEach(form => {
    form.addEventListener('submit', (e) => {
      let valid = true;

      // Required fields
      form.querySelectorAll('[required]').forEach(field => {
        const errorEl = field.parentElement.querySelector('.form-error');
        if (!field.value.trim()) {
          valid = false;
          field.style.borderColor = 'var(--error)';
          if (errorEl) errorEl.textContent = 'This field is required.';
        } else {
          field.style.borderColor = '';
          if (errorEl) errorEl.textContent = '';
        }
      });

      // Email validation
      form.querySelectorAll('input[type="email"]').forEach(field => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (field.value && !emailRegex.test(field.value)) {
          valid = false;
          field.style.borderColor = 'var(--error)';
        }
      });

      // Phone validation
      form.querySelectorAll('input[data-validate-phone]').forEach(field => {
        const phoneRegex = /^(\+91)?[6-9]\d{9}$/;
        const cleaned = field.value.replace(/[\s\-\(\)]/g, '');
        if (cleaned && !phoneRegex.test(cleaned)) {
          valid = false;
          field.style.borderColor = 'var(--error)';
        }
      });

      // Password match
      const password = form.querySelector('input[name="password"]');
      const confirm = form.querySelector('input[name="confirm_password"]');
      if (password && confirm && password.value !== confirm.value) {
        valid = false;
        confirm.style.borderColor = 'var(--error)';
      }

      if (!valid) {
        e.preventDefault();
      }
    });
  });

  // ── Show/Hide Password ───────────────────
  document.querySelectorAll('.password-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const input = toggle.previousElementSibling;
      if (input && input.type === 'password') {
        input.type = 'text';
        toggle.textContent = '🙈';
      } else if (input) {
        input.type = 'password';
        toggle.textContent = '👁';
      }
    });
  });

  // ── Smooth scroll for anchor links ───────
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

});
