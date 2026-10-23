// Progressive enhancements; every page works without JavaScript.
(function () {
  "use strict";

  // ---- sortable tables -----------------------------------------------------
  function cellValue(cell, type) {
    var raw = cell.getAttribute("data-sort");
    var text = raw !== null ? raw : cell.textContent.trim();
    if (type === "num") {
      var n = parseFloat(text.replace(/\./g, "").replace(",", "."));
      return isNaN(n) ? -Infinity : n;
    }
    if (type === "date") {   // dd.mm.yyyy[, hh:mm]
      var m = text.match(/^(\d{2})\.(\d{2})\.(\d{4})(?:, (\d{2}):(\d{2}))?/);
      return m ? m[3] + m[2] + m[1] + (m[4] || "00") + (m[5] || "00") : "";
    }
    return text.toLocaleLowerCase("de");
  }

  document.querySelectorAll("table.sortable").forEach(function (table) {
    var headers = table.tHead ? table.tHead.rows[0].cells : [];
    Array.prototype.forEach.call(headers, function (th, index) {
      th.addEventListener("click", function () {
        var type = th.getAttribute("data-type") || "text";
        var asc = th.getAttribute("aria-sort") !== "ascending";
        Array.prototype.forEach.call(headers, function (h) { h.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var body = table.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var x = cellValue(a.cells[index], type), y = cellValue(b.cells[index], type);
          var r = x < y ? -1 : x > y ? 1 : 0;
          return asc ? r : -r;
        });
        rows.forEach(function (row) { body.appendChild(row); });
      });
    });
  });

  // ---- name suggestions ------------------------------------------------------
  document.querySelectorAll("input[list]").forEach(function (input) {
    var list = document.getElementById(input.getAttribute("list"));
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { return; }
      var whereFrom = input.getAttribute("data-suggest-from");
      var where = whereFrom ? document.getElementById(whereFrom).value : (input.getAttribute("data-suggest") || "all");
      timer = setTimeout(function () {
        fetch("/api/suggest?where=" + encodeURIComponent(where) + "&q=" + encodeURIComponent(q))
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (names) {
            list.innerHTML = "";
            names.forEach(function (name) {
              var option = document.createElement("option");
              option.value = name;
              list.appendChild(option);
            });
          })
          .catch(function () {});
      }, 200);
    });
  });

  // ---- relation form helpers --------------------------------------------------
  function utcNow() {
    return new Date().toISOString().slice(0, 19).replace("T", " ");
  }
  document.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-now], button[data-clear], button[data-set]");
    if (!button) { return; }
    var target = document.getElementById(button.getAttribute("data-now") ||
      button.getAttribute("data-clear") || button.getAttribute("data-set"));
    if (!target) { return; }
    if (button.hasAttribute("data-now")) { target.value = utcNow(); }
    else if (button.hasAttribute("data-clear")) { target.value = ""; }
    else { target.value = button.getAttribute("data-value"); target.scrollIntoView({block: "center"}); target.focus(); }
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) { event.preventDefault(); }
    });
  });

  // ---- highlight all rows of the same mentor / mentee ---------------------------
  function hoverGroup(selector, attr, container) {
    container.addEventListener("mouseover", function (event) {
      var el = event.target.closest(selector);
      if (!el) { return; }
      var id = el.getAttribute(attr);
      container.querySelectorAll(".hover-match").forEach(function (n) { n.classList.remove("hover-match"); });
      container.querySelectorAll(selector + "[" + attr + '="' + id + '"]').forEach(function (n) {
        (n.closest("tr") || n).classList.add("hover-match");
      });
    });
    container.addEventListener("mouseleave", function () {
      container.querySelectorAll(".hover-match").forEach(function (n) { n.classList.remove("hover-match"); });
    });
  }
  document.querySelectorAll("table[data-highlight=mentor]").forEach(function (t) { hoverGroup("td[data-mentor]", "data-mentor", t); });
  document.querySelectorAll("ul.rc").forEach(function (ul) { hoverGroup("li[data-actor]", "data-actor", ul); });
})();
