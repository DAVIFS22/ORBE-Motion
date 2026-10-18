// Efeitos pontuais e ambiências, sintetizados com a Web Audio API. As ambiências são "ambientação sintética" e nunca
// são apresentadas como gravações históricas nem como o som de acontecimentos bíblicos.
import { mulberry32, hash32, rngFor } from '../engine/rng.js';
import { SR, hz, hzMidi, midi, bumbo, taiko, sino, riser, impacto, whoosh, piano, fonteRuido, adsr, sub, lig } from './sintese.js';

// Pico-alvo de cada tipo de efeito, em dB relativos ao nível (RMS) da narração.
export const ALVOS_PICO = { impacto: -4, whoosh: -9, nota: -7, passos: -14, tecido: -20, pergaminho: -16, revelar: -8, ping: -14, faixa: -15, rota: -13 };

function osc(ctx, tipo, f, t0, t1) { const o = ctx.createOscillator(); o.type = tipo; o.frequency.value = f; o.start(t0); o.stop(t1); return o; }

export function tocarEvento(ctx, bus, tipo, t0, variante = 0, dur = 0) {
  const v = variante;
  if (tipo === 'impacto') {
    if (t0 > 0.7) riser(ctx, bus, t0 - 0.65, 0.65, { f0: 200, f1: 3200, ganho: 0.1, semente: 5 + v });
    impacto(ctx, bus, t0, { variante: v, ganho: 0.9 });
  } else if (tipo === 'whoosh') {
    whoosh(ctx, bus, t0, { variante: v, sobe: v % 2 === 0, dur: 1.0 + 0.2 * (v % 3), ganho: 0.3 });
  } else if (tipo === 'nota') {
    const f = [hz('D5'), hz('F#5'), hz('A5'), hz('B4')][v % 4];
    piano(ctx, bus, t0, f, { vel: 0.85, dur: 5, wet: 0.6, semente: 70 + v });
  } else if (tipo === 'passos') {
    const n = Math.max(2, Math.floor((dur || 5) / 0.62));
    for (let i = 0; i < n; i++) {
      const r = rngFor(900 + v, i), ts = t0 + i * 0.62 + (r() - 0.5) * 0.05;
      const s = fonteRuido(ctx, 61 + (i % 3), ts, ts + 0.14, i), lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 380 + 160 * r();
      const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, ts); g.gain.linearRampToValueAtTime(0.5 * (0.7 + 0.3 * r()), ts + 0.012); g.gain.exponentialRampToValueAtTime(0.0001, ts + 0.12);
      const p = ctx.createStereoPanner(); p.pan.value = (r() - 0.5) * 0.5; s.connect(lp); lp.connect(g); g.connect(p); lig(p, bus, 0.15);
    }
  } else if (tipo === 'tecido') {
    const s = fonteRuido(ctx, 66 + v, t0, t0 + 0.7, v), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 0.8; bp.frequency.setValueAtTime(900, t0); bp.frequency.exponentialRampToValueAtTime(2400, t0 + 0.5);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(0.4, t0 + 0.18); g.gain.linearRampToValueAtTime(0.0001, t0 + 0.6); s.connect(bp); bp.connect(g); lig(g, bus, 0.1);
  } else if (tipo === 'pergaminho') {
    const s = fonteRuido(ctx, 71 + v, t0, t0 + 1.0, v), hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 2600;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t0); const r = rngFor(950 + v, 1);
    for (let i = 0; i < 26; i++) { const ts = t0 + i * 0.035 + r() * 0.02; g.gain.setValueAtTime(0.0001, ts); g.gain.linearRampToValueAtTime(0.25 * (0.4 + r()), ts + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, ts + 0.03); }
    s.connect(hp); hp.connect(g); lig(g, bus, 0.15);
  } else if (tipo === 'revelar') {                                  // nome/ficha entra: golpe grave suave + ar
    bumbo(ctx, bus, t0, { ganho: 0.55, f0: 74, f1: 38, dur: 1.2, wet: 0.45 });
    const s = fonteRuido(ctx, 81 + v, t0 - 0.05, t0 + 0.5, v), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 1400; bp.Q.value = 0.7;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t0 - 0.05); g.gain.linearRampToValueAtTime(0.12, t0 + 0.05); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.45); s.connect(bp); bp.connect(g); lig(g, bus, 0.3);
  } else if (tipo === 'ping') {                                      // local/data marcado no mapa ou na linha do tempo
    sino(ctx, bus, t0, [hz('A5'), hz('E6'), hz('D6')][v % 3], { ganho: 0.12, dur: 2.6, wet: 0.55 });
  } else if (tipo === 'faixa') {
    whoosh(ctx, bus, t0, { variante: v + 1, sobe: true, dur: 0.6, ganho: 0.18, wet: 0.3 });
  } else if (tipo === 'rota') {
    const o = osc(ctx, 'sine', 330, t0, t0 + 1.2); o.frequency.setValueAtTime(330, t0); o.frequency.exponentialRampToValueAtTime(880, t0 + 0.9);
    const g = ctx.createGain(); adsr(g.gain, t0, 0.05, 0.3, 0.4, 0.4, 0.2, 0.8); o.connect(g); lig(g, bus, 0.5);
  }
}

