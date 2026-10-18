// Linha do tempo histórica: régua que se amplia/desloca entre períodos, faixas de períodos, eventos com datas e a ficha.
// Também serve de "cartão de data/fato": a janela se fecha no intervalo do fato e o ano aparece em destaque.
// params: { janela:[{f,a,b}], periodos:[{nome,curto,ini,fim,lane,f,foco}], eventos:[{nome,sub,ano,aprox,f,foco}],
//           ficha:{...}, rodape, batidas }
// Anos astronômicos simplificados: negativo = a.C., positivo = d.C. (não existe ano zero na leitura histórica; não é usado).
import { linha } from '../engine/tl.js';
import { el, canvas, COR, FONTE } from '../engine/ui.js';
import { prog, outCubic, outExpo, inOutCubic, smooth, aBatida, mola, clamp01 } from '../engine/ease.js';
import { construirFicha, construirRodape } from '../engine/ficha.js';
import { criarCamadaFinal } from '../engine/atmos.js';

const W = 1920, H = 1080, X0 = 110, X1 = 1810, AX = 770;
const NS = 'http://www.w3.org/2000/svg';
const PASSOS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000];

export const fmtAno = (a) => (a < 0 ? `${-a} a.C.` : `${a} d.C.`);

function no(tag, attrs, pai) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (pai) pai.appendChild(e); return e; }

