// Abertura: céu noturno com Via Láctea sobre as silhuetas de três tradições (obelisco e colunas egípcias, templo dórico, círculo de
// pedras nórdico) — RECONSTRUÇÃO ARTÍSTICA por código. A câmera sobe do horizonte ao céu enquanto o título é revelado letra a letra.
// Tipografia: Cinzel (exibição) + Inter (UI), uma cor de destaque (ouro). Todo o movimento é função de t.
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho } from '../engine/cena3d.js';
import { colunaPapiro, temploDorico, obelisco, caixa, malha, material } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import { el, COR, FONTE } from '../engine/ui.js';
import { prog, outExpo, outCubic, smooth, inCubic } from '../engine/ease.js';
import * as tex from '../engine/tex.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };

// Linha de letras que sobem de uma janela de corte (revelação por máscara), uma a uma.
function linhaLetras(pai, texto, { x, y, larg, alt, fonte, cor, esp = '0.02em' }) {
  const jan = el('div', { left: x + 'px', top: y + 'px', width: larg + 'px', height: alt + 'px', overflow: 'hidden' }, pai);
  const linha = el('div', { left: '0', top: '0', whiteSpace: 'nowrap', display: 'flex', font: `${fonte}`, lineHeight: alt + 'px', letterSpacing: esp, color: cor }, jan);
  const spans = [];
  for (const ch of texto) { const s = document.createElement('span'); s.textContent = ch === ' ' ? '\u00a0' : ch; Object.assign(s.style, { display: 'inline-block', position: 'relative' }); linha.appendChild(s); spans.push(s); }
  return { jan, spans, alt };
}

