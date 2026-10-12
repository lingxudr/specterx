"""Hardened stealth JS. Injected via Page.addScriptToEvaluateOnNewDocument
so it applies before any page script runs, on every navigation, and inside
iframes (including the Turnstile challenge iframe itself).

Fixes vs the original specter stealth:
  - platform typo fixed: "Linux armv81" -> "Linux armv8l"
  - navigator.webdriver removed (not just undefined-valued)
  - toString of patched functions preserved (no "function () { [native code] }" leaks)
  - iframe contentWindow inherits spoofs automatically via the CDP mechanism
  - no console.log beacon
"""
from __future__ import annotations

import json


def build(fp: dict) -> str:
    cfg = json.dumps({
        "platform": fp["platform"],
        "hardwareConcurrency": fp["hardware_concurrency"],
        "deviceMemory": fp["device_memory"],
        "maxTouchPoints": fp["max_touch_points"],
        "languages": fp["languages"],
        "screenW": fp["screen_width"],
        "screenH": fp["screen_height"],
        "availW": fp["avail_width"],
        "availH": fp["avail_height"],
        "colorDepth": fp["color_depth"],
        "pixelDepth": fp["pixel_depth"],
        "dpr": fp["device_pixel_ratio"],
        "webglVendor": fp["webgl_vendor"],
        "webglRenderer": fp["webgl_renderer"],
        "tzOffset": fp["tz_offset_min"],
        "mobile": fp["mobile"],
        "canvasSeed": fp["canvas_seed"],
    })
    return r"""
(() => {
  const C = __CFG__;
  const nativeToString = Function.prototype.toString;
  const mask = (fn) => {
    const s = nativeToString.call(fn);
    Object.defineProperty(fn, "toString", { value: () => s, configurable: true });
    return fn;
  };
  let st = C.canvasSeed >>> 0;
  const lcg = () => (st = (st * 1664525 + 1013904223) >>> 0);

  // ---- canvas noise (seeded, deterministic per host) ----
  const _td = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = mask(function (...a) {
    try {
      const ctx = this.getContext("2d");
      if (ctx) {
        const img = ctx.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < img.data.length; i += 4) {
          if (lcg() % 220 === 0) {
            img.data[i] = (img.data[i] + 1) & 0xff;
            img.data[i + 1] = (img.data[i + 1] + 1) & 0xff;
            img.data[i + 2] = (img.data[i + 2] + 1) & 0xff;
          }
        }
        ctx.putImageData(img, 0, 0);
      }
    } catch (e) {}
    return _td.apply(this, a);
  });

  // ---- WebGL vendor/renderer ----
  const _p1 = WebGLRenderingContext.prototype.getParameter;
  const _p2 = typeof WebGL2RenderingContext !== "undefined"
    ? WebGL2RenderingContext.prototype.getParameter : null;
  const spoofGL = function (p) {
    if (p === 37445) return C.webglVendor;
    if (p === 37446) return C.webglRenderer;
    return (_p1 === this.getParameter ? _p1 : _p1).call(this, p);
  };
  WebGLRenderingContext.prototype.getParameter = mask(function (p) {
    if (p === 37445) return C.webglVendor;
    if (p === 37446) return C.webglRenderer;
    return _p1.call(this, p);
  });
  if (_p2) WebGL2RenderingContext.prototype.getParameter = mask(function (p) {
    if (p === 37445) return C.webglVendor;
    if (p === 37446) return C.webglRenderer;
    return _p2.call(this, p);
  });
  // hide debug renderer info extension
  try {
    const _ge = WebGLRenderingContext.prototype.getExtension;
    WebGLRenderingContext.prototype.getExtension = mask(function (n) {
      if (n === "WEBGL_debug_renderer_info") return null;
      return _ge.call(this, n);
    });
  } catch (e) {}

  // ---- navigator ----
  const nav = navigator;
  const def = (obj, prop, val) => {
    try { Object.defineProperty(obj, prop, { get: mask(() => val), configurable: true }); }
    catch (e) {}
  };
  def(nav, "platform", C.platform);
  def(nav, "hardwareConcurrency", C.hardwareConcurrency);
  def(nav, "deviceMemory", C.deviceMemory);
  def(nav, "maxTouchPoints", C.maxTouchPoints);
  def(nav, "languages", C.languages.slice());
  def(nav, "language", C.languages[0]);
  def(nav, "doNotTrack", null);
  // webdriver: real browsers expose it as `false`; automated Chrome as `true`.
  // Spoof it as a native-looking getter returning false.
  try {
    try { delete Object.getPrototypeOf(nav).webdriver; } catch (e) {}
    try { delete nav.webdriver; } catch (e) {}
    Object.defineProperty(nav, "webdriver",
      { get: mask(() => false), configurable: true });
  } catch (e) {}
  // plugins / mimeTypes consistent with profile
  const emptyList = () => {
    const a = [];
    a.item = mask(() => null); a.namedItem = mask(() => null); a.refresh = mask(() => {});
    return a;
  };
  def(nav, "plugins", emptyList());
  def(nav, "mimeTypes", emptyList());
  def(nav, "connection", { effectiveType: "4g", rtt: 60, downlink: 8, saveData: false });

  // ---- screen ----
  const scr = screen;
  const sdef = (p, v) => { try { Object.defineProperty(scr, p, { get: mask(() => v), configurable: true }); } catch (e) {} };
  sdef("width", C.screenW); sdef("height", C.screenH);
  sdef("availWidth", C.availW); sdef("availHeight", C.availH);
  sdef("colorDepth", C.colorDepth); sdef("pixelDepth", C.pixelDepth);
  try {
    Object.defineProperty(window, "devicePixelRatio", { get: mask(() => C.dpr), configurable: true });
  } catch (e) {}

  // ---- touch ----
  if (C.mobile) {
    try { Object.defineProperty(window, "ontouchstart", { get: mask(() => null), configurable: true }); } catch (e) {}
    try { navigator.maxTouchPoints; } catch (e) {}
  }

  // ---- timezone ----
  try {
    const _off = Date.prototype.getTimezoneOffset;
    Date.prototype.getTimezoneOffset = mask(function () { return C.tzOffset; });
  } catch (e) {}

  // ---- chrome.runtime (headless has none; real Chrome has it) ----
  try {
    window.chrome = window.chrome || {};
    if (!window.chrome.runtime) window.chrome.runtime = {};
  } catch (e) {}

  // ---- permissions ----
  try {
    if (nav.permissions && nav.permissions.query) {
      const _q = nav.permissions.query.bind(nav.permissions);
      nav.permissions.query = mask((p) => {
        if (p && p.name === "notifications")
          return Promise.resolve({ state: "denied", name: "notifications" });
        return _q(p);
      });
    }
  } catch (e) {}

  // ---- history length (fresh profile looks odd with length 1 everywhere) ----
  // (left untouched: spoofing this breaks navigation)

  window.__specterx_fp = true;
})();
""".replace("__CFG__", cfg)
