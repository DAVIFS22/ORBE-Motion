// Síntese sonora com a Web Audio API (OfflineAudioContext): osciladores, filtros, envelopes, FM, ruído com semente.
// Nada aqui usa arquivos de áudio, samples ou gravações: tudo é sintetizado. Os timbres são sintéticos e não imitam
// instrumentos acústicos de forma enganosa. Todo ruído vem de mulberry32 com semente fixa (nunca Math.random).
import { mulberry32, hash32 } from '../engine/rng.js';

export const SR = 48000;
const BASE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

export function midi(nome) {
  const m = /^([A-G])([#b]?)(-?\d)$/.exec(nome);
  if (!m) throw new Error('nota inválida: ' + nome);
  return 12 * (Number(m[3]) + 1) + BASE[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
}
export const hzMidi = (n) => 440 * Math.pow(2, (n - 69) / 12);
export const hz = (nome) => hzMidi(midi(nome));
export const dbLin = (db) => Math.pow(10, db / 20);

// ------------------------------------------------------------------ infraestrutura ---

const cacheRuido = new WeakMap();
export function bufferRuido(ctx, semente = 1, seg = 8) {
  let c = cacheRuido.get(ctx);
  if (!c) { c = new Map(); cacheRuido.set(ctx, c); }
  const k = semente + ':' + seg;
  if (!c.has(k)) {
    const b = ctx.createBuffer(1, Math.round(SR * seg), SR);
    const d = b.getChannelData(0); const r = mulberry32(hash32(semente, 424242));
    for (let i = 0; i < d.length; i++) d[i] = r() * 2 - 1;
    c.set(k, b);
  }
  return c.get(k);
}

export function fonteRuido(ctx, semente, inicio, fim, desloc = 0) {
  const s = ctx.createBufferSource(); s.buffer = bufferRuido(ctx, semente); s.loop = true;
  s.start(inicio, desloc % 7); s.stop(fim);
  return s;
}

// Resposta ao impulso sintética (estéreo): ruído com decaimento exponencial e amortecimento de agudos crescente.
export function respostaImpulso(ctx, decaimento = 3.5, semente = 1, brilho = 0.5) {
  const n = Math.round(SR * decaimento * 1.15), b = ctx.createBuffer(2, n, SR);
  for (let c = 0; c < 2; c++) {
    const d = b.getChannelData(c), r = mulberry32(hash32(semente, 7001 + c)); let y = 0;
    const pre = Math.round(SR * 0.018);
    for (let i = 0; i < n; i++) {
      const t = i / SR, x = r() * 2 - 1;
      const a = 0.08 + (0.9 - 0.08) * Math.pow(1 - Math.min(1, t / decaimento), 2) * brilho + 0.04;   // agudos morrem antes dos graves
      y += a * (x - y);
      d[i] = i < pre ? 0 : y * Math.exp((-6.9 * t) / decaimento) * (1 - Math.exp(-t * 60));
    }
  }
  return b;
}

// Barramento: som direto + envio de reverberação, tudo terminando em `saida` (GainNode estéreo).
export function criarBarramento(ctx, saida, { decaimento = 3.5, wet = 0.5, semente = 1, brilho = 0.5 } = {}) {
  const seco = ctx.createGain(), envio = ctx.createGain(), conv = ctx.createConvolver(), molhado = ctx.createGain();
  conv.normalize = true; conv.buffer = respostaImpulso(ctx, decaimento, semente, brilho); molhado.gain.value = wet;
  seco.connect(saida); envio.connect(conv); conv.connect(molhado); molhado.connect(saida);
  return { ctx, seco, envio };
}

export function lig(no, bus, wet = 0.25) {
  no.connect(bus.seco);
  if (wet > 0) { const g = bus.ctx.createGain(); g.gain.value = wet; no.connect(g); g.connect(bus.envio); }
}

export function adsr(param, t0, a, d, s, r, pico, dur) {
  const fim = t0 + Math.max(dur, a + d);
  param.setValueAtTime(0.00001, t0);
  param.linearRampToValueAtTime(pico, t0 + a);
  param.linearRampToValueAtTime(Math.max(0.00001, pico * s), t0 + a + d);
  param.setValueAtTime(Math.max(0.00001, pico * s), fim);
  param.linearRampToValueAtTime(0.00001, fim + r);
}

function osc(ctx, tipo, freq, t0, t1, detune = 0) {
  const o = ctx.createOscillator(); o.type = tipo; o.frequency.value = freq; o.detune.value = detune; o.start(t0); o.stop(t1); return o;
}

// ------------------------------------------------------------------- vozes de música ---

// Pad sintético: três osciladores levemente desafinados por nota, filtro com respiração lenta.
export function pad(ctx, bus, t0, dur, freqs, o = {}) {
  const { ganho = 0.05, brilho = 1, ataque = 2.5, libera = 3, onda = 'sawtooth', desafina = 7, lfo = 0.08, wet = 0.35, vib = 0, vibHz = 5.2 } = o;
  const fim = t0 + dur + libera + 0.2;
  freqs.forEach((f, i) => {
    for (const dt of [-desafina, 0, desafina]) {
      const x = osc(ctx, onda, f, t0, fim, dt);
      const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = Math.min(11000, f * (2 + 3 * brilho)); lp.Q.value = 0.5;
      const l = osc(ctx, 'sine', lfo * (0.7 + 0.13 * i), t0, fim), lg = ctx.createGain(); lg.gain.value = lp.frequency.value * 0.28; l.connect(lg); lg.connect(lp.frequency);
      if (vib) { const v = osc(ctx, 'sine', vibHz * (0.9 + 0.05 * i), t0, fim), vg = ctx.createGain(); vg.gain.value = vib * 1200; v.connect(vg); vg.connect(x.detune); }
      const g = ctx.createGain(); adsr(g.gain, t0, ataque, 0.6, 1, libera, ganho / (freqs.length * 1.6), dur);
      const p = ctx.createStereoPanner(); p.pan.value = ((i % 5) - 2) * 0.26;
      x.connect(lp); lp.connect(g); g.connect(p); lig(p, bus, wet);
    }
  });
}

// Voz sintética de "coro" (formantes de /a/ sobre dente de serra com vibrato) – timbre eletrônico, não vozes gravadas.
export function coro(ctx, bus, t0, dur, freqs, o = {}) {
  const { ganho = 0.05, ataque = 2.8, libera = 3.5, wet = 0.5, vogal = [[800, 1], [1150, 0.5], [2900, 0.22]] } = o;
  const fim = t0 + dur + libera + 0.2;
  freqs.forEach((f, i) => {
    const x = osc(ctx, 'sawtooth', f, t0, fim, (i % 2 ? 5 : -5)), y = osc(ctx, 'sawtooth', f, t0, fim, (i % 2 ? -4 : 4));
    const v = osc(ctx, 'sine', 5.4 + 0.2 * i, t0, fim), vg = ctx.createGain(); vg.gain.value = 9; v.connect(vg); vg.connect(x.detune); vg.connect(y.detune);
    const soma = ctx.createGain(); soma.gain.value = 1; x.connect(soma); y.connect(soma);
    const g = ctx.createGain(); adsr(g.gain, t0, ataque, 0.8, 1, libera, ganho / (freqs.length * 1.4), dur);
    const p = ctx.createStereoPanner(); p.pan.value = ((i % 4) - 1.5) * 0.3;
    for (const [fc, a] of vogal) { const b = ctx.createBiquadFilter(); b.type = 'bandpass'; b.frequency.value = fc; b.Q.value = 7; const ga = ctx.createGain(); ga.gain.value = a; soma.connect(b); b.connect(ga); ga.connect(g); }
    g.connect(p); lig(p, bus, wet);
  });
}

// Subgrave: seno + triângulo com respiração lenta.
export function sub(ctx, bus, t0, dur, freq, o = {}) {
  const { ganho = 0.12, ataque = 3, libera = 3.5, bat = 0.12 } = o; const fim = t0 + dur + libera + 0.2;
  const g = ctx.createGain(); adsr(g.gain, t0, ataque, 0.5, 1, libera, ganho, dur);
  const a = osc(ctx, 'sine', freq, t0, fim), b = osc(ctx, 'triangle', freq + bat, t0, fim), bg = ctx.createGain(); bg.gain.value = 0.35;
  const l = osc(ctx, 'sine', 0.07, t0, fim), lg = ctx.createGain(); lg.gain.value = ganho * 0.18; l.connect(lg); lg.connect(g.gain);
  a.connect(g); b.connect(bg); bg.connect(g); lig(g, bus, 0.08);
}

// Piano sintético (aditivo): parciais com decaimento próprio e batida de martelo; soa como "piano eletrônico".
export function piano(ctx, bus, t0, freq, o = {}) {
  const { vel = 0.7, dur = 5, wet = 0.45, semente = 1 } = o;
  const g = ctx.createGain(); g.gain.value = 0.18 * vel; const p = ctx.createStereoPanner(); p.pan.value = Math.max(-0.6, Math.min(0.6, (Math.log2(freq / 261.6)) * 0.22));
  g.connect(p); lig(p, bus, wet);
  for (let k = 1; k <= 7; k++) {
    const fk = freq * k * Math.sqrt(1 + 0.00035 * k * k); if (fk > 11000) break;
    const tau = Math.min(dur, 4.2 / (0.55 + 0.6 * k));
    const x = osc(ctx, 'sine', fk, t0, t0 + tau + 0.3), a = ctx.createGain();
    a.gain.setValueAtTime(vel / Math.pow(k, 1.25), t0); a.gain.exponentialRampToValueAtTime(0.0001, t0 + tau);
    x.connect(a); a.connect(g);
  }
  const r = fonteRuido(ctx, 11 + semente, t0, t0 + 0.04, semente), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = Math.min(6000, freq * 5); bp.Q.value = 1.1;
  const ng = ctx.createGain(); ng.gain.setValueAtTime(0.05 * vel, t0); ng.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.04); r.connect(bp); bp.connect(ng); ng.connect(g);
}

// Pluck sintético (dente de serra + triângulo, filtro que fecha) para ostinatos.
export function pluck(ctx, bus, t0, freq, o = {}) {
  const { ganho = 0.07, dur = 0.8, brilho = 1, wet = 0.3, pan = 0 } = o;
  const x = osc(ctx, 'sawtooth', freq, t0, t0 + dur + 0.2), y = osc(ctx, 'triangle', freq * 2, t0, t0 + dur + 0.2);
  const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 2.5;
  lp.frequency.setValueAtTime(Math.min(9000, freq * (6 + 6 * brilho)), t0); lp.frequency.exponentialRampToValueAtTime(Math.max(200, freq * 1.6), t0 + dur * 0.8);
  const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(ganho, t0 + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  const ya = ctx.createGain(); ya.gain.value = 0.3; const p = ctx.createStereoPanner(); p.pan.value = pan;
  x.connect(lp); y.connect(ya); ya.connect(lp); lp.connect(g); g.connect(p); lig(p, bus, wet);
}

// "Palheta" sintética para melodias modais (dente de serra com vibrato e filtro formante nasal).
export function palheta(ctx, bus, t0, dur, freq, o = {}) {
  const { ganho = 0.07, wet = 0.45 } = o; const fim = t0 + dur + 0.5;
  const x = osc(ctx, 'sawtooth', freq, t0, fim), v = osc(ctx, 'sine', 5.6, t0, fim), vg = ctx.createGain(); vg.gain.value = 14; v.connect(vg); vg.connect(x.detune);
  const b = ctx.createBiquadFilter(); b.type = 'bandpass'; b.frequency.value = Math.min(5000, freq * 3.2); b.Q.value = 2.2;
  const g = ctx.createGain(); adsr(g.gain, t0, 0.06, 0.12, 0.8, 0.25, ganho, dur); x.connect(b); b.connect(g); lig(g, bus, wet);
}

// ------------------------------------------------------------------ percussão e golpes ---

export function bumbo(ctx, bus, t0, o = {}) {
  const { ganho = 0.5, f0 = 118, f1 = 44, dur = 0.55, wet = 0.25 } = o;
  const x = osc(ctx, 'sine', f0, t0, t0 + dur + 0.1); x.frequency.setValueAtTime(f0, t0); x.frequency.exponentialRampToValueAtTime(f1, t0 + 0.16);
  const g = ctx.createGain(); g.gain.setValueAtTime(ganho, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  const r = fonteRuido(ctx, 31, t0, t0 + 0.012), cg = ctx.createGain(); cg.gain.value = ganho * 0.35; r.connect(cg); cg.connect(g);
  x.connect(g); lig(g, bus, wet);
}

export function taiko(ctx, bus, t0, o = {}) {
  const { ganho = 0.6, wet = 0.5, f = 82 } = o;
  bumbo(ctx, bus, t0, { ganho, f0: f * 1.5, f1: f * 0.55, dur: 0.9, wet });
  const r = fonteRuido(ctx, 37, t0, t0 + 0.4, 1.7), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 190; bp.Q.value = 0.9;
  const g = ctx.createGain(); g.gain.setValueAtTime(ganho * 0.55, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.35); r.connect(bp); bp.connect(g); lig(g, bus, wet);
}

// Sino de FM (não imita um sino real; timbre metálico sintético).
export function sino(ctx, bus, t0, freq, o = {}) {
  const { ganho = 0.12, dur = 6, wet = 0.6 } = o;
  const car = osc(ctx, 'sine', freq, t0, t0 + dur + 0.2), mod = osc(ctx, 'sine', freq * 3.51, t0, t0 + dur + 0.2), mg = ctx.createGain();
  mg.gain.setValueAtTime(freq * 2.6, t0); mg.gain.exponentialRampToValueAtTime(freq * 0.05, t0 + dur * 0.7); mod.connect(mg); mg.connect(car.frequency);
  const par = osc(ctx, 'sine', freq * 2.76, t0, t0 + dur + 0.2), pa = ctx.createGain(); pa.gain.setValueAtTime(0.25, t0); pa.gain.exponentialRampToValueAtTime(0.0001, t0 + dur * 0.5); par.connect(pa);
  const g = ctx.createGain(); g.gain.setValueAtTime(ganho, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur); car.connect(g); pa.connect(g); lig(g, bus, wet);
}

// Subida de tensão: ruído filtrado que varre para o agudo com crescendo; termina no instante t0 + dur.
export function riser(ctx, bus, t0, dur, o = {}) {
  const { f0 = 300, f1 = 5200, ganho = 0.14, wet = 0.4, semente = 3, tom = true } = o;
  const r = fonteRuido(ctx, semente, t0, t0 + dur + 0.1, semente), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 1.4;
  bp.frequency.setValueAtTime(f0, t0); bp.frequency.exponentialRampToValueAtTime(f1, t0 + dur);
  const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(ganho, t0 + dur * 0.92); g.gain.linearRampToValueAtTime(0.0001, t0 + dur + 0.08);
  r.connect(bp); bp.connect(g); lig(g, bus, wet);
  if (!tom) return;                                       // riser de "ar": sem o tom varrido (fica fora da banda da voz)
  const t = osc(ctx, 'sine', f0 / 2, t0, t0 + dur + 0.1); t.frequency.exponentialRampToValueAtTime(f1 / 6, t0 + dur); const tg = ctx.createGain();
  tg.gain.setValueAtTime(0.0001, t0); tg.gain.exponentialRampToValueAtTime(ganho * 0.4, t0 + dur * 0.92); tg.gain.linearRampToValueAtTime(0.0001, t0 + dur + 0.08); t.connect(tg); lig(tg, bus, wet);
}

// Impacto cinematográfico: golpe grave + subgrave + estalo filtrado + cauda reverberante.
export function impacto(ctx, bus, t0, o = {}) {
  const { ganho = 0.9, variante = 0, wet = 0.6 } = o;
  const f = [44, 40, 36, 48][variante % 4];
  bumbo(ctx, bus, t0, { ganho: ganho * 0.8, f0: f * 3.1, f1: f, dur: 1.4, wet });
  const s = osc(ctx, 'sine', f * 0.9, t0, t0 + 3.2), sg = ctx.createGain(); sg.gain.setValueAtTime(ganho * 0.55, t0); sg.gain.exponentialRampToValueAtTime(0.0001, t0 + 3); s.connect(sg); lig(sg, bus, wet * 0.5);
  const r = fonteRuido(ctx, 41 + variante, t0, t0 + 0.8, variante), lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(5200, t0); lp.frequency.exponentialRampToValueAtTime(260, t0 + 0.7);
  const rg = ctx.createGain(); rg.gain.setValueAtTime(ganho * 0.5, t0); rg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.7); r.connect(lp); lp.connect(rg); lig(rg, bus, wet);
}

export function whoosh(ctx, bus, t0, o = {}) {
  const { ganho = 0.3, dur = 1.3, sobe = true, variante = 0, wet = 0.4 } = o;
  const r = fonteRuido(ctx, 51 + variante, t0, t0 + dur + 0.1, variante * 1.3), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 0.9 + 0.3 * (variante % 3);
  const a = sobe ? 250 : 4200, b = sobe ? 4200 : 250; bp.frequency.setValueAtTime(a, t0); bp.frequency.exponentialRampToValueAtTime(b, t0 + dur);
  const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(ganho, t0 + dur * 0.45); g.gain.linearRampToValueAtTime(0.0001, t0 + dur);
  const p = ctx.createStereoPanner(); p.pan.setValueAtTime(variante % 2 ? 0.7 : -0.7, t0); p.pan.linearRampToValueAtTime(variante % 2 ? -0.7 : 0.7, t0 + dur);
  r.connect(bp); bp.connect(g); g.connect(p); lig(p, bus, wet);
}


// ------------------------------------------------------------------ barramentos e master ---

// Master com barramentos por família (graves, harmonia, melodia, percussão, efeitos), reverberação compartilhada e cadeia final:
// passa-altas 24 Hz (sem energia inaudível), compressor de "cola" suave e limitador de segurança. Cada família devolve um barramento
// do mesmo formato dos instrumentos ({ctx, seco, envio}), então `lig(no, bus, wet)` continua valendo.
export function criarMestre(ctx, saida, { decaimento = 4.2, wet = 0.55, semente = 1, brilho = 0.45 } = {}) {
  const entrada = ctx.createGain();
  const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 24; hp.Q.value = 0.6;
  const cola = ctx.createDynamicsCompressor(); Object.assign(cola, {}); cola.threshold.value = -22; cola.knee.value = 14; cola.ratio.value = 1.8; cola.attack.value = 0.03; cola.release.value = 0.35;
  const lim = ctx.createDynamicsCompressor(); lim.threshold.value = -3; lim.knee.value = 0; lim.ratio.value = 20; lim.attack.value = 0.003; lim.release.value = 0.12;
  entrada.connect(hp); hp.connect(cola); cola.connect(lim); lim.connect(saida);
  const rev = criarBarramento(ctx, entrada, { decaimento, wet, semente, brilho });
  const cadeia = (nos, destino) => { for (let i = 0; i < nos.length - 1; i++) nos[i].connect(nos[i + 1]); nos[nos.length - 1].connect(destino); return nos[0]; };
  const filtro = (tipo, f, q = 0.7, g = 0) => { const b = ctx.createBiquadFilter(); b.type = tipo; b.frequency.value = f; b.Q.value = q; b.gain.value = g; return b; };
  const comp = (limiar, razao, atq, rel, joelho = 6) => { const c = ctx.createDynamicsCompressor(); c.threshold.value = limiar; c.ratio.value = razao; c.attack.value = atq; c.release.value = rel; c.knee.value = joelho; return c; };
  const fam = (nos) => ({ ctx, seco: cadeia(nos, entrada), envio: rev.envio });
  return {
    ctx, entrada, rev,
    graves: fam([filtro('highpass', 35, 0.7), comp(-24, 3, 0.012, 0.25)]),                       // controle de subgraves
    harmonia: fam([filtro('highpass', 38), filtro('peaking', 2800, 0.9, -2.0)]),                 // abre espaço para a voz (2–3 kHz)
    melodia: fam([filtro('highpass', 110), filtro('peaking', 3000, 0.9, -1.5)]),
    percussao: fam([filtro('highpass', 28), comp(-18, 2.2, 0.02, 0.2)]),
    efeitos: fam([filtro('highpass', 60)]),
  };
}

// ------------------------------------------------------------ instrumentos adicionais ---

// Tambor de mão (derbake) sintético: "dum" grave, "tak" seco, "ka" leve. Timbre eletrônico, não imita gravação.
export function darbuka(ctx, bus, t0, o = {}) {
  const { tipo = 'dum', ganho = 0.4, wet = 0.3 } = o;
  if (tipo === 'dum') {
    const x = osc(ctx, 'sine', 170, t0, t0 + 0.4); x.frequency.setValueAtTime(170, t0); x.frequency.exponentialRampToValueAtTime(82, t0 + 0.12);
    const g = ctx.createGain(); g.gain.setValueAtTime(ganho, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.34); x.connect(g); lig(g, bus, wet);
    const r = fonteRuido(ctx, 111, t0, t0 + 0.05, 2.1), lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 900; const rg = ctx.createGain(); rg.gain.setValueAtTime(ganho * 0.4, t0); rg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.05); r.connect(lp); lp.connect(rg); lig(rg, bus, wet);
  } else {
    const r = fonteRuido(ctx, tipo === 'tak' ? 113 : 114, t0, t0 + 0.12, 3.3), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = tipo === 'tak' ? 3300 : 2400; bp.Q.value = 1.6;
    const g = ctx.createGain(); g.gain.setValueAtTime(ganho * (tipo === 'tak' ? 0.8 : 0.45), t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + (tipo === 'tak' ? 0.085 : 0.06)); r.connect(bp); bp.connect(g); lig(g, bus, wet);
    const x = osc(ctx, 'sine', tipo === 'tak' ? 480 : 380, t0, t0 + 0.1), xg = ctx.createGain(); xg.gain.setValueAtTime(ganho * 0.25, t0); xg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.07); x.connect(xg); lig(xg, bus, wet);
  }
}

// Tambor de quadro grave (batida lenta, tom nórdico): seno que cai + ruído grave com cauda mais longa.
export function tamborQuadro(ctx, bus, t0, o = {}) {
  const { ganho = 0.5, wet = 0.5 } = o;
  const x = osc(ctx, 'sine', 108, t0, t0 + 1.2); x.frequency.setValueAtTime(108, t0); x.frequency.exponentialRampToValueAtTime(58, t0 + 0.2);
  const g = ctx.createGain(); g.gain.setValueAtTime(ganho, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.9); x.connect(g); lig(g, bus, wet);
  const r = fonteRuido(ctx, 117, t0, t0 + 0.3, 4.1), lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 520;
  const rg = ctx.createGain(); rg.gain.setValueAtTime(ganho * 0.5, t0); rg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.22); r.connect(lp); lp.connect(rg); lig(rg, bus, wet);
}

