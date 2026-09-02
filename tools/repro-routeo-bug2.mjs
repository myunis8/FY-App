// Harness para reproducir el Bug 2 de Routeo (la línea de color del circuito
// dentro del caño mal ubicada en obras nuevas). Levanta app.server, abre
// canaliza.html en Edge headless, traza un tramo con clicks reales sobre el
// canvas, e instrumenta el drawing para ver con qué puntos se dibuja la
// envoltura gris del caño vs la línea de color.
//
//   node tools/repro-routeo-bug2.mjs <obraId>
//
// <obraId> debe ser una obra que ya tenga plano + escala + circuitos (para
// poder trazar un tramo de un circuito). Ideal: una obra recién abierta en
// Routeo, sin `canalizacion.runs` guardados todavía.
//
// Requiere: npm install (puppeteer-core) y Microsoft Edge instalado.
import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const OBRA = process.argv[2];
if (!OBRA) { console.error("uso: node tools/repro-routeo-bug2.mjs <obraId>"); process.exit(2); }

const PORT = 8123;
const BASE = `http://127.0.0.1:${PORT}`;
const OUT = path.resolve("tools/_repro");
const EDGE = process.env.EDGE_PATH || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
fs.mkdirSync(OUT, { recursive: true });

const srv = spawn("python", ["-m", "app.main", String(PORT)], { cwd: path.resolve("fy-app"), stdio: "inherit" });
const stop = () => { try { srv.kill(); } catch {} };
process.on("exit", stop);

async function waitServer() {
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`${BASE}/api/obras`)).ok) return; } catch {}
    await sleep(300);
  }
  throw new Error("el servidor no levantó");
}

async function main() {
  await waitServer();
  const browser = await puppeteer.launch({
    executablePath: EDGE, headless: "new",
    args: ["--no-sandbox", "--window-size=1700,1050"],
    defaultViewport: { width: 1700, height: 1050 },
  });
  const page = await browser.newPage();
  page.on("pageerror", e => console.log("[pageerror]", e.message));

  await page.goto(`${BASE}/canaliza.html?obra=${OBRA}`, { waitUntil: "networkidle0" });
  await page.waitForFunction("window.canalizaObraCargada === true", { timeout: 25000 });
  await sleep(1500);
  await page.screenshot({ path: `${OUT}/1-abierta.png` });

  // elegir un circuito con >= 2 cajas propias, activarlo y la herramienta "run"
  const plan = await page.evaluate(() => {
    const S = window.canalizaDebug.S;
    let c, ns;
    for (const cand of S.circuits) {
      const list = S.nodes.filter(n => n.circuitId === cand.id);
      if (list.length >= 2) { c = cand; ns = list; break; }
    }
    if (!c) return { ok: false, why: "ningún circuito con 2 cajas" };
    S.tool = "run"; S.activeCircuit = c.id;
    const scr = w => ({ x: w.x * S.view.z + S.view.x, y: w.y * S.view.z + S.view.y });
    const cv = document.querySelector("#stage canvas") || document.querySelector("canvas");
    const r = cv.getBoundingClientRect();
    return {
      ok: true, circuit: { id: c.id, name: c.name, color: c.color, kind: c.kind },
      p1: scr(ns[0]), p2: scr(ns[1]), origin: { x: r.left, y: r.top }, view: { ...S.view },
    };
  });
  console.log("PLAN:", JSON.stringify(plan, null, 2));
  if (!plan.ok) { await browser.close(); stop(); return; }

  // instrumentar el canvas para registrar cada stroke y sus puntos
  await page.evaluate(() => {
    window.__diag = [];
    const g = (document.querySelector("#stage canvas") || document.querySelector("canvas")).getContext("2d");
    const oM = g.moveTo.bind(g), oL = g.lineTo.bind(g), oS = g.stroke.bind(g);
    let cur = [];
    g.moveTo = (x, y) => { cur = [{ x: +x.toFixed(1), y: +y.toFixed(1) }]; return oM(x, y); };
    g.lineTo = (x, y) => { cur.push({ x: +x.toFixed(1), y: +y.toFixed(1) }); return oL(x, y); };
    g.stroke = () => { window.__diag.push({ style: String(g.strokeStyle), w: +(+g.lineWidth).toFixed(2), pts: cur.slice(0, 6) }); return oS(); };
  });

  // clicks reales: primer nodo, mover, segundo nodo -> finishRun
  await page.mouse.click(plan.origin.x + plan.p1.x, plan.origin.y + plan.p1.y);
  await sleep(150);
  await page.mouse.move(plan.origin.x + plan.p2.x, plan.origin.y + plan.p2.y);
  await sleep(100);
  await page.mouse.click(plan.origin.x + plan.p2.x, plan.origin.y + plan.p2.y);
  await sleep(400);

  const diag = await page.evaluate((color) => {
    const S = window.canalizaDebug.S;
    const d = window.__diag || [];
    return {
      nRuns: S.runs.length,
      runPts: S.runs.map(r => ({ id: r.id, a: r.a, b: r.b, pts: r.pts })),
      colorStrokes: d.filter(x => x.style.toLowerCase() === color.toLowerCase()),
      view: { ...S.view },
    };
  }, plan.circuit.color);
  console.log("DIAG:", JSON.stringify(diag, null, 2));

  await page.screenshot({ path: `${OUT}/2-con-tramo.png` });
  // zoom al tramo
  await page.evaluate(() => {
    const S = window.canalizaDebug.S;
    const r = S.runs[S.runs.length - 1]; if (!r) return;
    const mx = (r.pts[0].x + r.pts[r.pts.length - 1].x) / 2, my = (r.pts[0].y + r.pts[r.pts.length - 1].y) / 2;
    S.view.z = 2.2; S.view.x = 850 - mx * 2.2; S.view.y = 525 - my * 2.2;
    window.dispatchEvent(new Event("resize"));
  });
  await sleep(250);
  await page.screenshot({ path: `${OUT}/3-zoom.png` });

  await browser.close();
  stop();
  console.log("capturas en", OUT);
}

main().catch(e => { console.error(e); stop(); process.exit(1); });
