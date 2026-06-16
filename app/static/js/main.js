// Juana María — site interactions: nav, scroll reveal, gallery lightbox,
// and click-to-load video facades. Vanilla JS, no dependencies.
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------- Nav */
  var nav = document.getElementById("nav");
  var toggle = document.getElementById("navToggle");
  var links = document.getElementById("navLinks");

  function onScroll() {
    if (nav) nav.classList.toggle("is-scrolled", window.scrollY > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  function closeMenu() {
    if (!links || !toggle) return;
    links.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Abrir menú");
    document.body.style.overflow = "";
  }

  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
      document.body.style.overflow = open ? "hidden" : "";
    });
    links.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", closeMenu);
    });
    // Escape closes the mobile menu and returns focus to the toggle.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && links.classList.contains("is-open")) {
        closeMenu();
        toggle.focus();
      }
    });
  }

  /* ------------------------------------------------------- Scroll reveal */
  var reveals = document.querySelectorAll(".reveal");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    reveals.forEach(function (el) { el.classList.add("is-in"); });
  } else {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.08 }
    );
    reveals.forEach(function (el) {
      if (!el.classList.contains("is-in")) io.observe(el);
    });
  }

  /* --------------------------------------------------------- Scroll-spy */
  // Highlight the nav link for the section currently in view.
  var navAnchors = Array.prototype.slice.call(
    document.querySelectorAll('.nav-links a[href^="#"]')
  );
  var sectionFor = {};
  navAnchors.forEach(function (a) {
    var id = a.getAttribute("href").slice(1);
    var sec = document.getElementById(id);
    if (sec) sectionFor[id] = a;
  });
  if (Object.keys(sectionFor).length && "IntersectionObserver" in window) {
    var spy = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          navAnchors.forEach(function (a) { a.classList.remove("is-active"); });
          var a = sectionFor[entry.target.id];
          if (a) a.classList.add("is-active");
        });
      },
      // A thin band across the viewport's vertical middle.
      { rootMargin: "-45% 0px -50% 0px", threshold: 0 }
    );
    Object.keys(sectionFor).forEach(function (id) {
      spy.observe(document.getElementById(id));
    });
  }

  /* ----------------------------------------------------- Count-up numbers */
  var counters = document.querySelectorAll("[data-count]");
  if (counters.length && !reduceMotion && "IntersectionObserver" in window) {
    var countIO = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var el = entry.target;
          countIO.unobserve(el);
          var target = parseInt(el.getAttribute("data-count"), 10) || 0;
          var start = null;
          var dur = 1400;
          function tick(ts) {
            if (start === null) start = ts;
            var t = Math.min((ts - start) / dur, 1);
            // easeOutCubic for a settle at the end
            var eased = 1 - Math.pow(1 - t, 3);
            el.textContent = Math.round(eased * target);
            if (t < 1) requestAnimationFrame(tick);
            else el.textContent = target;
          }
          requestAnimationFrame(tick);
        });
      },
      { threshold: 0.6 }
    );
    counters.forEach(function (el) { countIO.observe(el); });
  }

  /* ------------------------------------------------------------ Lightbox */
  var gallery = document.getElementById("gallery");
  var lb = document.getElementById("lightbox");
  if (gallery && lb) {
    var lbImg = document.getElementById("lbImg");
    var lbCaption = document.getElementById("lbCaption");
    var lbCount = document.getElementById("lbCount");
    var items = Array.prototype.slice.call(gallery.querySelectorAll(".gallery__item"));
    // Everything on the page except the dialog itself — inerted while open so
    // focus/AT can't reach the nav, content or footer behind the overlay.
    var backdrop = Array.prototype.filter.call(document.body.children, function (el) {
      return el !== lb && el.tagName !== "SCRIPT";
    });
    var index = 0;
    var lastFocused = null;
    // The dialog's own focusable controls, in tab order.
    var focusables = ["lbClose", "lbPrev", "lbNext"].map(function (id) {
      return document.getElementById(id);
    });

    function render() {
      var item = items[index];
      lbImg.src = item.getAttribute("data-full");
      lbImg.alt = item.getAttribute("data-caption") || "";
      lbCaption.textContent = item.getAttribute("data-caption") || "";
      if (lbCount) lbCount.textContent = index + 1 + " / " + items.length;
      // Warm the neighbours so prev/next swap instantly (no flash).
      [(index + 1) % items.length, (index - 1 + items.length) % items.length].forEach(
        function (i) {
          var url = items[i].getAttribute("data-full");
          if (url) {
            var img = new Image();
            img.src = url;
          }
        }
      );
    }

    function open(i) {
      index = i;
      lastFocused = document.activeElement;
      render();
      lb.classList.add("is-open");
      document.body.style.overflow = "hidden";
      // Make the rest of the page inert so AT/keyboard stay in the dialog.
      backdrop.forEach(function (el) { el.setAttribute("inert", ""); });
      focusables[0].focus();
    }

    function close() {
      lb.classList.remove("is-open");
      document.body.style.overflow = "";
      backdrop.forEach(function (el) { el.removeAttribute("inert"); });
      lbImg.src = "";
      if (lastFocused) lastFocused.focus();
    }

    function step(dir) {
      index = (index + dir + items.length) % items.length;
      render();
    }

    // Trap Tab/Shift+Tab within the dialog's controls.
    function trap(e) {
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    items.forEach(function (item, i) {
      item.addEventListener("click", function () { open(i); });
    });
    focusables[0].addEventListener("click", close);
    focusables[1].addEventListener("click", function () { step(-1); });
    focusables[2].addEventListener("click", function () { step(1); });
    lb.addEventListener("click", function (e) {
      if (e.target === lb) close();
    });
    document.addEventListener("keydown", function (e) {
      if (!lb.classList.contains("is-open")) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "Tab") trap(e);
    });
  }

  /* ----------------------------------------- Lazy media near the viewport */
  // Defer the heavy hero/heritage <video> and the facade poster images until
  // their section approaches, so they don't compete with above-the-fold load.
  function whenNear(el, cb, margin) {
    if (!("IntersectionObserver" in window)) { cb(); return; }
    var obs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { obs.unobserve(entry.target); cb(); }
        });
      },
      { rootMargin: margin || "600px 0px" }
    );
    obs.observe(el);
  }

  document.querySelectorAll("video[data-lazy-video]").forEach(function (video) {
    whenNear(video, function () {
      var src = video.getAttribute("data-src");
      if (!src) return;
      var source = document.createElement("source");
      source.src = src;
      source.type = "video/mp4";
      video.appendChild(source);
      video.load();
      if (!reduceMotion) {
        var p = video.play();
        if (p && p.catch) p.catch(function () {}); // ignore autoplay rejections
      }
    });
  });

  document.querySelectorAll(".video-facade[data-bg]").forEach(function (facade) {
    whenNear(facade, function () {
      facade.style.backgroundImage = "url('" + facade.getAttribute("data-bg") + "')";
    });
  });

  /* ------------------------------------------------ Video facades (click) */
  document.querySelectorAll(".video-facade").forEach(function (facade) {
    facade.addEventListener("click", function () {
      var src = facade.getAttribute("data-embed");
      var title = facade.getAttribute("data-title") || "Video";
      if (!src) return;
      var iframe = document.createElement("iframe");
      iframe.setAttribute("src", src);
      iframe.setAttribute("title", title);
      // allow="fullscreen" already grants fullscreen; the legacy allowfullscreen
      // attribute is redundant and triggers a console warning, so it's omitted.
      iframe.setAttribute("allow", "autoplay; fullscreen; picture-in-picture");
      facade.replaceWith(iframe);
    });
  });
})();
