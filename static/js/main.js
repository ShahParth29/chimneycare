/* ═══════════════════════════════════════════════════
   ChimneyCare — Main JavaScript
   Navigation, flash messages, scroll reveals, AJAX
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Mobile Nav Toggle & Drawer ──────────────
  const navToggle = document.getElementById('nav-toggle') || document.querySelector('.nav__toggle');
  const mobileDrawer = document.getElementById('mobile-drawer');
  const navOverlay = document.getElementById('nav-overlay');

  function openMobileNav() {
    if (!mobileDrawer || !navToggle) return;
    mobileDrawer.classList.add('open');
    mobileDrawer.setAttribute('aria-hidden', 'false');
    navToggle.classList.add('active');
    navToggle.setAttribute('aria-expanded', 'true');
    if (navOverlay) navOverlay.classList.add('open');
    document.body.classList.add('nav-open');
  }

  function closeMobileNav() {
    if (!mobileDrawer || !navToggle) return;
    mobileDrawer.classList.remove('open');
    mobileDrawer.setAttribute('aria-hidden', 'true');
    navToggle.classList.remove('active');
    navToggle.setAttribute('aria-expanded', 'false');
    if (navOverlay) navOverlay.classList.remove('open');
    document.body.classList.remove('nav-open');
  }

  if (navToggle && mobileDrawer) {
    navToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = mobileDrawer.classList.contains('open');
      if (isOpen) {
        closeMobileNav();
      } else {
        openMobileNav();
      }
    });

    // Close on link or button click inside mobile drawer
    mobileDrawer.querySelectorAll('a, button').forEach(link => {
      link.addEventListener('click', () => {
        closeMobileNav();
      });
    });

    // Close on backdrop overlay click
    if (navOverlay) {
      navOverlay.addEventListener('click', closeMobileNav);
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && mobileDrawer.classList.contains('open')) {
        closeMobileNav();
      }
    });

    // Reset mobile nav state on window resize (e.g. desktop view)
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768) {
        closeMobileNav();
      }
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
    window.addEventListener('scroll', () => {
      if (window.pageYOffset > 20) {
        nav.classList.add('nav--scrolled');
      } else {
        nav.classList.remove('nav--scrolled');
      }
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

      // Phone validation (accepts 7-15 digits with optional + and formatting)
      form.querySelectorAll('input[data-validate-phone]').forEach(field => {
        const errorEl = field.parentElement.querySelector('.form-error');
        const cleaned = field.value.replace(/[\s\-\(\)]/g, '');
        const phoneRegex = /^\+?[0-9]{7,15}$/;
        if (cleaned && !phoneRegex.test(cleaned)) {
          valid = false;
          field.style.borderColor = 'var(--error)';
          if (errorEl) errorEl.textContent = 'Please enter a valid phone number (at least 7-10 digits).';
        } else if (cleaned) {
          field.style.borderColor = '';
          if (errorEl) errorEl.textContent = '';
        }
      });

      // Reset border and error on input
      form.querySelectorAll('input, select, textarea').forEach(input => {
        input.addEventListener('input', () => {
          input.style.borderColor = '';
          const err = input.parentElement.querySelector('.form-error');
          if (err) err.textContent = '';
        });
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
