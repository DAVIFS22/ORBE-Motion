// Base comum das cenas 3D (Three.js): monta renderizador, céu/IBL, câmera em trilho, informação na tela e camada final.
// Uma cena define `montar(ctx)` e devolve { trilho, ceu, atualizar(t), ibl } — todo o resto é feito aqui.
// seek(t) é função pura do tempo: atualiza só uniformes/transformações a partir de t e renderiza um quadro.
import * as THREE from 'three';
import { el, COR } from './ui.js';
import { prog, smooth, aBatida, outCubic } from './ease.js';
import { construirFicha, construirRodape, medirTexto } from './ficha.js';
import { criarCamadaFinal } from './atmos.js';
import { criarRenderizador, ambienteDoCeu, criarTremor, aplicarCamera } from './cena3d.js';

// Informação na tela: faixa escura suave à esquerda (legibilidade em telas pequenas) + ficha animada + rodapé de procedência.
function criarHud(raiz, P, D, snap) {
  const cfg = P.hud || {};
  const x = cfg.x ?? 110, y = cfg.y ?? 560, largura = cfg.largura ?? 760;
  const scrim = el('div', { left: '0', top: '0', width: '1180px', height: '1080px', pointerEvents: 'none',
    background: 'linear-gradient(90deg, rgba(4,3,2,0.74) 0%, rgba(4,3,2,0.5) 46%, rgba(4,3,2,0) 100%)' }, raiz);
  const ficha = construirFicha(raiz, { ...P.ficha, tamNome: P.ficha.tamNome ?? cfg.tamNome ?? 96 }, { x, y, largura });
  const rodape = P.rodape ? construirRodape(raiz, P.rodape, { x, y: cfg.yRodape ?? 936, largura: cfg.larguraRodape ?? 760 }) : null;
  const ini = snap(cfg.ini ?? 0.6), saida = D - 0.5;
  const tp = { eyebrow: ini, nome: ini + 0.22, regra: ini + 0.5, periodo: ini + 0.62, descricao: ini + 0.9, fonte: ini + 1.2 };
  return {
    tp, ini,
    aplicar(t) {
      scrim.style.opacity = String(prog(t, ini - 0.25, ini + 0.7, smooth) * (1 - prog(t, saida, saida + 0.4, smooth)));
      ficha.aplicar(t, tp, saida);
      if (rodape) rodape.aplicar(t, tp.fonte, saida);
    },
  };
}

// Anotações híbridas: rótulo 2D + linha-guia vetorial presos a um ponto 3D (projetado pela câmera a cada quadro).
// P.anotacoes = [{ pos:[x,y,z], texto, sub?, t0, t1, lado?: 'dir'|'esq', dy? }] — t0/t1 em segundos do plano.
function criarAnotacoes(raiz, lista, cam) {
  if (!lista || !lista.length) return null;
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('width', 1920); svg.setAttribute('height', 1080);
  Object.assign(svg.style, { position: 'absolute', left: '0', top: '0', pointerEvents: 'none', overflow: 'visible' }); raiz.appendChild(svg);
  const v = new THREE.Vector3();
  const itens = lista.map((a) => {
    const linha = document.createElementNS(NS, 'polyline'); linha.setAttribute('fill', 'none'); linha.setAttribute('stroke', COR.ouro); linha.setAttribute('stroke-width', '2.5');
    const ponto = document.createElementNS(NS, 'circle'); ponto.setAttribute('r', '6'); ponto.setAttribute('fill', 'none'); ponto.setAttribute('stroke', COR.ouro); ponto.setAttribute('stroke-width', '2.5');
    svg.appendChild(linha); svg.appendChild(ponto);
    const largura = Math.max(medirTexto(a.texto.toUpperCase(), '700 40px "Cinzel", serif') + a.texto.length * 40 * 0.03, a.sub ? medirTexto(a.sub, '500 27px "Inter", sans-serif') : 0);
    const caixa = el('div', { left: '0', top: '0', width: Math.ceil(largura + 4) + 'px', whiteSpace: 'nowrap', textShadow: '0 1px 3px rgba(0,0,0,0.9), 0 0 16px rgba(0,0,0,0.7)' }, raiz);
    const t1 = el('div', { position: 'relative', font: `700 40px/1.15 "Cinzel", serif`, color: COR.marfim, letterSpacing: '0.03em' }, caixa, a.texto.toUpperCase());
    if (a.sub) el('div', { position: 'relative', font: `500 27px/1.3 "Inter", sans-serif`, color: 'rgba(239,230,210,0.88)' }, caixa, a.sub);
    return { a, linha, ponto, caixa, w: Math.ceil(largura + 4) };
  });
  return {
    aplicar(t) {
      for (const it of itens) {
        const { a } = it;
        const k = prog(t, a.t0, a.t0 + 0.7, outCubic) * (1 - prog(t, a.t1 - 0.4, a.t1, smooth));
        v.set(...a.pos).project(cam);
        const vis = k > 0.001 && v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1;
        if (!vis) { it.linha.setAttribute('opacity', '0'); it.ponto.setAttribute('opacity', '0'); it.caixa.style.opacity = '0'; continue; }
        const x = (v.x * 0.5 + 0.5) * 1920, y = (-v.y * 0.5 + 0.5) * 1080;
        const dir = (a.lado ?? (x < 960 ? 'dir' : 'esq')) === 'dir' ? 1 : -1;
        const cx = x + dir * 70, cy = y - (a.dy ?? 90), fx = cx + dir * 150 * k;
        it.linha.setAttribute('points', `${x.toFixed(1)},${y.toFixed(1)} ${cx.toFixed(1)},${cy.toFixed(1)} ${fx.toFixed(1)},${cy.toFixed(1)}`);
        it.linha.setAttribute('opacity', String(k)); it.ponto.setAttribute('cx', x.toFixed(1)); it.ponto.setAttribute('cy', y.toFixed(1)); it.ponto.setAttribute('opacity', String(k));
        const w = it.w;
        it.caixa.style.left = (dir > 0 ? cx + 14 : cx - 14 - w).toFixed(1) + 'px';
        it.caixa.style.top = (cy - 56).toFixed(1) + 'px';
        it.caixa.style.opacity = String(k);
        it.caixa.style.textAlign = dir > 0 ? 'left' : 'right';
      }
    },
  };
}

