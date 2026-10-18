// Tipografia cinética editorial: uma frase curta da narração, palavra por palavra, no instante em que é dita.
// Fundo: imagem (still 3D ou cenário) com câmera lenta e, opcionalmente, um corte interno para um enquadramento mais fechado.
// params: { imagem, lado:'esq'|'dir', eyebrow, linhas:[[{txt, t, enfase}]], aspas, nota, camera:{s0,s1,x0,x1,y0,y1,corte:{t,s,x,y}}, batidas }
// Cada palavra é uma janela de corte; o texto sobe de baixo para dentro dela (outExpo). A ênfase é cor + sublinhado que se desenha.
import { el, canvas, carregarImagem, COR, FONTE } from '../engine/ui.js';
import { prog, outExpo, inCubic, smooth, lerp, clamp01 } from '../engine/ease.js';
import { criarCamadaFinal } from '../engine/atmos.js';

const W = 1920, H = 1080;
const LARG_MAX = 1060, MARGEM = 150;

function medir(texto, fonte) {
  const c = document.createElement('canvas').getContext('2d');
  c.font = fonte;
  return c.measureText(texto).width;
}

export const frase = {
  async build(palco, spec) {
    const P = spec.params, D = spec.dur;
    const dir = P.lado === 'dir';
    const raiz = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', background: COR.tinta, overflow: 'hidden' }, palco);

    // ---------------------------------------------------------------- fundo ---
    const cv = canvas(W, H, {}, raiz); const g = cv.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    const img = P.imagem ? await carregarImagem(P.imagem) : null;
    const cam = Object.assign({ s0: 1.03, s1: 1.09, x0: 0, x1: dir ? 26 : -26, y0: 0, y1: -8 }, P.camera || {});
    const scrim = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px',
      background: `linear-gradient(${dir ? 270 : 90}deg, rgba(5,6,9,0.80) 0%, rgba(5,6,9,0.62) 30%, rgba(5,6,9,0.18) 56%, rgba(5,6,9,0) 70%)` }, raiz);

    // ---------------------------------------------------------- tipografia ---
    const linhas = (P.linhas || []).filter((l) => l.length);
    const todas = linhas.flat();
    todas.forEach((w, i) => { if (w.t == null) w.t = 0.5 + i * Math.max(0.28, (D * 0.62) / Math.max(1, todas.length)); });
    let tam = 104;
    const larguraPalavra = (txt, s) => medir(txt.toUpperCase(), `700 ${s}px ${FONTE.display}`) + s * 0.03 * txt.length;
    const espacoEm = (s) => medir(' ', `700 ${s}px ${FONTE.display}`) + s * 0.08;
    const larguraLinha = (l, s) => l.reduce((n, w) => n + larguraPalavra(w.txt, s), 0) + espacoEm(s) * (l.length - 1);
    while (tam > 60 && Math.max(...linhas.map((l) => larguraLinha(l, tam))) > LARG_MAX) tam -= 2;
    const alt = Math.round(tam * 1.18);
    const blocoH = linhas.length * alt;
    const temEb = !!P.eyebrow;
    const y0 = Math.round(H * 0.5 - blocoH / 2 + (temEb ? 30 : 0));
    const espaco = espacoEm(tam);

    const caixa = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px' }, raiz);
    const palavras = [];
    linhas.forEach((l, li) => {
      const larg = larguraLinha(l, tam);
      let x = dir ? W - MARGEM - larg : MARGEM;
      for (const w of l) {
        const lw = larguraPalavra(w.txt, tam);
        const jan = el('div', { left: Math.round(x) + 'px', top: y0 + li * alt + 'px', width: Math.ceil(lw + 6) + 'px', height: alt + 'px', overflow: 'hidden' }, caixa);
        const t = el('div', { left: '0', top: '0', whiteSpace: 'nowrap', font: `700 ${tam}px/${alt}px ${FONTE.display}`, letterSpacing: '0.03em',
          color: w.enfase ? COR.ouro : COR.marfim }, jan, w.txt.toUpperCase());
        const sub = w.enfase ? el('div', { left: Math.round(x) + 'px', top: y0 + li * alt + Math.round(alt * 0.9) + 'px', height: '3px', width: '0px', background: COR.ouro }, caixa) : null;
        palavras.push({ w, jan, t, sub, lw, li });
        x += lw + espaco;
      }
    });

    // aspas de abertura (citação direta), discretas
    // aspas "penduradas" à esquerda da primeira linha (fora do bloco de texto)
    const larg0 = larguraLinha(linhas[0] || [], tam);
    const aspas = P.aspas ? el('div', { left: Math.round(dir ? W - MARGEM - larg0 - tam * 0.78 : MARGEM - tam * 0.78) + 'px', top: y0 + Math.round(tam * 0.02) + 'px',
      font: `700 ${Math.round(tam * 1.25)}px/1 ${FONTE.display}`, color: COR.ouro, opacity: '0' }, caixa, '“') : null;

    // sobrancelha: régua + referência
    let eb = null, regua = null;
    if (temEb) {
      const yEb = y0 - 74;
      regua = el('div', { left: (dir ? W - MARGEM - 64 : MARGEM) + 'px', top: yEb + 19 + 'px', height: '2px', width: '0px', background: COR.ouro }, caixa);
      const janEb = el('div', { left: (dir ? MARGEM : MARGEM + 88) + 'px', top: yEb + 'px', width: (dir ? W - 2 * MARGEM - 88 : 1200) + 'px', height: '40px', overflow: 'hidden' }, caixa);
      eb = el('div', { left: '0', top: '0', width: '100%', textAlign: dir ? 'right' : 'left', whiteSpace: 'nowrap', font: `600 28px/40px ${FONTE.ui}`, letterSpacing: '0.24em', color: COR.ouro }, janEb, P.eyebrow.toUpperCase());
    }
    // nota (fonte, tradução ou "paráfrase da narração")
    let nota = null, reguaNota = null;
    if (P.nota) {
      const yN = y0 + blocoH + 34;
      reguaNota = el('div', { left: (dir ? W - MARGEM - 420 : MARGEM) + 'px', top: yN + 'px', height: '1px', width: '0px', background: 'rgba(239,230,210,0.45)' }, caixa);
      const janN = el('div', { left: (dir ? MARGEM : MARGEM) + 'px', top: yN + 14 + 'px', width: (W - 2 * MARGEM) + 'px', height: '40px', overflow: 'hidden' }, caixa);
      nota = el('div', { left: '0', top: '0', width: '100%', textAlign: dir ? 'right' : 'left', whiteSpace: 'nowrap', font: `500 27px/40px ${FONTE.ui}`, color: 'rgba(239,230,210,0.78)' }, janN, P.nota);
    }
    const final = criarCamadaFinal(raiz, { semente: spec.seed, poeira: { n: 0, brilho: 0 }, vinheta: 0.42, grao: 0.05 });

    const t1 = Math.min(...todas.map((w) => w.t));
    const tUlt = Math.max(...todas.map((w) => w.t));
    const tEb = Math.max(0.15, t1 - 0.55), tNota = Math.min(D - 1.4, tUlt + 0.5);
    const saida = Math.max(D - 0.62, tUlt + 0.9);                     // com pouco tempo depois da fala, o texto fica até o corte

    function fundo(t) {
      g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
      g.fillStyle = COR.tinta; g.fillRect(0, 0, W, H);
      if (img) {
        let s, x, y;
        const c = cam.corte;
        if (c && t >= c.t) {                       // corte seco para um enquadramento mais fechado, sincronizado com a fala
          const k = smooth((t - c.t) / Math.max(0.5, D - c.t));
          s = c.s * (1 + 0.03 * k); x = (c.x ?? 0) + (dir ? 10 : -10) * k; y = (c.y ?? 0) - 4 * k;
        } else {
          const k = smooth(t / D);
          s = lerp(cam.s0, cam.s1, k); x = lerp(cam.x0, cam.x1, k); y = lerp(cam.y0, cam.y1, k);
        }
        const esc = Math.max(W / img.width, H / img.height) * s;
        const iw = img.width * esc, ih = img.height * esc;
        g.drawImage(img, (W - iw) / 2 + x, (H - ih) / 2 + y, iw, ih);
      }
      g.restore();
    }

    return {
      eventos: [],
      seek(t) {
        fundo(t);
        const sai = (atraso) => prog(t, saida + atraso, saida + atraso + 0.42, inCubic);
        for (const p of palavras) {
          const e = prog(t, p.w.t - 0.06, p.w.t + 0.5, outExpo);
          const s = sai(0.025 * p.li);
          p.t.style.transform = `translateY(${((1 - e) * 104 - s * 104).toFixed(2)}%)`;
          p.t.style.opacity = String(clamp01(e * 1.6));
          if (p.sub) {
            const k = prog(t, p.w.t + 0.35, p.w.t + 0.95, outExpo) * (1 - sai(0));
            p.sub.style.width = (p.lw * k).toFixed(1) + 'px';
            if (dir) p.sub.style.transform = `translateX(${(p.lw * (1 - k)).toFixed(1)}px)`;
          }
        }
        if (aspas) {
          const k = prog(t, t1 - 0.1, t1 + 0.5, outExpo) * (1 - sai(0));
          aspas.style.opacity = (0.55 * k).toFixed(3);
          aspas.style.transform = `translateY(${((1 - k) * 18).toFixed(1)}px)`;
        }
        if (eb) {
          const k = prog(t, tEb, tEb + 0.6, outExpo), s = sai(0);
          regua.style.width = (64 * k * (1 - s)).toFixed(1) + 'px';
          if (dir) regua.style.transform = `translateX(${(64 * (1 - k * (1 - s))).toFixed(1)}px)`;
          eb.style.transform = `translateY(${((1 - prog(t, tEb + 0.1, tEb + 0.6, outExpo)) * 100 - s * 100).toFixed(1)}%)`;
        }
        if (nota) {
          const k = prog(t, tNota, tNota + 0.7, outExpo), s = sai(0.05);
          reguaNota.style.width = (420 * k * (1 - s)).toFixed(1) + 'px';
          if (dir) reguaNota.style.transform = `translateX(${(420 * (1 - k * (1 - s))).toFixed(1)}px)`;
          nota.style.transform = `translateY(${((1 - prog(t, tNota + 0.12, tNota + 0.7, outExpo)) * 100 - s * 100).toFixed(1)}%)`;
        }
        final.desenhar(t, 1);
      },
    };
  },
};
