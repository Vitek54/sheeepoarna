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

  /* ---------- PARALLAX ON HERO ---------- */
  var floatingLogos = document.querySelector('.hero-floating-logos');
  var heroSection = document.querySelector('.hero-section');

  window.addEventListener('scroll', function () {
    var scrollY = window.scrollY;
    if (heroSection && scrollY < window.innerHeight * 1.5) {
      var rate = scrollY * 0.3;
      if (floatingLogos) {
        floatingLogos.style.transform = 'translateY(' + (rate * 0.5) + 'px)';
      }
      var heroInner = document.querySelector('.hero-inner');
      if (heroInner) {
        heroInner.style.transform = 'translateY(' + (rate * 0.15) + 'px)';
        heroInner.style.opacity = Math.max(0, 1 - scrollY / (window.innerHeight * 0.8));
      }
    }
  });

  /* ---------- PARTICLES (Digital Network) ---------- */
  var canvas = document.getElementById('particles-canvas');
  if (canvas) {
    var ctx = canvas.getContext('2d');
    var particles = [];
    var PARTICLE_COUNT = 50;
    var CONNECT_DIST = 120;

    function resizeCanvas() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    function Particle() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.r = Math.random() * 1.5 + 0.5;
    }

    for (var i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(new Particle());
    }

    function drawParticles() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(167, 139, 250, 0.5)';
        ctx.fill();

        for (var j = i + 1; j < particles.length; j++) {
          var p2 = particles[j];
          var dx = p.x - p2.x;
          var dy = p.y - p2.y;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECT_DIST) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = 'rgba(167, 139, 250, ' + (0.15 * (1 - dist / CONNECT_DIST)) + ')';
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(drawParticles);
    }
    drawParticles();
  }

})();
