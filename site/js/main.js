/* ============================================================
   White-Angels — Main Script
   Preloader, navigation, typing effect, scroll reveals, lightbox
   ============================================================ */

(function () {
  'use strict';

  /* ---------- PRELOADER ---------- */
  const preloader = document.getElementById('preloader');
  const mainContent = document.getElementById('main-content');
  const glitchSound = document.getElementById('glitch-sound');

  preloader.addEventListener('click', function () {
    if (glitchSound) {
      glitchSound.pause();
      glitchSound.currentTime = 0;
    }
    preloader.classList.add('hidden');
    mainContent.classList.remove('hidden');

    setTimeout(startTyping, 400);
    setTimeout(initRevealObserver, 200);
  });

  /* ---------- TYPING EFFECT ---------- */
  var taglineEl = document.getElementById('hero-tagline');
  var fullText = 'Open Source Intelligence & Development Network';
  var charIdx = 0;

  function startTyping() {
    if (charIdx < fullText.length) {
      taglineEl.textContent += fullText.charAt(charIdx);
      charIdx++;
      setTimeout(startTyping, Math.random() * 35 + 20);
    } else {
      setTimeout(function () {
        taglineEl.classList.add('done');
      }, 2000);
    }
  }

  /* ---------- NAVBAR SCROLL ---------- */
  var navbar = document.getElementById('navbar');
  var navLinks = document.querySelectorAll('.nav-link');
  var sections = document.querySelectorAll('.section');

  window.addEventListener('scroll', function () {
    // Sticky bg
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }

    // Active link highlight
    var scrollPos = window.scrollY + 200;
    sections.forEach(function (sec) {
      if (sec.offsetTop <= scrollPos && (sec.offsetTop + sec.offsetHeight) > scrollPos) {
        var id = sec.getAttribute('id');
        navLinks.forEach(function (l) { l.classList.remove('active'); });
        var activeLink = document.querySelector('.nav-link[data-section="' + id + '"]');
        if (activeLink) activeLink.classList.add('active');
      }
    });
  });

  /* ---------- MOBILE MENU ---------- */
  var burger = document.getElementById('nav-burger');
  var mobileMenu = document.getElementById('mobile-menu');
  var mobileLinks = document.querySelectorAll('.mobile-link');

  burger.addEventListener('click', function () {
    burger.classList.toggle('active');
    mobileMenu.classList.toggle('open');
  });

  mobileLinks.forEach(function (link) {
    link.addEventListener('click', function () {
      burger.classList.remove('active');
      mobileMenu.classList.remove('open');
    });
  });

  /* ---------- SCROLL REVEAL ---------- */
  function initRevealObserver() {
    var reveals = document.querySelectorAll('[data-reveal]');
    if (!('IntersectionObserver' in window)) {
      reveals.forEach(function (el) { el.classList.add('visible'); });
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    reveals.forEach(function (el) { observer.observe(el); });
  }

  /* ---------- CAT CURSOR ---------- */
  var cursorToggle = document.getElementById('cursor-toggle');
  var isCat = false;

  cursorToggle.addEventListener('click', function () {
    isCat = !isCat;
    document.body.classList.toggle('cat-cursor', isCat);
    cursorToggle.style.transform = 'scale(0.85)';
    setTimeout(function () { cursorToggle.style.transform = ''; }, 150);
  });

  /* ---------- LIGHTBOX ---------- */
  var lightbox = document.getElementById('lightbox');
  var lightboxImg = document.getElementById('lightbox-img');

  window.openLightbox = function (thumb) {
    var img = thumb.querySelector('img');
    if (!img || thumb.classList.contains('no-img')) return;
    lightboxImg.src = img.src;
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
  };

  window.closeLightbox = function () {
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
  };

  lightbox.addEventListener('click', function (e) {
    if (e.target === lightbox || e.target.closest('.lightbox-close')) {
      closeLightbox();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeLightbox();
  });

  /* ---------- STAT COUNTER ---------- */
  var counterDone = false;

  function animateCounters() {
    if (counterDone) return;
    counterDone = true;

    document.querySelectorAll('.stat-num[data-count]').forEach(function (el) {
      var target = parseInt(el.getAttribute('data-count'), 10);
      var current = 0;
      var step = Math.ceil(target / 60);
      var timer = setInterval(function () {
        current += step;
        if (current >= target) {
          el.textContent = target + '+';
          clearInterval(timer);
        } else {
          el.textContent = current;
        }
      }, 20);
    });
  }

  // Observe the cases section for counter animation
  document.addEventListener('DOMContentLoaded', function () {
    var casesHero = document.querySelector('.cases-hero');
    if (!casesHero) return;

    if (!('IntersectionObserver' in window)) {
      animateCounters();
      return;
    }

    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCounters();
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.3 });

    obs.observe(casesHero);
  });

  /* ---------- SMOOTH SCROLL FOR NAV LINKS ---------- */
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  /* ---------- PAW CLICK EFFECT ---------- */
  document.addEventListener('click', function (e) {
    var paw = document.createElement('div');
    paw.innerHTML = '<svg width="24" height="24" viewBox="0 0 32 32"><path fill="rgba(167,139,250,0.4)" d="M16 16C26 16 30 22 26 30C22 34 10 34 6 30C2 22 6 16 16 16Z"/><circle cx="8" cy="12" r="4" fill="rgba(167,139,250,0.4)"/><circle cx="16" cy="6" r="4" fill="rgba(167,139,250,0.4)"/><circle cx="24" cy="12" r="4" fill="rgba(167,139,250,0.4)"/></svg>';
    paw.style.cssText = 'position:fixed;left:' + (e.clientX - 12) + 'px;top:' + (e.clientY - 12) + 'px;pointer-events:none;z-index:99999;transition:all 0.6s ease-out;transform:scale(0.5);opacity:1;';
    document.body.appendChild(paw);
    requestAnimationFrame(function () {
      paw.style.transform = 'scale(1.3)';
      paw.style.opacity = '0';
    });
    setTimeout(function () { paw.remove(); }, 600);
  });

})();
