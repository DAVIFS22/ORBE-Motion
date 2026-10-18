#!/usr/bin/env node
// Renderiza a trilha e os efeitos sintetizados (Web Audio / OfflineAudioContext) e grava WAV PCM por trecho.
//   node audio.mjs --spec audio-spec.json
// spec: { saida, ref, xf, cauda, janela, secoes:[{id,clima,bpm,ini,fim,nivelDb,ambiencias,primeira}], eventos:[{t,tipo,variante,dur}], total }
// Saída: <saida>/manifesto-audio.json + sec-NN-musica.wav, sec-NN-amb.wav, sfx-NN.wav (float32, 48 kHz, estéreo).
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { servidor } from './render.mjs';

const BLOCO = 1 << 20;

function gravarWav(arquivos, n, canais, destino) {   // canais: [Float32 pedaços por canal via leitor]; entrada raw f32le intercalada
  return new Promise((ok, no) => {
    const p = spawn('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', 'pipe:0', '-c:a', 'pcm_f32le', destino], { stdio: ['pipe', 'ignore', 'pipe'] });
    let err = ''; p.stderr.on('data', (d) => { err += d; }); p.on('close', (c) => (c === 0 ? ok() : no(new Error('ffmpeg: ' + err.slice(-300)))));
    arquivos(p.stdin);
  });
}

async function baixar(page, id, canalL, canalR, n, destino) {
  await gravarWav(async (stdin) => {
    for (let i = 0; i < n; i += BLOCO) {
      const m = Math.min(BLOCO, n - i);
      const [a, b] = await Promise.all([page.evaluate(([id, c, i, m]) => window.lerBloco(id, c, i, m), [id, canalL, i, m]), page.evaluate(([id, c, i, m]) => window.lerBloco(id, c, i, m), [id, canalR, i, m])]);
      const L = new Float32Array(Buffer.from(a, 'base64').buffer.slice(0)), R = new Float32Array(Buffer.from(b, 'base64').buffer.slice(0));
      const inter = new Float32Array(m * 2); for (let k = 0; k < m; k++) { inter[2 * k] = L[k]; inter[2 * k + 1] = R[k]; }
      if (!stdin.write(Buffer.from(inter.buffer))) await new Promise((r) => stdin.once('drain', r));
    }
    stdin.end();
  }, n, 2, destino);
}

async function principal() {
  const i = process.argv.indexOf('--spec'); if (i < 0) throw new Error('use --spec arquivo.json');
  const spec = JSON.parse(fs.readFileSync(process.argv[i + 1], 'utf-8'));
  fs.mkdirSync(spec.saida, { recursive: true });
  const srv = await servidor({});
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const manifesto = { sr: 48000, ref: spec.ref, secoes: [], sfx: [], motor: 'webaudio-offline', calibracao: null };
  try {
    const page = await browser.newPage(); page.on('pageerror', (e) => console.log('ERRO página: ' + e));
    await page.goto(`http://127.0.0.1:${srv.address().port}/audio/audio.html`); await page.waitForFunction('window.__audioPronto === true');
    let k = 0;
    for (const s of spec.secoes) {
      const r = await page.evaluate((a) => window.renderSecao(a), { ...s, xf: spec.xf ?? 2.5, cauda: spec.cauda ?? 6, ref: spec.ref, semente: 1 + k });
      const base = path.join(spec.saida, `sec-${String(k).padStart(2, '0')}`);
      await baixar(page, r.id, 0, 1, r.amostras, base + '-musica.wav');
      if (s.ambiencias?.length) await baixar(page, r.id, 2, 3, r.amostras, base + '-amb.wav');
      await page.evaluate((id) => window.liberar(id), r.id);
      manifesto.secoes.push({ ...s, indice: k, inicioAbs: r.inicioAbs, amostras: r.amostras, musica: base + '-musica.wav', amb: s.ambiencias?.length ? base + '-amb.wav' : null, compassos: r.compassos, beat: r.beat, marcos: r.marcos,
        picoMusicaDb: r.picoMusica, rmsMusicaDb: r.rmsMusicaDb, rmsAmbDb: r.rmsAmbDb });
      console.log(`SECAO ${k + 1}/${spec.secoes.length} ${s.clima} ${s.ini.toFixed(1)}–${s.fim.toFixed(1)}s rms ${r.rmsMusicaDb.toFixed(1)} dB`);
      k++;
    }
    manifesto.calibracao = await page.evaluate(() => window.calibrar());
    const J = spec.janela ?? 60; let w = 0;
    for (let t0 = 0; t0 < spec.total; t0 += J, w++) {
      const evs = (spec.eventos ?? []).filter((e) => e.t >= t0 && e.t < t0 + J);
      if (!evs.length) continue;
      const r = await page.evaluate((a) => window.renderEfeitos(a), { id: 'sfx' + w, t0, t1: t0 + J, ref: spec.ref, eventos: evs });
      const arq = path.join(spec.saida, `sfx-${String(w).padStart(2, '0')}.wav`);
      await baixar(page, r.id, 0, 1, r.amostras, arq); await page.evaluate((id) => window.liberar(id), r.id);
      manifesto.sfx.push({ inicioAbs: r.inicioAbs, arquivo: arq, eventos: evs.length, picoDb: r.pico });
      console.log(`SFX ${w} (${evs.length} eventos) pico ${r.pico.toFixed(1)} dBFS`);
    }
  } finally { await browser.close(); srv.close(); }
  fs.writeFileSync(path.join(spec.saida, 'manifesto-audio.json'), JSON.stringify(manifesto, null, 1));
  console.log('CONCLUIDO');
}
principal().catch((e) => { console.error('ERRO ' + (e.stack || e)); process.exit(1); });
