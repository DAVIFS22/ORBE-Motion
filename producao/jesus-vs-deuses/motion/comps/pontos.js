// Diagrama dos cinco pontos (seção de comparação): uma régua vetorial com cinco nós numerados. O ponto ativo acende quando o
// narrador diz a palavra-chave; os anteriores ficam marcados; no resumo ("todos"), os cinco entram em sequência.
// params: { imagem, ativo: 1..5 | 0 (todos), itens:[{rotulo, ref}], t_ativo, eyebrow, titulo?, sub? }
import { el, canvas, carregarImagem, COR, FONTE } from '../engine/ui.js';
import { prog, outExpo, outCubic, inCubic, smooth, mola, lerp, clamp01 } from '../engine/ease.js';
import { criarCamadaFinal } from '../engine/atmos.js';

const W = 1920, H = 1080, X0 = 230, X1 = 1690, YR = 812;
const NS = 'http://www.w3.org/2000/svg';
function no(tag, attrs, pai) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (pai) pai.appendChild(e); return e; }

export const pontos = {
  async build(palco, spec) {
    const P = spec.params, D = spec.dur;
    const itens = P.itens || [], n = itens.length || 5, ativo = P.ativo ?? 0;
    const tA = Math.min(Math.max(P.t_ativo ?? 0.9, 0.4), D - 1.2);
    const raiz = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', background: COR.tinta, overflow: 'hidden' }, palco);
    const cv = canvas(W, H, {}, raiz); const g = cv.getContext('2d'); g.imageSmoothingQuality = 'high';
    const img = P.imagem ? await carregarImagem(P.imagem) : null;
    el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px',
      background: 'linear-gradient(90deg, rgba(5,6,9,0.78) 0%, rgba(5,6,9,0.5) 45%, rgba(5,6,9,0.15) 75%), linear-gradient(0deg, rgba(5,6,9,0.85) 0%, rgba(5,6,9,0.0) 42%)' }, raiz);

    const xs = Array.from({ length: n }, (_, i) => X0 + (X1 - X0) * (i / (n - 1)));
    const svg = no('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, null);
    Object.assign(svg.style, { position: 'absolute', left: '0', top: '0', overflow: 'visible' }); raiz.appendChild(svg);
    const base = no('line', { x1: X0, x2: X1, y1: YR, y2: YR, stroke: 'rgba(239,230,210,0.35)', 'stroke-width': 2 }, svg);
    const prog1 = no('line', { x1: X0, x2: X0, y1: YR, y2: YR, stroke: COR.ouro, 'stroke-width': 4 }, svg);
    const nos = itens.map((it, i) => {
      const gr = no('g', {}, svg);
      const c = no('circle', { cx: xs[i], cy: YR, r: 30, fill: COR.tinta, stroke: COR.ouro, 'stroke-width': 3 }, gr);
      const num = no('text', { x: xs[i], y: YR + 11, 'text-anchor': 'middle', fill: COR.marfim, 'font-family': 'Cinzel', 'font-weight': 700, 'font-size': 30 }, gr); num.textContent = String(i + 1);
      const rot = no('text', { x: xs[i], y: YR + 80, 'text-anchor': 'middle', fill: COR.marfim, 'font-family': 'Inter', 'font-weight': 600, 'font-size': 27, 'letter-spacing': '2.5' }, gr); rot.textContent = it.rotulo.toUpperCase();
      const ref = no('text', { x: xs[i], y: YR + 116, 'text-anchor': 'middle', fill: 'rgba(239,230,210,0.72)', 'font-family': 'Inter', 'font-weight': 500, 'font-size': 23 }, gr); ref.textContent = it.ref;
      return { gr, c, num, rot, ref };
    });

    // bloco de título (ponto ativo ou o resumo)
    const titulo = ativo ? itens[ativo - 1].rotulo : (P.titulo || 'Cinco pontos');
    const sub = ativo ? itens[ativo - 1].ref : (P.sub || '');
    const eyebrow = P.eyebrow || (ativo ? `A afirmação cristã · ponto ${ativo} de ${n}` : 'A afirmação cristã');
    const janEb = el('div', { left: '150px', top: '236px', width: '1400px', height: '42px', overflow: 'hidden' }, raiz);
    const eb = el('div', { left: '0', top: '0', whiteSpace: 'nowrap', font: `600 29px/42px ${FONTE.ui}`, letterSpacing: '0.24em', color: COR.ouro }, janEb, eyebrow.toUpperCase());
    const janT = el('div', { left: '150px', top: '284px', width: '1600px', height: '150px', overflow: 'hidden' }, raiz);
    const tt = el('div', { left: '0', top: '0', whiteSpace: 'nowrap', font: `700 128px/150px ${FONTE.display}`, letterSpacing: '0.02em', color: COR.marfim }, janT, titulo.toUpperCase());
    const janS = el('div', { left: '154px', top: '440px', width: '1400px', height: '52px', overflow: 'hidden' }, raiz);
    const ss = el('div', { left: '0', top: '0', whiteSpace: 'nowrap', font: `500 38px/52px ${FONTE.ui}`, color: 'rgba(239,230,210,0.9)' }, janS, sub);
    const final = criarCamadaFinal(raiz, { semente: spec.seed, poeira: { n: 0, brilho: 0 }, vinheta: 0.45, grao: 0.05 });

    const saida = D - 0.55;
    // instante em que cada nó acende: ativo -> tA; anteriores já acesos; resumo -> sequência a partir de 0.5 s
    const tNo = (i) => (ativo ? (i + 1 < ativo ? -1 : i + 1 === ativo ? tA + 0.25 : Infinity) : 0.5 + i * 0.32);

    return {
      eventos: [{ t: ativo ? tA + 0.25 : 0.5, tipo: 'ping' }],
      seek(t) {
        g.fillStyle = COR.tinta; g.fillRect(0, 0, W, H);
        if (img) { const s = lerp(1.04, 1.1, smooth(t / D)), e = Math.max(W / img.width, H / img.height) * s, iw = img.width * e, ih = img.height * e; g.drawImage(img, (W - iw) / 2 - 20 * smooth(t / D), (H - ih) / 2, iw, ih); }
        const sai = prog(t, saida, saida + 0.45, inCubic);
        const entra = prog(t, 0.05, 0.6, outCubic);
        base.setAttribute('opacity', String(entra * (1 - sai)));
        // linha de progresso: até o nó anterior desde o início; avança até o ativo junto com a fala
        const xPrev = ativo ? xs[Math.max(0, ativo - 2)] : X0;
        const xAlvo = ativo ? xs[ativo - 1] : X1;
        const k = ativo ? prog(t, tA - 0.35, tA + 0.3, outExpo) : prog(t, 0.4, 0.5 + (n - 1) * 0.32, smooth);
        prog1.setAttribute('x2', String(ativo === 1 ? X0 + (xAlvo - X0) * k : lerp(xPrev, xAlvo, k)));
        prog1.setAttribute('opacity', String(entra * (1 - sai)));
        nos.forEach((o, i) => {
          const ti = tNo(i);
          const aceso = ti < 0 ? 1 : prog(t, ti, ti + 0.45, outExpo);
          const pop = ti < 0 ? 1 : mola(clamp01((t - ti) / 0.6));
          const eAtivo = ativo ? i + 1 === ativo : true;
          const r = (eAtivo ? 30 + 8 * aceso : 26) * (0.7 + 0.3 * (ti < 0 ? 1 : pop));
          o.c.setAttribute('r', r.toFixed(2));
          o.c.setAttribute('fill', aceso > 0.5 && eAtivo ? COR.ouro : COR.tinta);
          o.c.setAttribute('stroke', aceso > 0.02 ? COR.ouro : 'rgba(239,230,210,0.45)');
          o.num.setAttribute('fill', aceso > 0.5 && eAtivo ? COR.tinta : (aceso > 0.02 ? COR.marfim : 'rgba(239,230,210,0.45)'));
          const vis = (ativo ? (i + 1 <= ativo ? Math.max(aceso, ti < 0 ? 1 : 0) : 0.0) : aceso);
          o.rot.setAttribute('opacity', String(vis * (eAtivo && ativo ? 1 : 0.72) * entra * (1 - sai)));
          o.ref.setAttribute('opacity', String(vis * 0.9 * entra * (1 - sai)));
          o.rot.setAttribute('fill', eAtivo && ativo ? COR.ouro : COR.marfim);
          o.gr.setAttribute('opacity', String(entra * (1 - sai)));
        });
        const tTit = ativo ? tA : 0.4;
        eb.style.transform = `translateY(${((1 - prog(t, tTit - 0.5, tTit, outExpo)) * 100 + sai * -100).toFixed(1)}%)`;
        tt.style.transform = `translateY(${((1 - prog(t, tTit - 0.1, tTit + 0.5, outExpo)) * 100 + sai * -100).toFixed(1)}%)`;
        ss.style.transform = `translateY(${((1 - prog(t, tTit + 0.25, tTit + 0.8, outExpo)) * 100 + sai * -100).toFixed(1)}%)`;
        final.desenhar(t, 1);
      },
    };
  },
};
