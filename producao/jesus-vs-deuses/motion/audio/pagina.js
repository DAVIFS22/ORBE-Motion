// API da página de áudio: renderiza seções musicais (música + ambiência) e janelas de efeitos com OfflineAudioContext.
// Os resultados ficam na página e são lidos em blocos (base64) pelo Node. Nenhum arquivo de áudio externo é usado.
import { SR, criarBarramento, dbLin } from './sintese.js';
import { tocarSecao } from './partitura.js';
import { ALVOS_PICO, tocarEvento, AMBIENCIAS, OFFSET_AMB } from './efeitos.js';

const resultados = new Map();

function rms(canais, i0, i1) {
  let s = 0, n = 0;
  for (const c of canais) for (let i = i0; i < i1; i++) { const v = c[i]; s += v * v; n++; }
  return Math.sqrt(s / Math.max(1, n));
}
function pico(canais, i0 = 0, i1 = null) {
  let p = 0; for (const c of canais) { const f = i1 ?? c.length; for (let i = i0; i < f; i++) { const a = Math.abs(c[i]); if (a > p) p = a; } }
  return p;
}
const lin = (x) => 20 * Math.log10(Math.max(1e-9, x));

function saidaEstereo(ctx, merger, canal0) {
  const g = ctx.createGain(); g.channelCount = 2; g.channelCountMode = 'explicit';
  const sp = ctx.createChannelSplitter(2); g.connect(sp); sp.connect(merger, 0, canal0); sp.connect(merger, 1, canal0 + 1);
  return g;
}

// spec: { id, clima, bpm, ini, fim, xf, cauda, ref, nivelDb, primeira, ambiencias:[], semente }
window.renderSecao = async function (spec) {
  const { clima, bpm, ini, fim, xf, cauda, ref, nivelDb, primeira, ambiencias = [], semente = 1 } = spec;
  const inicioCtx = primeira ? 0 : xf;                       // instante (no contexto) do compasso 1
  const durSec = fim - ini, total = inicioCtx + durSec + xf + cauda;
  const ctx = new OfflineAudioContext(4, Math.ceil(total * SR), SR);
  const merger = ctx.createChannelMerger(4); merger.connect(ctx.destination);
  const mus = saidaEstereo(ctx, merger, 0), amb = saidaEstereo(ctx, merger, 2);
  // envelope de seção: entra em ~xf*2 (ou 3 s na primeira) e sai em xf*2, para somar com a vizinha em fusão cruzada
  const env = ctx.createGain(); env.connect(mus);
  env.gain.setValueAtTime(0.0001, primeira ? 0 : inicioCtx - xf); env.gain.linearRampToValueAtTime(1, inicioCtx + (primeira ? 3 : xf));
  env.gain.setValueAtTime(1, inicioCtx + durSec - xf); env.gain.linearRampToValueAtTime(0.0001, inicioCtx + durSec + xf);
  const busM = criarBarramento(ctx, env, { decaimento: 4.2, wet: 0.55, semente: semente + 1, brilho: 0.45 });
  const info = tocarSecao(ctx, busM, clima, bpm, inicioCtx, durSec, semente, spec.camadas ?? null);
  const envA = ctx.createGain(); envA.connect(amb);
  envA.gain.setValueAtTime(0.0001, primeira ? 0 : inicioCtx - xf); envA.gain.linearRampToValueAtTime(1, inicioCtx + (primeira ? 2.5 : xf));
  envA.gain.setValueAtTime(1, inicioCtx + durSec - xf); envA.gain.linearRampToValueAtTime(0.0001, inicioCtx + durSec + xf);
  const busA = criarBarramento(ctx, envA, { decaimento: 5.5, wet: 0.5, semente: semente + 2, brilho: 0.3 });
  let offs = 0, k = 0;
  for (const nome of ambiencias) { const f = AMBIENCIAS[nome]; if (!f) throw new Error('ambiência desconhecida: ' + nome); f(ctx, busA, inicioCtx - (primeira ? 0 : xf), durSec + (primeira ? 0 : xf) + xf, semente + 10 * (++k)); offs += OFFSET_AMB[nome] ?? 0; }
  if (ambiencias.length) offs /= ambiencias.length;
  const buf = await ctx.startRendering();
  const canais = [0, 1, 2, 3].map((i) => buf.getChannelData(i));
  // nível: RMS do corpo da seção (sem as fusões) = ref - 17 + nível do clima (música) e ref - 27 + deslocamento (ambiência)
  const c0 = Math.floor((inicioCtx + xf) * SR), c1 = Math.floor((inicioCtx + durSec - xf) * SR);
  const corpo0 = c1 > c0 + SR ? c0 : 0, corpo1 = c1 > c0 + SR ? c1 : canais[0].length;
  const alvoM = dbLin(ref - 17 + nivelDb), alvoA = dbLin(ref - 27 + offs);
  const rm = rms([canais[0], canais[1]], corpo0, corpo1), ra = ambiencias.length ? rms([canais[2], canais[3]], corpo0, corpo1) : 0;
  const gM = spec.bruto ? 1 : (rm > 1e-9 ? alvoM / rm : 0), gA = spec.bruto ? 1 : (ra > 1e-9 ? alvoA / ra : 0);   // bruto: calibração de camadas
  for (let i = 0; i < canais[0].length; i++) { canais[0][i] *= gM; canais[1][i] *= gM; canais[2][i] *= gA; canais[3][i] *= gA; }
  const id = spec.id ?? clima + ':' + ini; resultados.set(id, canais);
  return { id, amostras: canais[0].length, inicioAbs: ini - (primeira ? 0 : xf), compassos: info.compassos, beat: info.beat, marcos: info.marcos, picoMusica: lin(pico([canais[0], canais[1]])), picoAmb: lin(pico([canais[2], canais[3]])),
    rmsMusicaDb: lin(rms([canais[0], canais[1]], corpo0, corpo1)), rmsAmbDb: lin(rms([canais[2], canais[3]], corpo0, corpo1)) };
};