// ------------------------------------------------------------------------------ ambiências ---

function vento(ctx, bus, t0, dur, { centro = 600, q = 0.9, rajada = 0.3, ganho = 0.5, chiado = 0, semente = 1, rampa = null }) {
  const fim = t0 + dur + 0.2, s = fonteRuido(ctx, 91 + semente, t0, fim, semente * 1.7);
  const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = centro; bp.Q.value = q;
  for (const [i, f] of [0.05, 0.11, 0.23].entries()) { const l = osc(ctx, 'sine', f * (0.8 + 0.1 * semente), t0, fim), lg = ctx.createGain(); lg.gain.value = centro * rajada * (0.5 / (i + 1)); l.connect(lg); lg.connect(bp.frequency); }
  const g = ctx.createGain(); g.gain.value = ganho;
  const lv = osc(ctx, 'sine', 0.07 * (1 + 0.2 * semente), t0, fim), lvg = ctx.createGain(); lvg.gain.value = ganho * 0.45; lv.connect(lvg); lvg.connect(g.gain);
  if (rampa) { g.gain.setValueAtTime(ganho * rampa[0], t0); g.gain.linearRampToValueAtTime(ganho * rampa[1], t0 + dur); }
  s.connect(bp); bp.connect(g); lig(g, bus, 0.25);
  if (chiado) { const h = fonteRuido(ctx, 99, t0, fim, 3), hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 4200; const hg = ctx.createGain(); hg.gain.value = chiado; h.connect(hp); hp.connect(hg); hg.connect(g); }
}

function drone(ctx, bus, t0, dur, nota, { ganho = 0.3, bat = 0.35, quinta = false }) {
  const f = hz(nota), fim = t0 + dur + 0.2, g = ctx.createGain(); g.gain.value = ganho;
  for (const [d, a] of [[0, 1], [bat, 0.9]]) { const o = osc(ctx, 'sine', f + d, t0, fim), og = ctx.createGain(); og.gain.value = a; o.connect(og); og.connect(g); }
  const tr = osc(ctx, 'triangle', f * 2, t0, fim), tg = ctx.createGain(); tg.gain.value = 0.18; tr.connect(tg); tg.connect(g);
  if (quinta) { const q = osc(ctx, 'sine', f * 1.5, t0, fim), qg = ctx.createGain(); qg.gain.value = 0.22; q.connect(qg); qg.connect(g); }
  const l = osc(ctx, 'sine', 0.06, t0, fim), lg = ctx.createGain(); lg.gain.value = ganho * 0.35; l.connect(lg); lg.connect(g.gain); lig(g, bus, 0.3);
}

function passaros(ctx, bus, t0, dur, { densidade = 0.12, ganho = 0.25, semente = 1 }) {
  const r = mulberry32(hash32(semente, 1717)); let t = t0 + 1 + r() * 3;
  while (t < t0 + dur - 1) {
    const f0 = 2300 + 1500 * r(), n = 2 + Math.floor(r() * 3);
    for (let k = 0; k < n; k++) {
      const ts = t + k * (0.09 + 0.03 * r()), o = osc(ctx, 'sine', f0, ts, ts + 0.12); o.frequency.setValueAtTime(f0, ts); o.frequency.exponentialRampToValueAtTime(f0 * (1.2 + 0.5 * r()), ts + 0.07);
      const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, ts); g.gain.linearRampToValueAtTime(ganho * (0.5 + 0.5 * r()), ts + 0.015); g.gain.exponentialRampToValueAtTime(0.0001, ts + 0.1);
      const p = ctx.createStereoPanner(); p.pan.value = (r() - 0.5) * 1.4; o.connect(g); g.connect(p); lig(p, bus, 0.45);
    }
    t += (1 / densidade) * (0.6 + 0.9 * r());
  }
}

