// Partitura da trilha guiada por configuração de composição (composicao.json): um "clima" por seção do documentário, com andamento,
// tonalidade, progressão harmônica, motivos recorrentes (A: a pergunta; B: palheta modal; C: resposta), pulso/percussão, ostinatos e
// uma FORMA de desenvolvimento em "movimentos" (blocos de compassos que mudam harmonia, camadas e intensidade e se repetem em ciclo),
// para que a música evolua com a narração em vez de repetir um laço. Tudo sintetizado em código; nenhuma nota é aleatória:
// só entram graus da tonalidade/acorde/modo definidos na configuração.
//
// Material temático (semitons a partir de Ré4; [semitom, tempo (em batidas) em que entra, duração em batidas]):
//  - A, "a pergunta": Ré–Fá–Lá–Sol (menor) → Ré–Fá#–Lá–Si (maior); versão dórica Ré–Fá–Lá–Si.
//  - B, palheta modal (Ré frígio dominante): Lá–Sol–Fá#–Mib–Ré.
//  - C, "resposta": Lá–Si–Dó#–Ré ascendente (Ré maior), chega à tônica.
import { midi, hz, hzMidi, pad, coro, sub, piano, pluck, palheta, bumbo, taiko, sino, riser, adsr, darbuka, tamborQuadro, lira, trompa } from './sintese.js';

const D4 = midi('D4');
export const MOTIVOS = {
  A: { menor: [[0, 0, 1.5], [3, 2, 1.5], [7, 4, 2], [5, 6.5, 3]], maior: [[0, 0, 1.5], [4, 2, 1.5], [7, 4, 2], [9, 6.5, 3]], dorico: [[0, 0, 1.5], [3, 2, 1.5], [7, 4, 2], [9, 6.5, 3]] },
  C: { maior: [[7, 0, 1.5], [9, 2, 1.5], [11, 4, 1.5], [14, 6, 4]] },
};
export const MOTIVO_B = [[7, 0, 1], [5, 1, 1], [4, 2, 1], [1, 3, 1], [0, 4, 4]];

const N = (xs) => xs.map(hz);
const NOMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];
const nomeMidi = (m) => NOMES[((m % 12) + 12) % 12] + (Math.floor(m / 12) - 1);
// Ganho de cada tipo de camada, calibrado medindo cada camada isolada (equilíbrio espectral: graves não dominam o pad).
export const ESCALA = { pad: 6.3, cordas: 6.0, coro: 5.0, sub: 0.32, pulso: 0.56, ostinato: 3.2, arpejo: 2.0, tema: 1.4, palheta: 2.5, sino: 1.5, riser: 5.0,
  darbuka: 3.6, lira: 3.0, tambor: 1.9, trompa: 3.0, tema2: 1.4 };

export let COMPOSICAO = null;
export function definirComposicao(c) { COMPOSICAO = c; }

function lerp(a, b, k) { return a + (b - a) * k; }

// Divide a seção em segmentos de movimento (ciclo de movimentos; `ocorrencia` desloca o ponto de partida quando a seção volta).
export function segmentar(C, nBarras, ocorrencia = 0) {
  const mv = C.movimentos && C.movimentos.length ? C.movimentos : [{ compassos: 9999 }];
  const segs = []; let b = 0, i = ocorrencia % mv.length;
  while (b < nBarras) { const m = mv[i % mv.length]; const n = Math.max(1, Math.min(m.compassos, nBarras - b)); segs.push({ b0: b, n, m, ciclo: Math.floor((i - (ocorrencia % mv.length)) / mv.length) }); b += n; i++; }
  return segs;
}

