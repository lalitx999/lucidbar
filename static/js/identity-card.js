/*
 * Keeps the QR identity card fresh. Each card is signed with a timestamp and
 * expires on the server after a few minutes, so reload it every minute and
 * whenever the page comes back into view.
 */
(function () {
  "use strict";
  var images = document.querySelectorAll("img[data-card-qr]");
  if (!images.length) return;
  var base = images[0].getAttribute("src");
  var seconds = parseInt(images[0].getAttribute("data-refresh-seconds"), 10) || 60;

  function refresh() {
    var url = base + "?t=" + Date.now();
    images.forEach(function (img) { img.src = url; });
  }

  setInterval(function () {
    if (document.visibilityState === "visible") refresh();
  }, seconds * 1000);

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") refresh();
  });
})();
