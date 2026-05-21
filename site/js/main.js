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

  /* ---------- EASTER EGG ---------- */
  var heroAvatar = document.getElementById('hero-avatar');
  var easterToast = document.getElementById('easter-toast');
  var clickCount = 0;
  var clickTimer = null;
  var CLICK_THRESHOLD = 7;

  if (heroAvatar && easterToast) {
    heroAvatar.addEventListener('click', function (e) {
      e.stopPropagation();
      clickCount++;
      clearTimeout(clickTimer);
      clickTimer = setTimeout(function () { clickCount = 0; }, 2000);

      if (clickCount >= CLICK_THRESHOLD) {
        clickCount = 0;
        easterToast.classList.add('show');
        setTimeout(function () {
          easterToast.classList.remove('show');
        }, 2000);
      }
    });
  }

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

})();
