#!/usr/bin/env node
// Renderiza a trilha e os efeitos sintetizados (Web Audio / OfflineAudioContext) e grava WAV PCM por trecho.
//   node audio.mjs --spec audio-spec.json
// spec: { saida, ref, xf, cauda, janela, secoes:[{id,clima,bpm,ini,fim,nivelDb,ambiencias,primeira}], eventos:[{t,tipo,variante,dur}], total }
// Saída: <saida>/manifesto-audio.json + sec-NN-musica.wav, sec-NN-amb.wav, sfx-NN.wav (PCM 24 bits com dither TPDF determinístico, 48 kHz, estéreo; codificação própria em audio/wav.mjs).
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { criarEscritorWav, lerCabecalhoWav } from './audio/wav.mjs';
import { servidor } from './render.mjs';

const BLOCO = 1 << 20;

// Baixa os blocos Float32 de dois canais do OfflineAudioContext e grava WAV PCM com a codificação própria (audio/wav.mjs).
async function baixar(page, id, canalL, canalR, n, destino, { bits = 24 } = {}) {
  const w = criarEscritorWav(destino, { canais: 2, taxa: 48000, bits, float: bits === 32, quadros: n, dither: bits < 32, semente: hashNome(path.basename(destino)) });
  for (let i = 0; i < n; i += BLOCO) {
    const m = Math.min(BLOCO, n - i);
    const [a, b] = await Promise.all([page.evaluate(([id, c, i, m]) => window.lerBloco(id, c, i, m), [id, canalL, i, m]), page.evaluate(([id, c, i, m]) => window.lerBloco(id, c, i, m), [id, canalR, i, m])]);
    const L = new Float32Array(Buffer.from(a, 'base64').buffer.slice(0)), R = new Float32Array(Buffer.from(b, 'base64').buffer.slice(0));
    const inter = new Float32Array(m * 2); for (let k = 0; k < m; k++) { inter[2 * k] = L[k]; inter[2 * k + 1] = R[k]; }
    w.escrever(inter);
  }
  w.fechar();
  const h = lerCabecalhoWav(destino);
  if (h.quadros !== n || h.taxa !== 48000 || h.canais !== 2) throw new Error(`WAV inválido após a gravação: ${destino}`);
}
const hashNome = (s) => { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };

// Hash do código que define o som das seções (síntese, partitura, efeitos de ambiência, composição): entra na chave do cache.
function hashCodigoAudio() {
  const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'audio');
  const h = crypto.createHash('sha1');
  for (const f of fs.readdirSync(dir).filter((f) => /\.(js|json|html)$/.test(f)).sort()) h.update(f).update(fs.readFileSync(path.join(dir, f)));
  return h.digest('hex');
}

async function abrirPaginaAudio(browser, base) {
  const ctx = await browser.newContext();                    // contexto próprio = processo próprio: seções em paralelo de verdade
  const page = await ctx.newPage(); page.on('pageerror', (e) => console.log('ERRO página: ' + e));
  await page.goto(`${base}/audio/audio.html`); await page.waitForFunction('window.__audioPronto === true');
  return page;
}

