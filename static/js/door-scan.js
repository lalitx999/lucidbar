/*
 * Door check-in helper for staff.
 * - A handheld scanner types the card code into the input and presses Enter.
 * - On browsers with the BarcodeDetector API (Chrome on Android, for example)
 *   a "Scan with camera" button reads the QR and submits the form.
 * No third-party libraries are loaded.
 */
(function () {
  "use strict";
  var form = document.getElementById("door-form");
  if (!form) return;
  var input = document.getElementById("door-token");
  var button = document.getElementById("door-camera-btn");
  var video = document.getElementById("door-video");

  if (!("BarcodeDetector" in window) || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

  var detector;
  try {
    detector = new window.BarcodeDetector({ formats: ["qr_code"] });
  } catch (e) {
    return;
  }
  button.classList.remove("d-none");

  var stream = null;
  var submitted = false;

  function stop() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
    video.classList.add("d-none");
  }

  function scan() {
    if (!stream || submitted) return;
    detector.detect(video).then(function (codes) {
      var hit = codes.find(function (c) { return c.rawValue && c.rawValue.indexOf("LUCID1.") === 0; });
      if (hit) {
        submitted = true;
        input.value = hit.rawValue;
        stop();
        form.submit();
        return;
      }
      setTimeout(scan, 250);
    }).catch(function () { setTimeout(scan, 500); });
  }

  button.addEventListener("click", function () {
    if (stream) { stop(); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then(function (s) {
        stream = s;
        video.srcObject = s;
        video.classList.remove("d-none");
        return video.play();
      })
      .then(scan)
      .catch(function () { stop(); });
  });

  window.addEventListener("pagehide", stop);
})();
