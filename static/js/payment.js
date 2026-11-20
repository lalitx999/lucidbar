/*
  Pay screen behaviour:
  - copy-to-clipboard buttons ([data-copy])
  - while a slip is being checked, poll the status endpoint and reload the
    page when the state changes (approved, review, or back to upload)
*/
(function () {
  "use strict";

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = button.getAttribute("data-copy");
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(value).then(function () {
        var label = button.querySelector("span");
        if (!label) return;
        var original = label.textContent;
        label.textContent = button.getAttribute("data-copied-label") || original;
        setTimeout(function () { label.textContent = original; }, 1500);
      });
    });
  });

  var root = document.getElementById("payment");
  if (!root) return;
  var status = root.getAttribute("data-status");
  var url = root.getAttribute("data-status-url");
  if (status !== "verifying" && status !== "review") return;

  var delay = status === "verifying" ? 3000 : 15000;
  var maxDelay = 30000;
  var message = document.getElementById("payment-message");

  function poll() {
    fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (!data) return schedule();
        if (data.status !== status) {
          window.location.reload();
          return;
        }
        if (message && data.message) message.textContent = data.message;
        schedule();
      })
      .catch(schedule);
  }

  function schedule() {
    delay = Math.min(Math.round(delay * 1.3), maxDelay);
    setTimeout(poll, delay);
  }

  setTimeout(poll, delay);
})();
