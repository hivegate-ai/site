// HiveGate site behaviour. Everything degrades to a readable static page without JS.
(function () {
  "use strict";

  // Tabs (WAI-ARIA tabs pattern: click, arrow keys, Home/End).
  document.querySelectorAll("[data-tabs]").forEach(function (root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll('[role="tab"]'));
    function select(tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(t.getAttribute("aria-controls"));
        if (panel) panel.hidden = !on;
      });
      if (focus) tab.focus();
    }
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { select(tab, false); });
      tab.addEventListener("keydown", function (e) {
        var next = null;
        if (e.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
        else if (e.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
        else if (e.key === "Home") next = tabs[0];
        else if (e.key === "End") next = tabs[tabs.length - 1];
        if (next) { e.preventDefault(); select(next, true); }
      });
    });
  });

  // Play the hive sequence once, when the diagram is on screen.
  var hive = document.querySelector(".hive");
  if (hive && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) { hive.classList.add("is-playing"); io.disconnect(); }
    }, { threshold: 0.4 });
    io.observe(hive);
  }

  // Live GitHub star count, cached for the session. Hidden if the API is unavailable.
  var starEls = document.querySelectorAll("[data-stars]");
  function showStars(n) {
    if (typeof n !== "number") return;
    var text = n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n);
    starEls.forEach(function (el) {
      el.textContent = text;
      el.hidden = false;
      var link = el.closest("a");
      if (link) link.setAttribute("aria-label", "HiveGate on GitHub, " + n + (n === 1 ? " star" : " stars"));
    });
  }
  if (starEls.length) {
    var cached = null;
    try { cached = JSON.parse(sessionStorage.getItem("hg-stars") || "null"); } catch (e) { cached = null; }
    if (cached && Date.now() - cached.t < 3600e3) {
      showStars(cached.n);
    } else if (window.fetch) {
      fetch("https://api.github.com/repos/hivegate-ai/hivegate", { headers: { Accept: "application/vnd.github+json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (!d) return;
          showStars(d.stargazers_count);
          try { sessionStorage.setItem("hg-stars", JSON.stringify({ n: d.stargazers_count, t: Date.now() })); } catch (e) { /* storage unavailable */ }
        })
        .catch(function () { /* leave the plain GitHub link */ });
    }
  }

  // Let wide Markdown tables scroll inside their own box instead of the page.
  document.querySelectorAll(".prose table").forEach(function (table) {
    if (table.parentNode.classList.contains("table-wrap")) return;
    var wrap = document.createElement("div");
    wrap.className = "table-wrap";
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
  });

  // Copy buttons on code blocks.
  if (navigator.clipboard) {
    document.querySelectorAll("pre").forEach(function (pre) {
      var wrap = document.createElement("div");
      wrap.className = "code-block";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "copy-btn";
      btn.textContent = "Copy";
      btn.addEventListener("click", function () {
        navigator.clipboard.writeText(pre.innerText.replace(/\n$/, "")).then(function () {
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = "Copy"; }, 1500);
        }, function () {
          btn.textContent = "Copy failed";
        });
      });
      wrap.appendChild(btn);
    });
  }
})();