// Calibração dos efeitos: renderiza cada tipo/variante isolado e mede o pico (aplicado como ganho no render das janelas).
let calibracao = null;
async function calibrar() {
  if (calibracao) return calibracao;
  calibracao = {};
  for (const tipo of Object.keys(ALVOS_PICO)) {
    for (const v of tipo === 'whoosh' || tipo === 'impacto' || tipo === 'nota' || tipo === 'ping' || tipo === 'revelar' ? [0, 1, 2, 3] : [0, 1]) {
      const dur = tipo === 'passos' ? 5 : 8;
      const ctx = new OfflineAudioContext(2, Math.ceil((dur + 2) * SR), SR);
      const bus = criarBarramento(ctx, ctx.destination, { decaimento: 3, wet: 0.45, semente: 5, brilho: 0.4 });
      tocarEvento(ctx, bus, tipo, 1.0, v, dur);
      const b = await ctx.startRendering();
      calibracao[tipo + ':' + v] = Math.max(1e-6, pico([b.getChannelData(0), b.getChannelData(1)]));
    }
  }
  return calibracao;
}
window.calibrar = calibrar;

// spec: { id, t0, t1, ref, eventos:[{t, tipo, variante, dur}] }  (janela [t0, t1) com folga no começo/fim)
window.renderEfeitos = async function (spec) {
  const { t0, t1, ref, eventos } = spec; const cal = await calibrar();
  const folga = 1.0, cauda = 6.0, total = (t1 - t0) + folga + cauda;
  const ctx = new OfflineAudioContext(2, Math.ceil(total * SR), SR);
  const saida = ctx.createGain(); saida.connect(ctx.destination);
  const busJanela = criarBarramento(ctx, saida, { decaimento: 3.2, wet: 0.5, semente: 9, brilho: 0.4 });
  for (const e of eventos) {
    const v = e.variante ?? 0, chave = e.tipo + ':' + (cal[e.tipo + ':' + v] !== undefined ? v : v % 2);
    const alvo = dbLin(ref + (ALVOS_PICO[e.tipo] ?? -12)), fator = alvo / (cal[chave] ?? 1);
    const sg = ctx.createGain(), se = ctx.createGain(); sg.gain.value = fator; se.gain.value = fator;
    sg.connect(busJanela.seco); se.connect(busJanela.envio);
    tocarEvento(ctx, { ctx, seco: sg, envio: se }, e.tipo, e.t - t0 + folga, v, e.dur ?? 0);
  }
  const buf = await ctx.startRendering();
  const canais = [buf.getChannelData(0), buf.getChannelData(1)];
  const id = spec.id ?? 'sfx:' + t0; resultados.set(id, canais);
  return { id, amostras: canais[0].length, inicioAbs: t0 - folga, pico: lin(pico(canais)) };
};

window.lerBloco = function (id, canal, inicio, n) {
  const c = resultados.get(id)[canal].subarray(inicio, inicio + n);
  const u8 = new Uint8Array(c.buffer, c.byteOffset, c.byteLength); let s = '';
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
};
window.liberar = (id) => { resultados.delete(id); };
window.__audioPronto = true;
