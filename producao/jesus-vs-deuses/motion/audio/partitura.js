// Partitura da trilha: um "clima" por seção do documentário, com andamento próprio (climas.json), progressão harmônica,
// motivos recorrentes (pergunta, palheta modal), pulso rítmico, ostinatos e crescendos. Tudo sintetizado em código.
//
// Material temático (em semitons a partir de Ré4; [semitom, tempo em que entra, duração em tempos]):
//  - Motivo A, "a pergunta": Ré–Fá–Lá–Sol (modo menor) volta em Ré–Fá#–Lá–Si (maior) quando a resposta cristã se afirma.
//  - Motivo B, palheta modal (Ré frígio dominante) nas civilizações antigas: Lá–Sol–Fá#–Mib–Ré.
import { midi, hz, hzMidi, pad, coro, sub, piano, pluck, palheta, bumbo, taiko, sino, riser, adsr } from './sintese.js';

const D4 = midi('D4');
export const MOTIVO_A = { menor: [[0, 0, 1.5], [3, 2, 1.5], [7, 4, 2], [5, 6.5, 3]], maior: [[0, 0, 1.5], [4, 2, 1.5], [7, 4, 2], [9, 6.5, 3]] };
export const MOTIVO_B = [[7, 0, 1], [5, 1, 1], [4, 2, 1], [1, 3, 1], [0, 4, 4]];

const N = (xs) => xs.map(hz);
// Ganho de cada tipo de camada, calibrado medindo cada camada isolada (equilíbrio espectral: graves não dominam o pad).
export const ESCALA = { pad: 6.3, cordas: 6.0, coro: 5.0, sub: 0.32, pulso: 0.56, ostinato: 3.2, arpejo: 2.0, tema: 1.4, palheta: 2.5, sino: 1.5, riser: 5.0 };

