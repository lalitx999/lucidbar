/*
  Prize wheel animation. The server picks the prize; this script only spins
  the wheel to the segment it returns. Without JavaScript the form posts
  normally and the page shows the result.
*/
(function () {
  "use strict";

  var root = document.getElementById("reveal");
  var rotor = document.getElementById("wheel-rotor");
  var svg = document.getElementById("wheel");
  if (!root || !rotor || !svg) return;

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Rest on the won segment when the page is reloaded after a spin.
  var rest = parseFloat(svg.getAttribute("data-rest") || "0");
  if (rest) rotor.style.transform = "rotate(" + rest + "deg)";

  var form = document.getElementById("spin-form");
  if (!form) return;
  var button = document.getElementById("spin-button");
  var result = document.getElementById("spin-result");

  function showResult(data) {
    ["prize", "description", "value", "claim_code"].forEach(function (key) {
      var el = result.querySelector('[data-field="' + key + '"]');
      if (el) el.textContent = data[key] || "";
    });
    result.classList.remove("d-none");
    form.remove();
    result.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    button.disabled = true;

    fetch(root.getAttribute("data-spin-url"), {
      method: "POST",
      body: new FormData(form), // carries the CSRF token
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data.ok) {
          window.alert(data.message || root.getAttribute("data-error-text"));
          button.disabled = false;
          return;
        }
        if (reduceMotion) {
          rotor.style.transform = "rotate(" + data.rotation + "deg)";
          showResult(data);
          return;
        }
        rotor.classList.add("is-spinning");
        rotor.style.transform = "rotate(" + data.rotation + "deg)";
        rotor.addEventListener("transitionend", function done() {
          rotor.removeEventListener("transitionend", done);
          rotor.classList.remove("is-spinning");
          showResult(data);
        });
      })
      .catch(function () {
        window.alert(root.getAttribute("data-error-text"));
        button.disabled = false;
      });
  });
})();
