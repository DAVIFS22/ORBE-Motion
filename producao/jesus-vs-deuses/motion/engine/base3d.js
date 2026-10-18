// Base comum das cenas 3D (Three.js): monta renderizador, céu/IBL, câmera em trilho, informação na tela e camada final.
// Uma cena define `montar(ctx)` e devolve { trilho, ceu, atualizar(t), ibl } — todo o resto é feito aqui.
// seek(t) é função pura do tempo: atualiza só uniformes/transformações a partir de t e renderiza um quadro.
import * as THREE from 'three';
import { el, COR } from './ui.js';
import { prog, smooth, aBatida, outCubic } from './ease.js';
import { construirFicha, construirRodape } from './ficha.js';
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
      if (s.overlay) s.overlay(t, f);
      final.desenhar(t, 1);
    },
  };
}

export { THREE, COR, outCubic };
