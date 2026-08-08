/* ops_dashboard/static/app.js — Refresh buttons + mobile card toggle + sort helpers */
(function () {
  "use strict";

  /* ── Refresh buttons ── */
  document.addEventListener("DOMContentLoaded", function () {

    /* 마스터 재검사 버튼 (index.html) */
    var masterBtn = document.getElementById("btn-run-all-checks");
    if (masterBtn) {
      masterBtn.addEventListener("click", function () {
        if (masterBtn.disabled) return;
        masterBtn.disabled = true;
        masterBtn.textContent = "검사 중…";
        fetch("/api/run-checks", {
          method: "POST",
          credentials: "same-origin",
        })
          .then(function (r) { return r.json(); })
          .then(function () {
            window.location.reload();
          })
          .catch(function () {
            masterBtn.disabled = false;
            masterBtn.textContent = "전체 재검사 실행";
          });
      });
    }

    /* 개별 블로그 재검사 버튼 (blog.html) */
    var blogRefreshBtn = document.getElementById("btn-refresh-blog");
    if (blogRefreshBtn) {
      blogRefreshBtn.addEventListener("click", function () {
        if (blogRefreshBtn.disabled) return;
        blogRefreshBtn.disabled = true;
        blogRefreshBtn.textContent = "검사 중…";
        var blogId = blogRefreshBtn.getAttribute("data-blog-id");
        fetch("/api/run-checks?blog_id=" + encodeURIComponent(blogId), {
          method: "POST",
          credentials: "same-origin",
        })
          .then(function (r) { return r.json(); })
          .then(function () {
            window.location.reload();
          })
          .catch(function () {
            blogRefreshBtn.disabled = false;
            blogRefreshBtn.textContent = "이 블로그 재검사";
          });
      });
    }

    /* 정비 체크리스트 재실행 버튼 (blog.html) */
    var maintBtn = document.getElementById("btn-refresh-maintenance");
    if (maintBtn) {
      maintBtn.addEventListener("click", function () {
        if (maintBtn.disabled) return;
        maintBtn.disabled = true;
        maintBtn.textContent = "실행 중…";
        var blogId = maintBtn.getAttribute("data-blog-id");
        fetch("/api/maintenance/checklist", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ blog_id: blogId }),
        })
          .then(function (r) { return r.json(); })
          .then(function () {
            window.location.reload();
          })
          .catch(function () {
            maintBtn.disabled = false;
            maintBtn.textContent = "정비 체크리스트 재실행";
          });
      });
    }

  }); /* end refresh buttons */

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