export async function iniciar3D(palco, spec, def) {
  const P = spec.params ?? {}, D = spec.dur, bat = P.batidas || [];
  const snap = (x) => aBatida(x, bat, 0.22);
  const raiz = el('div', { left: '0', top: '0', width: '1920px', height: '1080px', background: '#000', overflow: 'hidden' }, palco);
  const { r, copiar } = criarRenderizador(raiz, def.render ?? {});
  const cena = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(40, 16 / 9, 0.2, 3000);
  const s = await def.montar({ THREE, cena, r, cam, spec, P, D, raiz, snap });
  if (s.ceu) { cena.add(s.ceu.malha); if (s.ibl !== false) { const env = ambienteDoCeu(r, s.ceu); cena.environment = env.textura; cena.environmentIntensity = s.ibl ?? 0.6; } }
  r.compile(cena, cam);                                              // compila shaders agora (não no primeiro quadro)

  window.__dbg3d = { cena, r, cam };                                 // só para diagnóstico de desempenho (não afeta o render)
  const hud = (P.hud && P.hud.desligado) ? null : criarHud(raiz, P, D, snap);   // a cena pode trazer o próprio texto (s.overlay)
  // sem ficha, mas com o rodapé de procedência (ex.: "reconstrução artística por código"), discreto no canto inferior esquerdo
  const soRodape = (!hud && P.rodape && P.hud && P.hud.rodape) ? construirRodape(raiz, P.rodape, { x: 110, y: 966, largura: 1100, sombra: true }) : null;
  const iniRod = snap(0.5);
  const anot = criarAnotacoes(raiz, P.anotacoes, cam);
  const final = criarCamadaFinal(raiz, { semente: spec.seed, poeira: { n: s.poeiraTela ?? 24, brilho: 0.35 }, vinheta: s.vinheta ?? 0.5, grao: 0.05 });
  const tremor = criarTremor(spec.seed, s.tremor ?? { pos: 0.012, ang: 0.05 });
  const eventos = [...(hud ? [{ t: hud.tp.nome, tipo: 'revelar' }] : []), ...(s.eventos ?? [])];

  return {
    eventos,
    seek(t) {
      const f = Math.min(1, Math.max(0, t / D));
      s.atualizar?.(t, f);
      const k = s.trilho(f);
      aplicarCamera(cam, k, tremor(t));
      if (s.ceu) s.ceu.u.uT.value = t;
      r.render(cena, cam);
      copiar();
      if (hud) hud.aplicar(t);
      if (soRodape) soRodape.aplicar(t, iniRod, D - 0.5);
      if (anot) anot.aplicar(t);
      if (s.overlay) s.overlay(t, f);
      final.desenhar(t, 1);
    },
  };
}

export { THREE, COR, outCubic };
