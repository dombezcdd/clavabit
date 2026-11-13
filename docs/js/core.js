"use strict";
/* Общее: настройки, Telegram, помощники, состояние экрана */
/* ===== настройки ===== */
const BOT = new URLSearchParams(location.search).get("bot") || "clavekGift_bot";   // имя бота без @
const FAST = Number(new URLSearchParams(location.search).get("fast")) || 1;         // только для тестов
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { try { tg.ready(); tg.expand(); tg.disableVerticalSwipes && tg.disableVerticalSwipes(); tg.setHeaderColor && tg.setHeaderColor("#1b1530"); tg.setBackgroundColor && tg.setBackgroundColor("#1b1530"); } catch (e) {} }
const q = new URLSearchParams(location.search);
const sid = ((tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) || q.get("sid") || "dem00000000").replace(/[^a-z0-9]/gi, "");
const demo = sid.startsWith("dem");
const $ = id => document.getElementById(id);
const stage = $("stage"), bar = $("barFill"), pill = $("pill"), hint = $("hint");
const rnd = (a, b) => a + Math.random() * (b - a), irnd = (a, b) => Math.floor(rnd(a, b + 1));
const shuffle = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = irnd(0, i); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const pick = a => a[irnd(0, a.length - 1)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const haptic = t => { try { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(t); } catch (e) {} };

let timerHandle = 0, cleanup = null, finished = false;

function setTime(frac) { bar.style.transform = "scaleX(" + clamp(frac, 0, 1) + ")"; }
function reset() { if (cleanup) { try { cleanup(); } catch (e) {} } cleanup = null; stage.innerHTML = ""; hint.textContent = ""; setTime(1); finished = false; pill.textContent = "0"; }
function el(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
const wait = ms => new Promise(r => setTimeout(r, ms / FAST));
function setTitle(title, sub) { $("jobTitle").firstChild.nodeValue = title; $("jobSub").textContent = sub || ""; }
function showBar(v) { $("bar").classList.toggle("hide", !v); }
let onBack = null;
function setBack(fn) { onBack = fn; $("back").classList.toggle("show", !!fn); }
$("back").onclick = () => { if (onBack) onBack(); };
