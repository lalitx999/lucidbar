/*
 * PWA helpers, loaded on every page:
 * 1. Register the service worker (served from /sw.js so it covers the site).
 * 2. Offer installation: Chrome/Android `beforeinstallprompt`, or short
 *    instructions on iOS Safari. A dismissal is remembered for 30 days.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var swUrl = script && script.getAttribute("data-sw");
  if ("serviceWorker" in navigator && swUrl) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register(swUrl, { scope: "/" }).catch(function () {});
    });
  }

  var banner = document.getElementById("install-banner");
  if (!banner) return;

  var DISMISS_KEY = "lucid.install.dismissedAt";
  var THIRTY_DAYS = 30 * 24 * 60 * 60 * 1000;

  function storageGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function storageSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }

  var standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  var dismissedAt = parseInt(storageGet(DISMISS_KEY) || "0", 10);
  if (standalone || (dismissedAt && Date.now() - dismissedAt < THIRTY_DAYS)) return;

  var acceptBtn = document.getElementById("install-accept");
  var dismissBtn = document.getElementById("install-dismiss");
  var deferred = null;

  function show(mode) {
    banner.querySelectorAll("[data-install-text]").forEach(function (el) {
      el.classList.toggle("d-none", el.getAttribute("data-install-text") !== mode);
    });
    acceptBtn.classList.toggle("d-none", mode !== "prompt");
    banner.classList.remove("d-none");
  }

  function hide() { banner.classList.add("d-none"); }

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferred = event;
    show("prompt");
  });

  window.addEventListener("appinstalled", hide);

  acceptBtn.addEventListener("click", function () {
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.finally(function () { deferred = null; hide(); });
  });

  dismissBtn.addEventListener("click", function () {
    storageSet(DISMISS_KEY, String(Date.now()));
    hide();
  });

  var ua = window.navigator.userAgent;
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (ua.indexOf("Macintosh") > -1 && navigator.maxTouchPoints > 1);
  var isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
  if (isIOS && isSafari) show("ios");
})();