const def = {
  render: { exposicao: 1.1 },
  async montar({ cena, P, D, spec, raiz, snap }) {
    const seed = spec.seed ?? 1;
    const paraLua = norm([-0.35, 0.42, -0.84]);
    const ceu = criarCeu({ hor: 0x3a4a78, meio: 0x15204a, zen: 0x05081a, baixo: 0x0a0c16, sol: 0xc8d8ff, sunDir: paraLua, expo: 0.6, brilho: 0.9, nuvens: 0, estrelas: 2.4, via: 2.6, disco: 1.0 });
    cena.fog = new THREE.FogExp2(0x101a38, 0.0075);

    const tAreia = tex.terra({ tam: 1024, semente: 101, base: [110, 104, 100] });
    const tPedra = tex.blocos({ tam: 1024, semente: 103, fiadas: 4, comprimento: [0.4, 0.8], base: [170, 160, 150], desgaste: 0.9 });
    const tFuste = tex.egipcia({ tam: 1024, semente: 21, modo: 'fuste', pintura: 0.5 }), tCap = tex.egipcia({ tam: 1024, semente: 23, modo: 'capitel', pintura: 0.5 });
    const tM = tex.marmore({ tam: 1024, semente: 105, tambores: 9, base: [190, 186, 180] });
    const mats = { fuste: material(tFuste, { env: 0.6 }), capitel: material(tCap, { env: 0.6 }), pedra: material(tPedra, { env: 0.6 }),
      arquitrave: material(tM, { rep: [0.35, 0.35], env: 0.7 }), triglifo: material(tM, { rep: [0.5, 0.5], vertexColors: true, env: 0.7 }), metopa: material(tM, { rep: [0.35, 0.35], env: 0.7 }),
      cornija: material(tM, { rep: [0.35, 0.35], env: 0.7 }), timpano: material(tM, { rep: [0.25, 0.25], cor: 0x7a7e88 }), telha: material(tM, { rep: [0.3, 0.3], env: 0.7 }),
      degrau: material(tPedra, { env: 0.6 }), cela: material(tPedra, { env: 0.6 }), fuste2: material(tM, { env: 0.7 }) };

    // chão de areia/pedra escuro, grande
    const chao = new THREE.Mesh(new THREE.PlaneGeometry(1400, 1400), material(tAreia, { rep: [90, 90], normal: 0.6, rug: 1, env: 0.6, cor: 0x7a7a88 }));
    chao.rotation.x = -Math.PI / 2; chao.receiveShadow = true; cena.add(chao);

    // três tradições, em fila diante da câmera (cada uma em um plano de profundidade)
    const ob = obelisco({ base: 3.4, alt: 34, mats }); ob.position.set(-24, 0, -64); cena.add(ob);
    for (let i = 0; i < 3; i++) { const c = colunaPapiro({ R: 1.7, H: 19, aberto: i !== 1, gomos: 8, mats }); c.position.set(-42 + i * 8.5, 0, -62 - i * 3); cena.add(c); }
    const templo = temploDorico({ nF: 6, nL: 3, D: 2.25, H: 10.4, entre: 5.2, mats: { ...mats, fuste: mats.fuste2, capitel: mats.fuste2 }, estrias: 20 });
    templo.position.set(16, 0, -88); templo.rotation.y = -0.22; cena.add(templo);
    const rr = rngFor(seed, 7);
    for (let i = 0; i < 9; i++) {                               // círculo de pedras erguidas (formas simples, sem runas)
      const a = (i / 9) * Math.PI * 2 + 0.2, R = 15 + rr() * 1.5, h = 5 + rr() * 3.2, w = 1.5 + rr() * 1.1;
      const pedra = malha(caixa(w, h, 1 + rr() * 0.8, { raio: 0.25, seg: 3, esc: 0.2 }), mats.pedra, { pos: [54 + Math.cos(a) * R, h / 2 - 0.2, -66 + Math.sin(a) * R * 0.7] });
      pedra.rotation.set((rr() - 0.5) * 0.12, rr() * 3, (rr() - 0.5) * 0.12); cena.add(pedra);
    }

    // luz da lua (fria) com sombras longas, preenchimento do céu e um brilho dourado discreto na fachada do templo
    const lua = criarSol({ cor: 0xa8c0ff, intensidade: 2.2, dir: paraLua, alvo: [0, 5, -70], dist: 220, caixa: 90, mapa: 2048, bias: -0.0004, normalBias: 0.08, near: 50, far: 520 });
    cena.add(lua, lua.target);
    cena.add(new THREE.HemisphereLight(0x405080, 0x141018, 0.7));
    const brasa = new THREE.PointLight(0xffb060, 160, 70, 1.6); brasa.position.set(12, 4, -78); cena.add(brasa);
    const poeira = criarPoeira3D({ semente: seed, n: 260, caixa: [-30, 0.5, -60, 30, 14, 25], vel: [0.1, 0.03, -0.05], cor: 0xb8c8ff, tam: 1.6, op: 0.45 });
    cena.add(poeira);

    // título: JESUS (ouro) + CONTRA TODOS OS DEUSES + subtítulo; esquerda-baixo, sobre uma faixa escura suave
    const T = P.titulo || { linha1: 'JESUS', linha2: 'CONTRA TODOS', linha3: 'OS DEUSES', sub: 'Por que Jesus é único?' };
    const x0 = 120, y0 = 470;
    const scrim = el('div', { left: '0', top: '0', width: '1300px', height: '1080px', pointerEvents: 'none', background: 'linear-gradient(90deg, rgba(3,4,10,0.72) 0%, rgba(3,4,10,0.45) 50%, rgba(3,4,10,0) 100%)' }, raiz);
    const L1 = linhaLetras(raiz, T.linha1, { x: x0, y: y0, larg: 1000, alt: 210, fonte: `700 190px ${FONTE.display}`, cor: COR.ouro, esp: '0.03em' });
    const L2 = linhaLetras(raiz, T.linha2, { x: x0 + 4, y: y0 + 214, larg: 1000, alt: 108, fonte: `600 92px ${FONTE.display}`, cor: COR.marfim, esp: '0.06em' });
    const L3 = linhaLetras(raiz, T.linha3, { x: x0 + 4, y: y0 + 318, larg: 1000, alt: 108, fonte: `600 92px ${FONTE.display}`, cor: COR.marfim, esp: '0.06em' });
    const regra = el('div', { left: x0 + 'px', top: (y0 + 444) + 'px', width: '340px', height: '3px', background: COR.ouro, transformOrigin: '0 50%' }, raiz);
    const sub = linhaLetras(raiz, T.sub, { x: x0, y: y0 + 462, larg: 1000, alt: 56, fonte: `600 46px ${FONTE.ui}`, cor: COR.marfimSuave, esp: "0.12em" });
    const preto = el('div', { left: '0', top: '0', width: '1920px', height: '1080px', background: '#000', pointerEvents: 'none' }, raiz);
    const t1 = snap(0.35), t2 = snap(1.45), t3 = snap(2.35), sai = D - 0.55;

    const trilho = criarTrilho({
      pos: [[0, 1.5, 22], [2.0, 1.9, 10], [3.6, 2.6, -2], [4.6, 3.6, -14]],
      alvo: [[-4, 8, -100], [-2, 13, -100], [0, 20, -98], [2, 27, -96]],
      fov: [48, 42], curva: (x) => 0.2 * x + 0.8 * smooth(x),
    });
    return {
      ceu, trilho, ibl: 0.45, vinheta: 0.62, poeiraTela: 22,
      tremor: { pos: 0.006, ang: 0.03 },
      eventos: [{ t: t1, tipo: 'impacto' }, { t: t2, tipo: 'whoosh' }, { t: t3, tipo: 'revelar' }],
      atualizar(t) { poeira.material.uniforms.uT.value = t; },
      overlay(t) {
        const sob = (L, ini, passo, alturaLetra) => L.spans.forEach((s, i) => { s.style.transform = `translateY(${(1 - prog(t, ini + i * passo, ini + i * passo + 0.7, outExpo)) * alturaLetra * 1.2}px)`; });
        sob(L1, t1, 0.07, 190); sob(L2, t2, 0.03, 92); sob(L3, t2 + 0.22, 0.03, 92); sob(sub, t3 + 0.25, 0.018, 40);
        regra.style.transform = `scaleX(${prog(t, t3, t3 + 0.7, outExpo)})`;
        const fora = prog(t, sai, sai + 0.45, inCubic);
        for (const L of [L1, L2, L3, sub]) L.jan.style.opacity = String(1 - fora);
        regra.style.opacity = String(1 - fora);
        scrim.style.opacity = String(prog(t, 0.2, 1.2, smooth) * (1 - fora));
        preto.style.opacity = String(1 - prog(t, 0, 0.55, outCubic));
      },
    };
  },
};

export const cena3d_abertura = { build: (palco, spec) => iniciar3D(palco, spec, def) };