// bpa = compassos por acorde; camadas ativas por clima; "de/ate" = intensidade no início e no fim da seção (crescendo).
export const PARTITURAS = {
  misterio: {
    acordes: [['D2', 'A2', 'D3', 'F3', 'E4'], ['Bb1', 'F2', 'Bb2', 'D3'], ['G1', 'D2', 'G2', 'Bb2'], ['A1', 'E2', 'A2', 'C#3']], bpa: 4,
    pad: { onda: 'sawtooth', brilho: 0.6, ataque: 3.4, libera: 4.5, ganho: 0.9, wet: 0.5 }, sub: { nota: 'D1', ganho: 0.7 },
    pulso: { tipo: 'coracao', ganho: 0.30, entra: 2 }, tema: { instr: 'piano', modo: 'menor', entra: 3, cada: 8, oitava: 0, vel: 0.55 }, riser: 1.4, de: 0.7, ate: 1.0,
  },
  civilizacoes: {
    acordes: [['D2', 'A2', 'D3', 'Eb3'], ['A1', 'E2', 'A2', 'Bb2'], ['G1', 'D2', 'G2', 'Ab2'], ['D2', 'A2', 'C3', 'D3']], bpa: 4,
    pad: { onda: 'sawtooth', brilho: 0.8, ataque: 2.6, libera: 3.5, ganho: 0.85, wet: 0.45 }, sub: { nota: 'D1', ganho: 0.6 },
    pulso: { tipo: 'taiko', ganho: 0.34, entra: 1 }, palheta: { entra: 2, cada: 8, ganho: 0.8 }, riser: 1.2, de: 0.8, ate: 1.0,
  },
  identidade: {
    acordes: [['D3', 'F#3', 'A3', 'E4'], ['B2', 'F#3', 'B3', 'D4'], ['G2', 'D3', 'G3', 'B3'], ['A2', 'E3', 'A3', 'C#4']], bpa: 2,
    pad: { onda: 'sawtooth', brilho: 1.1, ataque: 2.2, libera: 3, ganho: 0.75, wet: 0.4 }, sub: { nota: 'D2', ganho: 0.4 },
    pulso: { tipo: 'toque', ganho: 0.22, entra: 0 }, ostinato: { padrao: [0, 2, 1, 3, 2, 1, 3, 2], oitava: 1, ganho: 0.8, entra: 2 },
    tema: { instr: 'piano', modo: 'maior', entra: 4, cada: 8, oitava: 0, vel: 0.62 }, riser: 1.2, de: 0.75, ate: 1.0,
  },
  contemplativa: {
    acordes: [['C3', 'G3', 'D4', 'E4'], ['A2', 'E3', 'A3', 'C4'], ['F2', 'C3', 'F3', 'G3'], ['G2', 'D3', 'G3', 'B3']], bpa: 4,
    pad: { onda: 'triangle', brilho: 0.9, ataque: 3.2, libera: 4, ganho: 0.9, wet: 0.5 }, sub: { nota: 'C2', ganho: 0.35 },
    pulso: { tipo: 'toque', ganho: 0.12, entra: 0 }, arpejo: { passo: 2, oitava: 1, vel: 0.5, entra: 1 },
    tema: { instr: 'piano', modo: 'maior', entra: 6, cada: 12, oitava: 0, vel: 0.5 }, riser: 0, de: 0.85, ate: 0.95,
  },
  morte: {
    acordes: [['E1', 'B1', 'E2', 'C3'], ['E1', 'B1', 'F#2', 'C3'], ['D1', 'A1', 'D2', 'Bb2']], bpa: 4,
    pad: { onda: 'sawtooth', brilho: 0.4, ataque: 4, libera: 5, ganho: 0.8, wet: 0.55 }, sub: { nota: 'E1', ganho: 0.9 },
    pulso: { tipo: 'coracao', ganho: 0.34, entra: 0 }, sino: { nota: 'E3', cada: 4, ganho: 0.7, entra: 1 }, riser: 1.6, de: 0.8, ate: 1.0,
  },
  crucificacao: {
    acordes: [['D2', 'A2', 'D3', 'Eb3'], ['Bb1', 'F2', 'Bb2', 'B2'], ['D2', 'A2', 'C3', 'Eb3']], bpa: 4,
    cordas: { brilho: 0.5, ataque: 2.4, libera: 4, ganho: 1.0, vib: 0.0028, wet: 0.5 }, sub: { nota: 'D1', ganho: 0.8 },
    pulso: { tipo: 'taiko', ganho: 0.4, entra: 1, esparso: true }, sino: { nota: 'D3', cada: 4, ganho: 0.6, entra: 2 },
    tema: { instr: 'cordas', modo: 'menor', entra: 2, cada: 8, oitava: -1, vel: 0.7 }, riser: 1.6, de: 0.7, ate: 1.0,
  },
  ressurreicao: {
    acordes: [['D3', 'A3', 'F#4', 'D5'], ['G2', 'D3', 'B3', 'G4'], ['A2', 'E3', 'C#4', 'A4'], ['D3', 'A3', 'F#4', 'A4']], bpa: 2,
    cordas: { brilho: 0.85, ataque: 2.0, libera: 3.2, ganho: 0.9, vib: 0.003, wet: 0.5 }, coro: { ganho: 0.9, entra: 4 }, sub: { nota: 'D2', ganho: 0.55 },
    pulso: { tipo: 'taiko', ganho: 0.42, entra: 4 }, ostinato: { padrao: [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 3, 2, 1, 2, 3], oitava: 1, ganho: 0.75, entra: 2, sub: 2 },
    tema: { instr: 'piano', modo: 'maior', entra: 0, cada: 8, oitava: 0, vel: 0.75 }, riser: 1.0, de: 0.45, ate: 1.0,
  },
  comparacao: {
    acordes: [['D2', 'A2', 'D3', 'F3'], ['Bb1', 'F2', 'Bb2', 'D3'], ['F2', 'C3', 'F3', 'A3'], ['A1', 'E2', 'A2', 'C#3']], bpa: 2,
    cordas: { brilho: 0.6, ataque: 1.6, libera: 3, ganho: 0.85, vib: 0.002, wet: 0.45 }, sub: { nota: 'D1', ganho: 0.7 },
    pulso: { tipo: 'taiko', ganho: 0.36, entra: 0 }, ostinato: { padrao: [0, 0, 2, 0, 1, 0, 2, 0], oitava: 1, ganho: 0.7, entra: 0 },
    tema: { instr: 'cordas', modo: 'menor', entra: 4, cada: 8, oitava: 0, vel: 0.7 }, riser: 1.2, de: 0.75, ate: 1.0,
  },
  encerramento: {
    acordes: [['D3', 'A3', 'E4', 'F#4'], ['G2', 'D3', 'A3', 'B3'], ['B2', 'F#3', 'B3', 'D4'], ['A2', 'E3', 'A3', 'C#4']], bpa: 4,
    pad: { onda: 'sawtooth', brilho: 0.9, ataque: 3, libera: 4.5, ganho: 0.8, wet: 0.55 }, sub: { nota: 'D2', ganho: 0.35 },
    pulso: { tipo: 'toque', ganho: 0.10, entra: 0 }, arpejo: { passo: 2, oitava: 1, vel: 0.55, entra: 0, penta: true },
    tema: { instr: 'piano', modo: 'maior', entra: 1, cada: 8, oitava: 0, vel: 0.6 }, riser: 0, de: 1.0, ate: 0.8,
  },
};