function murmurio(ctx, bus, t0, dur, { ganho = 0.3, semente = 1 }) {
  const r = mulberry32(hash32(semente, 2121));
  for (const [i, f] of [420, 760, 1250].entries()) {
    const s = fonteRuido(ctx, 111 + i, t0, t0 + dur + 0.2, i * 2.3), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = f; bp.Q.value = 3;
    const g = ctx.createGain(); g.gain.value = 0.0001; let t = t0;
    while (t < t0 + dur) { const d = 0.15 + r() * 0.5; g.gain.linearRampToValueAtTime(ganho * (0.15 + 0.85 * r()) / (i + 1), t + d * 0.4); g.gain.linearRampToValueAtTime(0.0001, t + d); t += d + 0.05 + r() * 0.4; }
    const p = ctx.createStereoPanner(); p.pan.value = (i - 1) * 0.5; s.connect(bp); bp.connect(g); g.connect(p); lig(p, bus, 0.35);
  }
}

function texturaCrescente(ctx, bus, t0, dur, { ganho = 0.4 }) {
  const fim = t0 + dur + 0.2, s = fonteRuido(ctx, 131, t0, fim, 2), bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 1.1;
  bp.frequency.setValueAtTime(380, t0); bp.frequency.exponentialRampToValueAtTime(3200, t0 + dur);
  const g = ctx.createGain(); g.gain.setValueAtTime(ganho * 0.1, t0); g.gain.linearRampToValueAtTime(ganho, t0 + dur); s.connect(bp); bp.connect(g); lig(g, bus, 0.4);
  for (const [i, m] of [74, 81, 86, 90].entries()) {                        // brilho em Ré maior surgindo aos poucos
    const o = osc(ctx, 'sine', hzMidi(m), t0 + dur * (0.25 + 0.12 * i), fim), og = ctx.createGain(); og.gain.setValueAtTime(0.0001, t0 + dur * (0.25 + 0.12 * i)); og.gain.linearRampToValueAtTime(ganho * 0.07, t0 + dur); o.connect(og); lig(og, bus, 0.6);
  }
}

// Nome da ambiência -> síntese. `offset` em dB aproxima o equilíbrio relativo usado antes (templo/graves mais presentes).
export const AMBIENCIAS = {
  vento_profundo: (c, b, t0, d, s) => { vento(c, b, t0, d, { centro: 260, q: 0.8, rajada: 0.35, ganho: 0.6, semente: s }); drone(c, b, t0, d, 'D1', { ganho: 0.1, quinta: true }); },
  ressonancia_templo: (c, b, t0, d, s) => { drone(c, b, t0, d, 'D2', { ganho: 0.28, bat: 0.4, quinta: true }); vento(c, b, t0, d, { centro: 420, q: 2.4, rajada: 0.1, ganho: 0.18, semente: s + 1 }); },
  ambiencia_templo: (c, b, t0, d, s) => { drone(c, b, t0, d, 'A1', { ganho: 0.22, bat: 0.3 }); vento(c, b, t0, d, { centro: 520, q: 1.8, rajada: 0.15, ganho: 0.25, semente: s }); },
  vento_ruinas: (c, b, t0, d, s) => vento(c, b, t0, d, { centro: 720, q: 1.2, rajada: 0.5, ganho: 0.55, chiado: 0.03, semente: s }),
  aldeia: (c, b, t0, d, s) => { murmurio(c, b, t0, d, { ganho: 0.35, semente: s }); passaros(c, b, t0, d, { densidade: 0.1, ganho: 0.14, semente: s }); },
  vento_suave: (c, b, t0, d, s) => vento(c, b, t0, d, { centro: 900, q: 0.7, rajada: 0.25, ganho: 0.35, semente: s }),
  natureza_discreta: (c, b, t0, d, s) => { passaros(c, b, t0, d, { densidade: 0.18, ganho: 0.2, semente: s }); vento(c, b, t0, d, { centro: 800, q: 0.7, rajada: 0.2, ganho: 0.2, semente: s + 2 }); },
  vento_deserto: (c, b, t0, d, s) => vento(c, b, t0, d, { centro: 520, q: 0.9, rajada: 0.3, ganho: 0.5, chiado: 0.05, semente: s }),
  grave_atmosferico: (c, b, t0, d, s) => drone(c, b, t0, d, 'E1', { ganho: 0.45, bat: 0.5, quinta: true }),
  vento_crescente: (c, b, t0, d, s) => vento(c, b, t0, d, { centro: 640, q: 1.0, rajada: 0.4, ganho: 0.6, chiado: 0.04, semente: s, rampa: [0.3, 1.0] }),
  grave_sutil: (c, b, t0, d, s) => drone(c, b, t0, d, 'D1', { ganho: 0.3, bat: 0.35 }),
  textura_crescente: (c, b, t0, d, s) => texturaCrescente(c, b, t0, d, { ganho: 0.5 }),
};
export const OFFSET_AMB = { ressonancia_templo: 3.0, grave_atmosferico: -3.0, grave_sutil: -3.0, ambiencia_templo: -1.0 };