// "Lira" sintética: dedilhado aditivo curto e brilhante (parciais ímpares), pensado para arpejos modais.
export function lira(ctx, bus, t0, freq, o = {}) {
  const { ganho = 0.1, dur = 1.8, wet = 0.4, pan = 0 } = o;
  const g = ctx.createGain(); g.gain.value = ganho; const p = ctx.createStereoPanner(); p.pan.value = pan; g.connect(p); lig(p, bus, wet);
  for (const [k, a] of [[1, 1], [2, 0.5], [3, 0.38], [4, 0.2], [5, 0.12]]) {
    const fk = freq * k; if (fk > 9000) break;
    const x = osc(ctx, k % 2 ? 'sine' : 'triangle', fk, t0, t0 + dur + 0.1), ga = ctx.createGain();
    ga.gain.setValueAtTime(0.0001, t0); ga.gain.linearRampToValueAtTime(a, t0 + 0.004); ga.gain.exponentialRampToValueAtTime(0.0001, t0 + dur / (0.7 + 0.5 * k)); x.connect(ga); ga.connect(g);
  }
}

// "Trompa" sintética (grave, com abertura de filtro no ataque) para frases nórdicas; não imita um instrumento real.
export function trompa(ctx, bus, t0, dur, freq, o = {}) {
  const { ganho = 0.08, wet = 0.5 } = o; const fim = t0 + dur + 0.8;
  const x = osc(ctx, 'sawtooth', freq, t0, fim, -4), y = osc(ctx, 'sawtooth', freq, t0, fim, 5);
  const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 1.2; lp.frequency.setValueAtTime(freq * 1.2, t0); lp.frequency.linearRampToValueAtTime(freq * 5.5, t0 + Math.min(0.9, dur * 0.5)); lp.frequency.linearRampToValueAtTime(freq * 2.2, t0 + dur);
  const v = osc(ctx, 'sine', 4.8, t0, fim), vg = ctx.createGain(); vg.gain.value = 6; v.connect(vg); vg.connect(x.detune); vg.connect(y.detune);
  const g = ctx.createGain(); adsr(g.gain, t0, 0.35, 0.25, 0.8, 0.6, ganho, dur); x.connect(lp); y.connect(lp); lp.connect(g); lig(g, bus, wet);
}