// Escala da cena: um instante t (relativo ao início do compasso 1 da seção) para o tempo absoluto do contexto.
function lerp(a, b, k) { return a + (b - a) * k; }

// Toca a seção dentro do `ctx`: `t0` = instante (no contexto) em que começa o compasso 1; `dur` = duração da seção.
export function tocarSecao(ctx, bus, clima, bpm, t0, dur, semente = 1, camadas = null) {
  const P = PARTITURAS[clima]; if (!P) throw new Error('clima sem partitura: ' + clima);
  const on = (c) => !camadas || camadas.includes(c);      // calibração: toca só algumas camadas
  const beat = 60 / bpm, barra = 4 * beat, nBarras = Math.ceil(dur / barra);
  const intens = (b) => lerp(P.de, P.ate, nBarras > 1 ? b / (nBarras - 1) : 1);
  const acordesHz = P.acordes.map(N);
  const marcos = [];                                      // eventos musicais relevantes (tempo relativo ao compasso 1)
  // 1) camadas harmônicas por acorde (a cada `bpa` compassos)
  for (let b = 0; b < nBarras; b += P.bpa) {
    marcos.push({ t: b * barra, tipo: 'acorde', compasso: b + 1 });
    const ac = acordesHz[Math.floor(b / P.bpa) % acordesHz.length], ts = t0 + b * barra, d = Math.min(P.bpa * barra, t0 + dur - ts) + 0.4 * barra, k = intens(b);
    if (P.pad && on('pad')) pad(ctx, bus, ts, d, ac, { ...P.pad, ganho: P.pad.ganho * 0.06 * ESCALA.pad * k });
    if (P.cordas && on('cordas')) pad(ctx, bus, ts, d, ac, { onda: 'sawtooth', desafina: 9, lfo: 0.11, ...P.cordas, ganho: P.cordas.ganho * 0.065 * ESCALA.cordas * k });
    if (P.coro && on('coro') && b >= P.coro.entra) coro(ctx, bus, ts, d, ac.slice(1), { ganho: P.coro.ganho * 0.07 * ESCALA.coro * k });
    if (P.sub && on('sub')) sub(ctx, bus, ts, d, hz(P.sub.nota) * (acordesHz.indexOf(ac) % 2 && clima !== 'morte' ? 1 : 1), { ganho: P.sub.ganho * 0.13 * ESCALA.sub * k });
  }
  // 2) pulso rítmico (define a grade de batidas medida depois)
  if (P.pulso && on('pulso')) {
    for (let i = 0; i < nBarras * 4; i++) {
      const bar = Math.floor(i / 4), q = i % 4, ts = t0 + i * beat; if (bar < P.pulso.entra || ts > t0 + dur) continue;
      const g = P.pulso.ganho * ESCALA.pulso * intens(bar);
      const marca = (forte) => marcos.push({ t: i * beat, tipo: 'pulso', compasso: bar + 1, tempo: q + 1, forte });
      if (P.pulso.tipo === 'coracao') { if (q === 0) { marca(true); bumbo(ctx, bus, ts, { ganho: g * 0.9, f0: 100, f1: 46, dur: 0.5, wet: 0.35 }); bumbo(ctx, bus, ts + 0.38 * beat, { ganho: g * 0.55, f0: 86, f1: 42, dur: 0.4, wet: 0.35 }); } }
      else if (P.pulso.tipo === 'toque') { marca(q === 0); bumbo(ctx, bus, ts, { ganho: g * (q === 0 ? 1.0 : 0.45), f0: 96, f1: 52, dur: 0.28, wet: 0.2 }); }
      else if (P.pulso.tipo === 'taiko') {
        if (P.pulso.esparso) { if (q === 0 && bar % 2 === 0) { marca(true); taiko(ctx, bus, ts, { ganho: g * 1.0, wet: 0.6 }); } }
        else if (q === 0) { marca(true); taiko(ctx, bus, ts, { ganho: g * 1.0, wet: 0.5 }); }
        else if (q === 2) { marca(false); taiko(ctx, bus, ts, { ganho: g * 0.55, f: 94, wet: 0.5 }); }
      }
    }
  }
  // 3) ostinato (arpejo em colcheias/semicolcheias sobre o acorde atual)
  if (P.ostinato && on('ostinato')) {
    const o = P.ostinato, passo = beat / (o.padrao.length / 4);
    for (let b = o.entra; b < nBarras; b++) {
      const ac = acordesHz[Math.floor(b / P.bpa) % acordesHz.length], k = intens(b);
      o.padrao.forEach((idx, j) => {
        const ts = t0 + b * barra + j * passo; if (ts > t0 + dur) return;
        const f = ac[idx % ac.length] * Math.pow(2, o.oitava);
        pluck(ctx, bus, ts, f, { ganho: 0.06 * ESCALA.ostinato * o.ganho * k * (j % 4 === 0 ? 1.15 : 0.85), dur: 0.9, brilho: 0.9 * k, pan: ((j % 4) - 1.5) * 0.18 });
      });
    }
  }
  // 4) arpejo lento de piano (contemplativa / encerramento)
  if (P.arpejo && on('arpejo')) {
    const a = P.arpejo, penta = [0, 2, 4, 7, 9, 12, 14];
    for (let b = a.entra; b < nBarras; b++) {
      const ac = acordesHz[Math.floor(b / P.bpa) % acordesHz.length];
      for (let j = 0; j < 8 / a.passo * 0.5; j++) {
        const ts = t0 + b * barra + j * a.passo * beat; if (ts > t0 + dur - 1) continue;
        const f = a.penta ? hzMidi(D4 + penta[(b * 3 + j * 2) % penta.length] + 12 * (a.oitava - 1)) : ac[(j + b) % ac.length] * Math.pow(2, a.oitava);
        piano(ctx, bus, ts, f, { vel: a.vel * ESCALA.arpejo * (j % 2 ? 0.8 : 1), dur: 4.5, semente: b * 11 + j });
      }
    }
  }
  // 5) motivos recorrentes
  if (P.tema && on('tema')) {
    const T = P.tema, mot = MOTIVO_A[T.modo];
    for (let b = T.entra; b < nBarras; b += T.cada) {
      marcos.push({ t: b * barra, tipo: 'tema', compasso: b + 1 });
      mot.forEach(([semi, pos, dd], j) => {
        const ts = t0 + b * barra + pos * beat; if (ts > t0 + dur - 0.5) return;
        const f = hzMidi(D4 + semi + 12 * T.oitava);
        if (T.instr === 'piano') piano(ctx, bus, ts, f, { vel: T.vel * ESCALA.tema * (j === 2 ? 1.1 : 1), dur: Math.min(6, dd * beat + 2.5), semente: b + j });
        else pad(ctx, bus, ts, dd * beat, [f, f * 2], { onda: 'sawtooth', brilho: 0.7, ataque: 0.25, libera: 1.2, ganho: 0.09 * ESCALA.cordas * T.vel, wet: 0.5, vib: 0.0025 });
      });
    }
  }
  if (P.palheta && on('palheta')) {
    for (let b = P.palheta.entra; b < nBarras; b += P.palheta.cada) {
      marcos.push({ t: b * barra, tipo: 'palheta', compasso: b + 1 });
      MOTIVO_B.forEach(([semi, pos, dd]) => { const ts = t0 + b * barra + pos * beat; if (ts < t0 + dur - 0.5) palheta(ctx, bus, ts, dd * beat * 0.95, hzMidi(D4 + semi), { ganho: 0.07 * ESCALA.palheta * P.palheta.ganho }); });
    }
  }
  if (P.sino && on('sino')) {
    for (let b = P.sino.entra; b < nBarras; b += P.sino.cada) { const ts = t0 + b * barra; if (ts < t0 + dur) marcos.push({ t: b * barra, tipo: 'sino', compasso: b + 1 }), sino(ctx, bus, ts, hz(P.sino.nota), { ganho: 0.1 * ESCALA.sino * P.sino.ganho, dur: 7 }); }
  }
  // 6) subida de tensão antes da troca de seção (as últimas `riser` batidas*4 do trecho)
  if (P.riser && on('riser')) { const d = P.riser * barra; if (dur > d + 4) marcos.push({ t: dur - d, tipo: 'riser', compasso: Math.round((dur - d) / barra) + 1 }), riser(ctx, bus, t0 + dur - d, d, { ganho: 0.1 * ESCALA.riser, semente: semente + 3 }); }
  return { compassos: nBarras, beat, barra, marcos };
}