// Toca a seção dentro do `ctx`. `buses`: {harmonia, graves, melodia, percussao, efeitos} (de criarMestre) ou um único barramento.
// `t0` = instante (no contexto) em que começa o compasso 1; `dur` = duração da seção.
// opcoes: { ocorrencia, fimFilme: true (cadência final planejada) }; `camadas` (lista) restringe as camadas (calibração).
export function tocarSecao(ctx, buses, clima, bpm, t0, dur, semente = 1, camadas = null, opcoes = {}) {
  const C = COMPOSICAO.climas[clima]; if (!C) throw new Error('clima sem partitura: ' + clima);
  const B = buses.harmonia ? buses : { harmonia: buses, graves: buses, melodia: buses, percussao: buses, efeitos: buses };
  const beat = 60 / bpm, barra = 4 * beat, nBarras = Math.ceil(dur / barra);
  const marcos = [];                                      // eventos musicais relevantes (tempo relativo ao compasso 1)
  const arco = (b) => lerp(C.de ?? 1, C.ate ?? 1, nBarras > 1 ? b / (nBarras - 1) : 1);

  // cadência final planejada (último trecho do filme): IV – V – I, tônica sustentada com decaimento natural
  const F = C.final && opcoes.fimFilme ? C.final : null;
  let nBarrasMov = nBarras, bTonica = null;
  if (F) {
    const tTonica = Math.max((F.compassos + 4) * barra, dur - (F.libera_s + 5.5));           // a cauda (release + reverb) termina antes do fim
    bTonica = Math.max(F.compassos, Math.round(tTonica / barra));
    nBarrasMov = bTonica - (F.compassos - 1);
  }

  for (const sg of segmentar(C, nBarrasMov, opcoes.ocorrencia ?? 0)) {
    const M = sg.m, P = { ...C, ...M };
    const on = (c) => (!camadas || camadas.includes(c)) && (!M.camadas || M.camadas.includes(c));
    const acordesHz = (M.acordes ?? C.acordes).map(N), bpa = M.bpa ?? C.bpa ?? 2;
    const iM = M.intens ?? [1, 1];
    const intens = (b) => Math.min(1.25, lerp(iM[0], iM[1], sg.n > 1 ? (b - sg.b0) / (sg.n - 1) : 1) * arco(b) * (1 + 0.04 * sg.ciclo));
    const fimSeg = Math.min(t0 + dur, t0 + (sg.b0 + sg.n) * barra);
    marcos.push({ t: sg.b0 * barra, tipo: 'movimento', compasso: sg.b0 + 1, compassos: sg.n, camadas: M.camadas ?? null, intens: iM, ciclo: sg.ciclo });
    // 1) camadas harmônicas por acorde (a cada `bpa` compassos dentro do movimento)
    for (let b = sg.b0; b < sg.b0 + sg.n; b += bpa) {
      const iac = Math.floor((b - sg.b0) / bpa) % acordesHz.length;
      marcos.push({ t: b * barra, tipo: 'acorde', compasso: b + 1, notas: (M.acordes ?? C.acordes)[iac] });
      const ac = acordesHz[iac], ts = t0 + b * barra, d = Math.min(bpa * barra, fimSeg - ts) + 0.4 * barra, k = intens(b);
      if (P.pad && on('pad')) pad(ctx, B.harmonia, ts, d, ac, { ...P.pad, ganho: P.pad.ganho * 0.06 * ESCALA.pad * k });
      if (P.cordas && on('cordas')) pad(ctx, B.harmonia, ts, d, ac, { onda: 'sawtooth', desafina: 9, lfo: 0.11, ...P.cordas, ganho: P.cordas.ganho * 0.065 * ESCALA.cordas * k });
      if (P.coro && on('coro') && b - sg.b0 >= (P.coro.entra ?? 0)) coro(ctx, B.harmonia, ts, d, ac.slice(1), { ganho: P.coro.ganho * 0.07 * ESCALA.coro * k });
      if (P.sub && on('sub')) sub(ctx, B.graves, ts, d, hz(P.sub.nota), { ganho: P.sub.ganho * 0.13 * ESCALA.sub * k });
    }
    // 2) pulso rítmico (define a grade de batidas confirmada depois)
    if (P.pulso && on('pulso')) {
      for (let i = sg.b0 * 4; i < (sg.b0 + sg.n) * 4; i++) {
        const bar = Math.floor(i / 4), q = i % 4, ts = t0 + i * beat; if (bar - sg.b0 < (P.pulso.entra ?? 0) || ts > t0 + dur) continue;
        const g = P.pulso.ganho * ESCALA.pulso * intens(bar);
        const marca = (forte) => marcos.push({ t: i * beat, tipo: 'pulso', compasso: bar + 1, tempo: q + 1, forte });
        if (P.pulso.tipo === 'coracao') { if (q === 0) { marca(true); bumbo(ctx, B.percussao, ts, { ganho: g * 0.9, f0: 100, f1: 46, dur: 0.5, wet: 0.35 }); bumbo(ctx, B.percussao, ts + 0.38 * beat, { ganho: g * 0.55, f0: 86, f1: 42, dur: 0.4, wet: 0.35 }); } }
        else if (P.pulso.tipo === 'toque') { marca(q === 0); bumbo(ctx, B.percussao, ts, { ganho: g * (q === 0 ? 1.0 : 0.45), f0: 96, f1: 52, dur: 0.28, wet: 0.2 }); }
        else if (P.pulso.tipo === 'taiko') {
          if (P.pulso.esparso) { if (q === 0 && (bar - sg.b0) % 2 === 0) { marca(true); taiko(ctx, B.percussao, ts, { ganho: g * 1.0, wet: 0.6 }); } }
          else if (q === 0) { marca(true); taiko(ctx, B.percussao, ts, { ganho: g * 1.0, wet: 0.5 }); }
          else if (q === 2) { marca(false); taiko(ctx, B.percussao, ts, { ganho: g * 0.55, f: 94, wet: 0.5 }); }
        }
      }
    }
    // 2b) percussão regional: tambor de mão (Egito, padrão 3+3+2 em colcheias) e tambor de quadro grave (nórdico)
    if (P.darbuka && on('darbuka')) {
      for (let b = sg.b0 + (P.darbuka.entra ?? 0); b < sg.b0 + sg.n; b++) P.darbuka.padrao.forEach((tp, j) => {
        const ts = t0 + b * barra + j * beat / 2; if (!tp || ts > t0 + dur) return;
        if (tp === 'dum') marcos.push({ t: b * barra + j * beat / 2, tipo: 'pulso', compasso: b + 1, tempo: Math.floor(j / 2) + 1, forte: j === 0 });
        darbuka(ctx, B.percussao, ts, { tipo: tp, ganho: 0.07 * ESCALA.darbuka * P.darbuka.ganho * intens(b) });
      });
    }
    if (P.tambor && on('tambor')) {
      for (let i = sg.b0 * 4; i < (sg.b0 + sg.n) * 4; i++) {
        const bar = Math.floor(i / 4), q = i % 4, ts = t0 + i * beat; if (bar - sg.b0 < (P.tambor.entra ?? 0) || ts > t0 + dur || (q !== 0 && q !== 2)) continue;
        marcos.push({ t: i * beat, tipo: 'pulso', compasso: bar + 1, tempo: q + 1, forte: q === 0 });
        tamborQuadro(ctx, B.percussao, ts, { ganho: 0.09 * ESCALA.tambor * P.tambor.ganho * intens(bar) * (q === 0 ? 1 : 0.65) });
      }
    }
    // 3) ostinato (pluck em colcheias/semicolcheias sobre o acorde atual)
    if (P.ostinato && on('ostinato')) {
      const o = P.ostinato, passo = beat / (o.padrao.length / 4);
      for (let b = sg.b0 + (o.entra ?? 0); b < sg.b0 + sg.n; b++) {
        const ac = acordesHz[Math.floor((b - sg.b0) / bpa) % acordesHz.length], k = intens(b);
        o.padrao.forEach((idx, j) => {
          const ts = t0 + b * barra + j * passo; if (ts > t0 + dur) return;
          const f = ac[idx % ac.length] * Math.pow(2, o.oitava);
          pluck(ctx, B.melodia, ts, f, { ganho: 0.06 * ESCALA.ostinato * o.ganho * k * (j % 4 === 0 ? 1.15 : 0.85), dur: 0.9, brilho: 0.9 * k, pan: ((j % 4) - 1.5) * 0.18 });
        });
      }
    }
    // 3b) lira (arpejo modal curto, colcheias) – Grécia
    if (P.lira && on('lira')) {
      for (let b = sg.b0 + (P.lira.entra ?? 0); b < sg.b0 + sg.n; b++) {
        const ac = acordesHz[Math.floor((b - sg.b0) / bpa) % acordesHz.length], k = intens(b);
        P.lira.padrao.forEach((idx, j) => {
          const ts = t0 + b * barra + j * beat / 2; if (ts > t0 + dur - 0.3) return;
          lira(ctx, B.melodia, ts, ac[idx % ac.length] * Math.pow(2, P.lira.oitava), { ganho: 0.06 * ESCALA.lira * P.lira.ganho * k * (j % 4 === 0 ? 1.1 : 0.8), dur: 1.7, pan: ((j % 4) - 1.5) * 0.22 });
        });
      }
    }
    // 4) arpejo lento de piano (contemplativa / encerramento / respiração)
    if (P.arpejo && on('arpejo')) {
      const a = P.arpejo, penta = [0, 2, 4, 7, 9, 12, 14];
      for (let b = sg.b0 + (a.entra ?? 0); b < sg.b0 + sg.n; b++) {
        const ac = acordesHz[Math.floor((b - sg.b0) / bpa) % acordesHz.length];
        for (let j = 0; j < 8 / a.passo * 0.5; j++) {
          const ts = t0 + b * barra + j * a.passo * beat; if (ts > t0 + dur - 1) continue;
          const f = a.penta ? hzMidi(D4 + penta[(b * 3 + j * 2) % penta.length] + 12 * (a.oitava - 1)) : ac[(j + b) % ac.length] * Math.pow(2, a.oitava);
          piano(ctx, B.melodia, ts, f, { vel: a.vel * ESCALA.arpejo * (j % 2 ? 0.8 : 1), dur: 4.5, semente: b * 11 + j });
        }
      }
    }
    // 5) motivos recorrentes: A (pergunta), tema2 = C (resposta)
    for (const [chave, camada] of [['tema', 'tema'], ['tema2', 'tema2']]) {
      const T = P[chave]; if (!T || !on(camada)) continue;
      const mot = (MOTIVOS[T.motivo ?? 'A'] ?? MOTIVOS.A)[T.modo ?? 'maior'] ?? MOTIVOS.A.maior;
      for (let b = sg.b0 + (T.entra ?? 0); b < sg.b0 + sg.n; b += T.cada ?? 8) {
        marcos.push({ t: b * barra, tipo: chave === 'tema' ? 'tema' : 'resposta', compasso: b + 1, instrumento: T.instr, notas: mot.map(([semi]) => nomeMidi(D4 + semi + 12 * (T.oitava ?? 0))) });
        mot.forEach(([semi, pos, dd], j) => {
          const ts = t0 + b * barra + pos * beat; if (ts > t0 + dur - 0.5) return;
          const f = hzMidi(D4 + semi + 12 * (T.oitava ?? 0)), k = intens(b);
          if (T.instr === 'piano') piano(ctx, B.melodia, ts, f, { vel: T.vel * ESCALA.tema * (j === 2 ? 1.1 : 1) * Math.min(1, 0.7 + 0.4 * k), dur: Math.min(6, dd * beat + 2.5), semente: b + j });
          else pad(ctx, B.melodia, ts, dd * beat, [f, f * 2], { onda: 'sawtooth', brilho: 0.7, ataque: 0.25, libera: 1.2, ganho: 0.09 * ESCALA.cordas * T.vel, wet: 0.5, vib: 0.0025 });
        });
      }
    }
    if (P.palheta && on('palheta')) {
      for (let b = sg.b0 + (P.palheta.entra ?? 0); b < sg.b0 + sg.n; b += P.palheta.cada ?? 8) {
        marcos.push({ t: b * barra, tipo: 'palheta', compasso: b + 1, notas: MOTIVO_B.map(([semi]) => nomeMidi(D4 + semi)) });
        MOTIVO_B.forEach(([semi, pos, dd]) => { const ts = t0 + b * barra + pos * beat; if (ts < t0 + dur - 0.5) palheta(ctx, B.melodia, ts, dd * beat * 0.95, hzMidi(D4 + semi), { ganho: 0.07 * ESCALA.palheta * P.palheta.ganho }); });
      }
    }
    if (P.trompa && on('trompa')) {                         // frase B uma oitava abaixo, em notas longas (nórdico)
      for (let b = sg.b0 + (P.trompa.entra ?? 0); b < sg.b0 + sg.n; b += P.trompa.cada ?? 8) {
        marcos.push({ t: b * barra, tipo: 'trompa', compasso: b + 1 });
        MOTIVO_B.forEach(([semi, pos, dd]) => { const ts = t0 + b * barra + pos * beat * 1.4; if (ts < t0 + dur - 1) trompa(ctx, B.harmonia, ts, dd * beat * 1.3, hzMidi(D4 + semi - 12), { ganho: 0.05 * ESCALA.trompa * P.trompa.ganho * intens(b) }); });
      }
    }
    if (P.sino && on('sino')) {
      for (let b = sg.b0 + (P.sino.entra ?? 0); b < sg.b0 + sg.n; b += P.sino.cada ?? 4) { const ts = t0 + b * barra; if (ts < t0 + dur) marcos.push({ t: b * barra, tipo: 'sino', compasso: b + 1 }), sino(ctx, B.melodia, ts, hz(P.sino.nota), { ganho: 0.1 * ESCALA.sino * P.sino.ganho, dur: 7 }); }
    }
  }

  // 6) subida de tensão antes da troca de seção (as últimas `riser` compassos do trecho; só quando o último movimento a admite)
  if (C.riser && (!camadas || camadas.includes('riser')) && !F) {
    const lastM = segmentar(C, nBarras, opcoes.ocorrencia ?? 0).pop().m;
    if (!lastM.camadas || lastM.camadas.includes('riser')) {
      const d = C.riser * barra;
      if (dur > d + 4) marcos.push({ t: dur - d, tipo: 'riser', compasso: Math.round((dur - d) / barra) + 1 }), riser(ctx, B.efeitos, t0 + dur - d, d, { f0: 2200, f1: 9500, tom: false, ganho: 0.1 * ESCALA.riser, semente: semente + 3 });   // varre o "ar" (acima da voz)
    }
  }

  // 7) cadência final: IV – V – I; o tema A (maior) e a resposta C preparam a tônica, que ressoa e decai sem corte
  if (F) {
    const nF = F.compassos;
    F.acordes.forEach((acs, j) => {
      const b = bTonica - (nF - 1) + j, ts = t0 + b * barra, ultimo = j === nF - 1, ac = N(acs);
      const dAc = ultimo ? Math.max(1, (t0 + dur - F.libera_s - 4.5) - ts) : barra + 0.35 * barra;
      marcos.push({ t: b * barra, tipo: ultimo ? 'tonica_final' : 'cadencia', compasso: b + 1, notas: acs });
      pad(ctx, B.harmonia, ts, dAc, ac, { onda: 'sawtooth', brilho: ultimo ? 0.8 : 0.9, ataque: ultimo ? 2.2 : 1.6, libera: ultimo ? F.libera_s : 2.4, ganho: 0.8 * 0.06 * ESCALA.pad * (ultimo ? 0.9 : 0.8), wet: 0.6 });
      if (ultimo) sub(ctx, B.graves, ts, dAc, hz('D2'), { ganho: 0.35 * 0.13 * ESCALA.sub * 0.8, ataque: 2.4, libera: F.libera_s });
    });
    const motA = MOTIVOS.A.maior, motC = MOTIVOS.C.maior;
    [[bTonica - 5, motA, 0.6, 'tema'], [bTonica - 2, motC, 0.66, 'resposta']].forEach(([b, mot, vel, tipo]) => {
      if (b < 0) return; marcos.push({ t: b * barra, tipo, compasso: b + 1 });
      mot.forEach(([semi, pos, dd], j) => { const ts = t0 + b * barra + pos * beat; if (ts < t0 + dur - 6) piano(ctx, B.melodia, ts, hzMidi(D4 + semi), { vel: vel * ESCALA.tema, dur: Math.min(8, dd * beat + 3.5), semente: b + j }); });
    });
  }
  return { compassos: nBarras, beat, barra, marcos };
}