async function principal() {
  const i = process.argv.indexOf('--spec'); if (i < 0) throw new Error('use --spec arquivo.json');
  const spec = JSON.parse(fs.readFileSync(process.argv[i + 1], 'utf-8'));
  fs.mkdirSync(spec.saida, { recursive: true });
  const cache = spec.cache ?? null; if (cache) fs.mkdirSync(cache, { recursive: true });
  const paralelo = Math.max(1, spec.paralelo ?? 3);
  const srv = await servidor({});
  const base = `http://127.0.0.1:${srv.address().port}`;
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const manifesto = { sr: 48000, ref: spec.ref, secoes: [], sfx: [], motor: 'webaudio-offline', calibracao: null };
  try {
    const page = await abrirPaginaAudio(browser, base);
    Object.assign(manifesto, await page.evaluate(() => ({ perfis: window.PERFIS, alvosPico: window.ALVOS_PICO, composicao: window.COMPOSICAO })));
    // seções musicais: cada uma é independente (semente própria); as já sintetizadas com o mesmo código e parâmetros vêm do cache
    const codigo = hashCodigoAudio();
    const tarefas = spec.secoes.map((s, k) => {
      const args = { ...s, xf: spec.xf ?? 2.5, cauda: spec.cauda ?? 6, ref: s.ref ?? spec.ref, semente: 1 + k };
      const chave = crypto.createHash('sha1').update(JSON.stringify(args)).update(codigo).digest('hex').slice(0, 20);
      return { s, k, args, chave, destino: path.join(spec.saida, `sec-${String(k).padStart(2, '0')}`) };
    });
    const resultados = new Array(tarefas.length);
    const pendentes = [];
    for (const t of tarefas) {
      const c = cache && path.join(cache, t.chave);
      if (c && fs.existsSync(c + '.json') && fs.existsSync(c + '-musica.wav') && (!t.s.ambiencias?.length || fs.existsSync(c + '-amb.wav'))) {
        fs.copyFileSync(c + '-musica.wav', t.destino + '-musica.wav');
        if (t.s.ambiencias?.length) fs.copyFileSync(c + '-amb.wav', t.destino + '-amb.wav');
        resultados[t.k] = { ...JSON.parse(fs.readFileSync(c + '.json', 'utf-8')), doCache: true };
      } else pendentes.push(t);
    }
    const paginas = [page];
    for (let p = 1; p < Math.min(paralelo, pendentes.length); p++) paginas.push(await abrirPaginaAudio(browser, base));
    let prox = 0, feitas = tarefas.length - pendentes.length;
    await Promise.all(paginas.map(async (pg) => {
      while (prox < pendentes.length) {
        const t = pendentes[prox++];
        const r = await pg.evaluate((a) => window.renderSecao(a), t.args);
        await baixar(pg, r.id, 0, 1, r.amostras, t.destino + '-musica.wav');
        if (t.s.ambiencias?.length) await baixar(pg, r.id, 2, 3, r.amostras, t.destino + '-amb.wav');
        await pg.evaluate((id) => window.liberar(id), r.id);
        const info = { inicioAbs: r.inicioAbs, amostras: r.amostras, compassos: r.compassos, beat: r.beat, marcos: r.marcos, picoMusicaDb: r.picoMusica, rmsMusicaDb: r.rmsMusicaDb, rmsAmbDb: r.rmsAmbDb };
        if (cache) {
          const c = path.join(cache, t.chave);
          fs.copyFileSync(t.destino + '-musica.wav', c + '-musica.wav');
          if (t.s.ambiencias?.length) fs.copyFileSync(t.destino + '-amb.wav', c + '-amb.wav');
          fs.writeFileSync(c + '.json', JSON.stringify(info));
        }
        resultados[t.k] = info;
        console.log(`SECAO ${++feitas}/${tarefas.length} ${t.s.clima} ${t.s.ini.toFixed(1)}–${t.s.fim.toFixed(1)}s rms ${r.rmsMusicaDb.toFixed(1)} dB`);
      }
    }));
    for (const t of tarefas) {
      const r = resultados[t.k];
      manifesto.secoes.push({ ...t.s, indice: t.k, inicioAbs: r.inicioAbs, amostras: r.amostras, musica: t.destino + '-musica.wav', amb: t.s.ambiencias?.length ? t.destino + '-amb.wav' : null,
        compassos: r.compassos, beat: r.beat, marcos: r.marcos, picoMusicaDb: r.picoMusicaDb, rmsMusicaDb: r.rmsMusicaDb, rmsAmbDb: r.rmsAmbDb, doCache: !!r.doCache });
      if (r.doCache) console.log(`SECAO ${t.k + 1}/${tarefas.length} ${t.s.clima} (cache) rms ${r.rmsMusicaDb.toFixed(1)} dB`);
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
