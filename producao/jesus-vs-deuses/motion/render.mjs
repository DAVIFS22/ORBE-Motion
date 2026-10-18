#!/usr/bin/env node
// Renderizador determinístico das cenas de motion.
//
//   node render.mjs --spec spec.json [--workers 3] [--only id1,id2]          -> MP4 (H.264, yuv420p, CRF 16) por clipe
//   node render.mjs --spec spec.json --quadros 0.5,3.2 --png-dir DIR          -> PNGs nos instantes pedidos (revisão/testes)
//
// Contrato: cada quadro é window.seek(t) com t = i / fps, sem estado entre quadros. Os instantes podem ser pedidos em
// qualquer ordem e o resultado é o mesmo. Não há timers, requestAnimationFrame, transições CSS nem Math.random.
//
// spec.json: { largura, altura, fps, crf, preset, assets: {chave: caminhoAbsoluto}, clipes: [{id, comp, dur, seed, params, saida}] }

import { chromium } from 'playwright-core';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
export const VERSAO_MOTION = '1.0.0';

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.woff2': 'font/woff2',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml' };

function argumentos(argv) {
  const a = { workers: 3, workersWebgl: 1, captura: 'cdp' };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    const v = () => argv[++i];
    if (k === '--spec') a.spec = v();
    else if (k === '--workers') a.workers = Math.max(1, parseInt(v(), 10));
    else if (k === '--workers-webgl') a.workersWebgl = Math.max(1, parseInt(v(), 10));
    else if (k === '--only') a.only = v().split(',');
    else if (k === '--quadros') a.quadros = v().split(',').map(Number);
    else if (k === '--png-dir') a.pngDir = v();
    else if (k === '--embaralhar') a.embaralhar = true;
    else if (k === '--captura') a.captura = v();
    else if (k === '--cancelar') a.cancelar = v();
    else if (k === '--ffmpeg') a.ffmpeg = v();
    else if (k === '--chromium') a.chromium = v();
    else if (k === '--sonda') a.sonda = true;
    else throw new Error('argumento desconhecido: ' + k);
  }
  if (!a.spec && !a.sonda) throw new Error('use --spec arquivo.json');
  return a;
}

// Servidor local: arquivos do projeto + /ativo/<chave> (imagens autorizadas na spec). Só leitura.
export function servidor(ativos) {
  const srv = http.createServer((req, res) => {
    try {
      const url = new URL(req.url, 'http://x');
      let arq;
      if (url.pathname.startsWith('/ativo/')) {
        arq = ativos[decodeURIComponent(url.pathname.slice(7))];
        if (!arq) { res.writeHead(404); res.end(); return; }
      } else if (url.pathname.startsWith('/vendor/')) {            // bibliotecas fixadas em package.json (somente leitura)
        const rel = decodeURIComponent(url.pathname.slice(8));
        const mapa = { 'three/': 'node_modules/three/build/', 'three-addons/': 'node_modules/three/examples/jsm/', 'gsap/': 'node_modules/gsap/' };
        const pref = Object.keys(mapa).find((k) => rel.startsWith(k));
        arq = pref ? path.join(AQUI, mapa[pref], rel.slice(pref.length)) : null;
        if (!arq || arq.includes('..')) { res.writeHead(403); res.end(); return; }
      } else {
        arq = path.join(AQUI, decodeURIComponent(url.pathname === '/' ? '/film.html' : url.pathname));
        if (!arq.startsWith(AQUI + path.sep) || arq.includes('node_modules')) { res.writeHead(403); res.end(); return; }
      }
      const dados = fs.readFileSync(arq);
      res.writeHead(200, { 'Content-Type': MIME[path.extname(arq).toLowerCase()] ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
      res.end(dados);
    } catch (_) { res.writeHead(404); res.end(); }
  });
  return new Promise((ok) => srv.listen(0, '127.0.0.1', () => ok(srv)));
}

async function abrirPagina(browser, base, spec) {
  // O layout é sempre 1920×1080 px CSS; a resolução de saída é obtida pelo fator de escala do dispositivo (prévias em 960×540 etc.).
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: spec.largura / 1920, colorScheme: 'dark' });
  // Contrato aplicado no próprio navegador: nenhum avanço autônomo (rAF neutralizado) e Math.random determinístico
  // (mulberry32 com semente fixa; o Three.js o usa só para UUIDs, que não afetam os pixels).
  await ctx.addInitScript(() => {
    window.requestAnimationFrame = () => 0;
    window.cancelAnimationFrame = () => {};
    let a = 0xc0ffee;
    Math.random = () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  });
  await ctx.addInitScript((c) => { window.RENDER3D = c; }, spec.render3d ?? {});      // { escala, msaa }: resolução interna das cenas 3D
  const page = await ctx.newPage();
  const erros = [];
  page.on('pageerror', (e) => erros.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });
  await page.goto(base + '/film.html');
  await page.waitForFunction('window.__pronto === true');
  const cdp = await ctx.newCDPSession(page);
  return { ctx, page, cdp, erros, escala: spec.largura / 1920 };
}

