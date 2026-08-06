/* ops_dashboard/static/app.js — Mobile card toggle + sort helpers */
(function () {
  "use strict";

  /* ── Mobile table ↔ card toggle ── */
  document.addEventListener("DOMContentLoaded", function () {
    var btns = document.querySelectorAll(".view-toggle");
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var wrap = btn.closest(".view-section");
        if (!wrap) return;
        var tv = wrap.querySelector(".table-view");
        var cv = wrap.querySelector(".card-view");
        if (!tv || !cv) return;
        var showingCards = cv.style.display !== "none";
        if (showingCards) {
          tv.style.display = "";
          cv.style.display = "none";
          btn.textContent = "Cards";
        } else {
          tv.style.display = "none";
          cv.style.display = "block";
          btn.textContent = "Table";
        }
      });
    });
  });

  /* ── Simple table sort (click th) ── */
  document.addEventListener("click", function (e) {
    var th = e.target.closest("th[data-sort]");
    if (!th) return;
    var table = th.closest("table");
    if (!table) return;
    var idx = Array.from(th.parentNode.children).indexOf(th);
    var tbody = table.querySelector("tbody") || table;
    var rows = Array.from(tbody.querySelectorAll("tr")).filter(function (r) {
      return !r.querySelector("th");
    });
    var asc = th.getAttribute("data-sort") !== "asc";
    th.setAttribute("data-sort", asc ? "asc" : "desc");
    rows.sort(function (a, b) {
      var av = (a.children[idx] || {}).textContent || "";
      var bv = (b.children[idx] || {}).textContent || "";
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
    rows.forEach(function (r) { tbody.appendChild(r); });
  });
})();