export const periodo = {
  async build(palco, spec) {
    const P = spec.params, D = spec.dur, bat = P.batidas || [];
    const snap = (x) => aBatida(x, bat, 0.22);
    const raiz = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', background: COR.tinta, overflow: 'hidden' }, palco);
    // fundo: pontos de grade muito discretos + brilho quente baixo (sem gradiente decorativo vazio: o brilho marca o eixo do tempo)
    const fundo = canvas(W, H, {}, raiz); const gf = fundo.getContext('2d');
    const svg = no('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, null);
    Object.assign(svg.style, { position: 'absolute', left: '0', top: '0', overflow: 'visible' }); raiz.appendChild(svg);
    const gTicks = no('g', {}, svg), gBars = no('g', {}, svg), gEv = no('g', {}, svg);
    const eixo = no('line', { x1: X0, x2: X1, y1: AX, y2: AX, stroke: 'rgba(239,230,210,0.55)', 'stroke-width': 2 }, svg);
    const ticks = Array.from({ length: 44 }, () => ({ l: no('line', { stroke: 'rgba(239,230,210,0.55)', 'stroke-width': 2 }, gTicks), t: no('text', { 'text-anchor': 'middle', fill: COR.marfim, 'font-family': 'Inter', 'font-weight': 500, 'font-size': 26 }, gTicks) }));
    const barras = (P.periodos || []).map((p) => {
      const r = no('rect', { rx: 8, height: 50 }, gBars);
      const cl = no('clipPath', { id: 'cb' + Math.abs(hashStr(p.nome)) }, svg); const cr = no('rect', { height: 50 }, cl);
      const tx = no('text', { fill: COR.marfim, 'font-family': 'Inter', 'font-weight': 600, 'font-size': 29, 'clip-path': `url(#cb${Math.abs(hashStr(p.nome))})` }, gBars); tx.textContent = p.nome;
      return { p, r, cr, tx };
    });
    const evs = (P.eventos || []).map((e) => {
      const l = no('line', { stroke: COR.ouro, 'stroke-width': 3 }, gEv);
      const d = no('circle', { r: 11, fill: e.foco ? COR.ouro : COR.tinta, stroke: COR.ouro, 'stroke-width': 4 }, gEv);
      const n = no('text', { fill: COR.marfim, 'font-family': 'Cinzel', 'font-weight': 700, 'font-size': e.foco ? 50 : 40, 'text-anchor': 'middle' }, gEv); n.textContent = e.nome.toUpperCase();
      const s = no('text', { fill: COR.ouro, 'font-family': 'Inter', 'font-weight': 600, 'font-size': 30, 'text-anchor': 'middle' }, gEv); s.textContent = (e.sub ? e.sub + ' · ' : '') + (e.data ? e.data : (e.aprox ? 'c. ' : '') + fmtAno(e.ano));
      const cl = no('clipPath', { id: 'ce' + Math.abs(hashStr(e.nome + e.ano)) }, svg); const cr = no('rect', {}, cl);
      n.setAttribute('clip-path', `url(#ce${Math.abs(hashStr(e.nome + e.ano))})`); s.setAttribute('clip-path', `url(#ce${Math.abs(hashStr(e.nome + e.ano))})`);
      return { e, l, d, n, s, cr };
    });
    // ano grande (fantasma) ao fundo, em exibição
    const ano = el('div', { left: '0', top: '110px', width: W + 'px', textAlign: 'right', paddingRight: '90px', font: `700 170px/1 ${FONTE.display}`, color: 'rgba(232,190,105,0.085)', whiteSpace: 'nowrap' }, raiz, '');
    const fcfg = P.fichaCfg || { x: 110, y: 70, largura: 900, tamNome: 96 };
    const ficha = construirFicha(raiz, P.ficha, fcfg);
    const rodape = P.rodape ? construirRodape(raiz, P.rodape, { x: 110, y: 990, largura: 1500 }) : null;
    const final = criarCamadaFinal(raiz, { semente: spec.seed, poeira: { n: 30, brilho: 0.35 }, vinheta: 0.5, grao: 0.04 });

    const tp = { eyebrow: snap(0.3), nome: snap(0.5), regra: 0.9, periodo: 1.1, descricao: 1.4, fonte: 1.9 };
    const saida = D - 0.45;
    // rótulos dos eventos: largura medida, nível automático (só sobe quando dois rótulos se sobrepõem na janela final),
    // presos às margens da tela e sempre abaixo da ficha (a régua fica livre do texto)
    const topoZona = ficha.fim + 26, Jf = P.janela[P.janela.length - 1];
    const Xf = (a) => X0 + ((a - Jf.a) / (Jf.b - Jf.a)) * (X1 - X0);
    const prender = (x, larg) => Math.min(Math.max(x, 70 + larg / 2), W - 70 - larg / 2);
    const colocados = [];
    evs.forEach((o) => {
      o.larg = Math.max(o.n.getComputedTextLength(), o.s.getComputedTextLength());
      const cx = prender(Xf(o.e.ano), o.larg); let nivel = 0;
      while (colocados.some((c) => c.nivel === nivel && Math.abs(c.cx - cx) < (c.larg + o.larg) / 2 + 40)) nivel++;
      colocados.push({ cx, larg: o.larg, nivel }); o.nivel = nivel;
    });
    const maxN = Math.max(0, ...evs.map((o) => o.nivel));
    const passoN = maxN ? Math.max(72, Math.min(100, (AX - 115 - (topoZona + 40)) / maxN)) : 0;
    const eventos = [{ t: tp.nome, tipo: 'revelar' }];
    (P.eventos || []).forEach((e) => eventos.push({ t: snap(e.f * D), tipo: 'ping' }));
    (P.periodos || []).forEach((p) => eventos.push({ t: snap(p.f * D), tipo: 'faixa' }));

    function janelaEm(f) {
      const J = P.janela; if (f <= J[0].f) return [J[0].a, J[0].b];
      for (let i = 1; i < J.length; i++) if (f <= J[i].f) {
        const a = J[i - 1], b = J[i], k = inOutCubic((f - a.f) / Math.max(1e-6, b.f - a.f));
        const c = (a.a + a.b) / 2 + ((b.a + b.b) / 2 - (a.a + a.b) / 2) * k;
        const s = Math.exp(Math.log(a.b - a.a) + (Math.log(b.b - b.a) - Math.log(a.b - a.a)) * k);
        return [c - s / 2, c + s / 2];
      }
      const u = J[J.length - 1]; return [u.a, u.b];
    }

    return {
      eventos,
      seek(t) {
        const f = t / D;
        const [ja, jb] = janelaEm(f);
        const X = (a) => X0 + ((a - ja) / (jb - ja)) * (X1 - X0);
        const sai = 1 - prog(t, saida, saida + 0.4, smooth);
        // fundo
        gf.save();
        gf.fillStyle = COR.tinta; gf.fillRect(0, 0, W, H);
        const rg = gf.createRadialGradient(W / 2, AX, 10, W / 2, AX, 900); rg.addColorStop(0, 'rgba(232,190,105,0.13)'); rg.addColorStop(1, 'rgba(232,190,105,0)');
        gf.fillStyle = rg; gf.fillRect(0, 0, W, H);
        gf.restore();
        // régua
        const span = jb - ja; let passo = PASSOS[PASSOS.length - 1];
        for (const c of PASSOS) if (span / c <= 8.5) { passo = c; break; }
        const primeiro = Math.ceil(ja / passo) * passo;
        const ideal = clamp01((span / passo - 2.5) / 2);        // some quando há poucos rótulos (evita saltos bruscos)
        const kEixo = prog(t, 0.05, 0.9, outExpo);
        eixo.setAttribute('x2', String(X0 + (X1 - X0) * kEixo)); eixo.setAttribute('opacity', String(sai));
        let i = 0;
        for (let a = primeiro; a <= jb && i < ticks.length; a += passo, i++) {
          const x = X(a); const tk = ticks[i];
          tk.l.setAttribute('x1', x); tk.l.setAttribute('x2', x); tk.l.setAttribute('y1', AX - 12); tk.l.setAttribute('y2', AX + 12);
          tk.l.setAttribute('opacity', String(kEixo * sai));
          tk.t.setAttribute('x', x); tk.t.setAttribute('y', AX + 52); tk.t.textContent = fmtAno(a === 0 ? 1 : a); tk.t.setAttribute('opacity', String(ideal * kEixo * sai));
        }
        for (; i < ticks.length; i++) { ticks[i].l.setAttribute('opacity', '0'); ticks[i].t.setAttribute('opacity', '0'); }
        // faixas de períodos
        barras.forEach((b) => {
          const p = b.p; const t0 = snap(p.f * D); const k = prog(t, t0, t0 + 0.9, outExpo) * sai;
          const xa = Math.max(X0, X(p.ini)), xb = Math.min(X1, X(p.fim)); const y = AX + 76 + (p.lane || 0) * 62;
          const w = Math.max(0, (xb - xa) * k);
          b.r.setAttribute('x', xa); b.r.setAttribute('y', y); b.r.setAttribute('width', w); b.r.setAttribute('height', 50);
          b.r.setAttribute('fill', p.foco ? 'rgba(232,190,105,0.92)' : 'rgba(232,190,105,0.14)'); b.r.setAttribute('stroke', p.foco ? 'none' : 'rgba(232,190,105,0.65)'); b.r.setAttribute('stroke-width', 2);
          b.tx.textContent = (xb - xa) < 330 && p.curto ? p.curto : p.nome;
          // o nome cabe na faixa? senão vai ao lado dela (à direita, ou à esquerda perto da borda), nunca cortado
          const tw = b.tx.getComputedTextLength(), dentro = tw + 36 <= xb - xa, direita = xb + 16 + tw <= W - 60;
          const tx = dentro ? xa + 18 : direita ? xb + 16 : xa - 16 - tw;
          if (dentro) { b.cr.setAttribute('x', xa + 8); b.cr.setAttribute('width', Math.max(0, w - 16)); }
          else { b.cr.setAttribute('x', tx - 4); b.cr.setAttribute('width', (tw + 8) * k); }
          b.cr.setAttribute('y', y); b.cr.setAttribute('height', 50);
          b.tx.setAttribute('x', tx); b.tx.setAttribute('y', y + 35); b.tx.setAttribute('fill', p.foco && dentro ? COR.tinta : COR.marfim); b.tx.setAttribute('opacity', String(k > 0.05 ? 1 : 0));
        });
        // eventos
        evs.forEach((o) => {
          const e = o.e; const t0 = snap(e.f * D); const k = prog(t, t0, t0 + 0.55, outExpo) * sai; const x = X(e.ano);
          const ty = AX - 115 - o.nivel * passoN, alt = AX - (ty + 58), lx = prender(x, o.larg);
          const vis = x > X0 - 40 && x < X1 + 40 ? 1 : 0;
          o.l.setAttribute('x1', x); o.l.setAttribute('x2', x); o.l.setAttribute('y1', AX); o.l.setAttribute('y2', AX - alt * k); o.l.setAttribute('opacity', String(vis * k));
          o.d.setAttribute('cx', x); o.d.setAttribute('cy', AX); o.d.setAttribute('r', String(11 * mola(prog(t, t0, t0 + 0.6, (u) => u), 5, 8))); o.d.setAttribute('opacity', String(vis * (k > 0 ? 1 : 0)));
          o.n.setAttribute('x', lx); o.n.setAttribute('y', ty); o.s.setAttribute('x', lx); o.s.setAttribute('y', ty + 40);
          const revel = prog(t, t0 + 0.15, t0 + 0.8, outExpo);
          const cw = o.larg + 60; o.cr.setAttribute('y', ty - 56); o.cr.setAttribute('width', cw * revel); o.cr.setAttribute('height', 130);
          o.cr.setAttribute('x', lx - (cw * revel) / 2);
          const op = String(vis * k > 0 ? Math.min(1, k * 2) * sai : 0); o.n.setAttribute('opacity', op); o.s.setAttribute('opacity', op);
        });
        // ano grande
        const c = Math.round((ja + jb) / 2); ano.textContent = fmtAno(c === 0 ? 1 : c); ano.style.opacity = String(prog(t, 0.3, 1.2, smooth) * sai);
        ficha.aplicar(t, tp, saida);
        rodape && rodape.aplicar(t, tp.fonte, saida);
        final.desenhar(t, 0.7);
      },
    };
  },
};

function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0; return h; }