async function capturar(w, captura) {
  if (captura === 'cdp') {
    const clip = w.escala === 1 ? undefined : { x: 0, y: 0, width: 1920, height: 1080, scale: w.escala };   // prévias: saída em escala reduzida
    const r = await w.cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true, ...(clip ? { clip } : {}) });
    return Buffer.from(r.data, 'base64');
  }
  return w.page.screenshot({ type: 'png', animations: 'disabled' });
}

function comTimeout(promessa, ms, msg) {
  let t; const limite = new Promise((_, no) => { t = setTimeout(() => no(new Error(msg)), ms); });
  return Promise.race([promessa, limite]).finally(() => clearTimeout(t));
}

async function carregarCena(w, spec, clipe) {
  w.erros.length = 0;               // erros de um clipe anterior não contaminam o próximo
  const info = await comTimeout(w.page.evaluate((c) => window.loadScene(c), {
    comp: clipe.comp, dur: clipe.dur_visivel ?? clipe.dur, t0: clipe.t0 ?? 0, seed: clipe.seed ?? 1, params: clipe.params ?? {}, largura: spec.largura, altura: spec.altura,
    fps: spec.fps, base: '', id: clipe.id,
  }), 120000, `a cena ${clipe.id} não carregou em 120 s`);
  if (w.erros.length) throw new Error(`erro na página ao carregar ${clipe.id}: ${w.erros.join(' | ')}`);
  return info;
}

async function quadro(w, t, captura) {
  await comTimeout(w.page.evaluate((x) => window.seek(x), t), 120000, `seek(${t}) travou`);
  if (w.erros.length) throw new Error('erro na página: ' + w.erros.join(' | '));
  return comTimeout(capturar(w, captura), 120000, `captura em t=${t} travou`);
}

function lancarFfmpeg(spec, saidaTmp, ffmpeg) {
  const filtros = 'scale=in_range=full:out_range=tv:out_color_matrix=bt709:flags=lanczos,format=yuv420p';
  const args = ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(spec.fps), '-c:v', 'png', '-i', 'pipe:0',
    '-vf', filtros, '-c:v', 'libx264', '-preset', spec.preset ?? 'medium', '-crf', String(spec.crf ?? 16), '-pix_fmt', 'yuv420p',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-an', '-movflags', '+faststart', '-f', 'mp4', saidaTmp];
  const p = spawn(ffmpeg, args, { stdio: ['pipe', 'ignore', 'pipe'] });
  let err = '';
  p.stderr.on('data', (d) => { err += d; });
  const fim = new Promise((ok, no) => p.on('close', (c) => (c === 0 ? ok() : no(new Error('ffmpeg falhou: ' + err.slice(-400))))));
  return { p, fim };
}

async function renderizarClipe(w, spec, clipe, o) {
  const info = await carregarCena(w, spec, clipe);
  const n = Math.max(2, Math.round(clipe.dur * spec.fps));
  fs.mkdirSync(path.dirname(clipe.saida), { recursive: true });
  const tmp = clipe.saida + '.parcial.mp4';
  const ff = lancarFfmpeg(spec, tmp, o.ffmpeg ?? 'ffmpeg');
  ff.p.stdin.on('error', () => { /* o erro real vem do 'close' */ });
  const h = crypto.createHash('sha256');
  try {
    for (let i = 0; i < n; i++) {
      if (o.cancelar && fs.existsSync(o.cancelar)) { ff.p.kill('SIGKILL'); throw Object.assign(new Error('cancelado'), { cancelado: true }); }
      const buf = await quadro(w, i / spec.fps, o.captura);
      if (i % 10 === 0 || i === n - 1) h.update(buf);   // impressão digital leve para auditoria
      if (!ff.p.stdin.write(buf)) await new Promise((ok) => ff.p.stdin.once('drain', ok));
      if (i % 15 === 0 || i === n - 1) console.log(`PROGRESSO ${clipe.id} ${i + 1}/${n}`);
    }
    ff.p.stdin.end();
    await ff.fim;
  } catch (e) { try { ff.p.kill('SIGKILL'); } catch (_) { /* já encerrado */ } fs.rmSync(tmp, { force: true }); throw e; }
  fs.renameSync(tmp, clipe.saida);
  fs.writeFileSync(clipe.saida + '.json', JSON.stringify({ id: clipe.id, comp: clipe.comp, dur: n / spec.fps, fps: spec.fps, quadros: n, eventos: info.eventos,
    motor: 'motion-' + VERSAO_MOTION, impressao: h.digest('hex').slice(0, 16) }, null, 1));
  console.log(`CLIPE_PRONTO ${clipe.id}`);
}

async function sonda(o) {
  const browser = await chromium.launch({ executablePath: o.chromium || process.env.MOTION_CHROMIUM || undefined, headless: true,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] });
  const page = await browser.newPage();
  const r = await page.evaluate(() => { const c = document.createElement('canvas'); const gl = c.getContext('webgl2'); return { versao: navigator.userAgent, webgl2: !!gl }; });
  await browser.close();
  console.log('SONDA_OK ' + JSON.stringify(r));
}

async function principal() {
  const o = argumentos(process.argv.slice(2));
  if (o.sonda) return sonda(o);
  const spec = JSON.parse(fs.readFileSync(o.spec, 'utf-8'));
  spec.largura ??= 1920; spec.altura ??= 1080; spec.fps ??= 30;
  let clipes = spec.clipes;
  if (o.only) clipes = clipes.filter((c) => o.only.includes(c.id));
  if (!clipes.length) throw new Error('nenhum clipe a renderizar');
  const srv = await servidor(spec.assets ?? {});
  const base = 'http://127.0.0.1:' + srv.address().port;
  const base_args = ['--force-color-profile=srgb', '--font-render-hinting=none', '--disable-lcd-text', '--hide-scrollbars', '--no-sandbox'];
  const lanc = (webgl) => chromium.launch({ executablePath: o.chromium || process.env.MOTION_CHROMIUM || undefined, headless: true,
    args: webgl ? [...base_args, '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-compositing', '--disable-gpu-rasterization', '--disable-accelerated-2d-canvas'] : [...base_args, '--disable-gpu'] });
  const navegadores = {};       // 2D: sem GPU (composição por software, ~7x mais rápida); WebGL: SwiftShader
  const navegador = (webgl) => (navegadores[webgl] ??= lanc(webgl));   // guarda a PROMESSA: workers concorrentes compartilham um só navegador
  const usaWebgl = (c) => c.webgl ?? /^(teste3d|cena3d)/.test(c.comp);
  const pagina = async (cache, webgl) => (cache[webgl] ??= await abrirPagina(await navegador(webgl), base, spec));
  const falhas = [];
  try {
    if (o.quadros) {                                   // modo revisão: PNGs em instantes arbitrários (qualquer ordem)
      const cache = {};
      fs.mkdirSync(o.pngDir, { recursive: true });
      for (const clipe of clipes) {
        const w = await pagina(cache, usaWebgl(clipe));
        await carregarCena(w, spec, clipe);
        const ts = o.embaralhar ? [...o.quadros].sort((a, b) => ((a * 7919) % 13) - ((b * 7919) % 13)) : o.quadros;
        for (const t of ts) fs.writeFileSync(path.join(o.pngDir, `${clipe.id.replace(/[^\w.-]/g, '_')}_t${String(Math.round(t * 1000)).padStart(6, '0')}.png`), await quadro(w, t, o.captura));
        console.log(`QUADROS_PRONTOS ${clipe.id}`);
      }
      for (const w of Object.values(cache)) await w.ctx.close();
    } else {
      // Duas filas: composições 2D (vários trabalhadores) e cenas WebGL por software (SwiftShader já usa todos os núcleos: 1 por vez)
      const filas = { plana: clipes.filter((c) => !usaWebgl(c)), webgl: clipes.filter((c) => usaWebgl(c)) };
      const trabalhadores = (fila, n) => Array.from({ length: Math.min(n, fila.length) }, async () => {
        const cache = {};
        for (let c = fila.shift(); c; c = fila.shift()) {
          try { await renderizarClipe(await pagina(cache, usaWebgl(c)), spec, c, o); } catch (e) {
            if (e.cancelado) { console.log('CANCELADO'); process.exitCode = 130; filas.plana.length = 0; filas.webgl.length = 0; break; }
            falhas.push(`${c.id}: ${e.message}`); console.log(`FALHOU ${c.id}: ${e.message}`);
          }
        }
        for (const w of Object.values(cache)) await w.ctx.close();
      });
      await Promise.all([...trabalhadores(filas.plana, o.workers), ...trabalhadores(filas.webgl, o.workersWebgl)]);
    }
  } finally { for (const b of Object.values(navegadores)) await (await b).close(); srv.close(); }
  if (falhas.length) { console.error('ERRO ' + falhas.join('\n')); process.exitCode = 1; } else if (!process.exitCode) console.log('CONCLUIDO');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  principal().catch((e) => { console.error('ERRO ' + (e.stack || e)); process.exit(1); });
}
