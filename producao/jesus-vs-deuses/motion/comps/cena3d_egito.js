// Salão hipostilo egípcio — RECONSTRUÇÃO ARTÍSTICA por código, inspirada no Salão Hipostilo de Karnak.
// Geometria 3D real (colunas papiriformes com gomos, arquitraves, lajes, claristório), texturas procedurais PBR, luz solar
// com sombras entrando pelas frestas do claristório, feixes de luz, poeira em suspensão e câmera em trilho (spline).
// Inscrições e cores são estilizadas: não representam texto nem pintura atestados.
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarFeixe, criarPoeira3D, criarTrilho } from '../engine/cena3d.js';
import { salaoHipostilo, obelisco, caixa, malha, material, terreno } from '../engine/arq.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };

function brilhoPortal() {                          // halo suave do sol entrando pela porta (sprite aditivo)
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d'), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(255,236,190,0.95)'); gr.addColorStop(0.35, 'rgba(255,214,150,0.38)'); gr.addColorStop(1, 'rgba(255,200,130,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: t, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, opacity: 0.55 }));
}

const def = {
  render: { exposicao: 1.05 },
  async montar({ cena, P, D, spec }) {
    const seed = spec.seed ?? 1;
    const paraSol = norm([-0.56, 0.7, -0.2]);                 // direção PARA o sol (vem do lado -x, alto)
    const ceu = criarCeu({ hor: 0xe6b774, meio: 0xb8c4d0, zen: 0x4f7fb8, baixo: 0xa88858, sol: 0xffe6b8, sunDir: paraSol, expo: 0.5, brilho: 1.2, nuvens: 0.25, cobertura: 0.25 });
    cena.fog = new THREE.FogExp2(0xb08a58, 0.0095);

    // materiais (texturas procedurais; sementes fixas)
    const tFuste = tex.egipcia({ tam: 1024, semente: 21, modo: 'fuste' }), tCap = tex.egipcia({ tam: 1024, semente: 23, modo: 'capitel' });
    const tPedra = tex.blocos({ tam: 1024, semente: 12, fiadas: 4, comprimento: [0.4, 0.7], base: [198, 160, 110], desgaste: 0.7, estratos: 0.5 });
    const tParede = tex.blocos({ tam: 1024, semente: 14, fiadas: 7, comprimento: [0.3, 0.5], base: [200, 166, 118], desgaste: 0.6, estratos: 0.6 });
    const tPiso = tex.lajes({ tam: 1024, semente: 16, n: 5, base: [176, 152, 118] });
    const tTeto = tex.teto({ tam: 1024, semente: 41 });
    const tAreia = tex.areia({ tam: 1024, semente: 18, base: [222, 184, 124] });
    const mats = {
      fuste: material(tFuste, { rep: [1, 1], normal: 1.0, rug: 0.95, env: 0.7 }),
      capitel: material(tCap, { rep: [1, 1], normal: 0.8, rug: 0.95, env: 0.7 }),
      pedra: material(tPedra, { rep: [1, 1], normal: 1.0, rug: 1, env: 0.6 }),
      parede: material(tParede, { rep: [1, 1], normal: 1.0, rug: 1, env: 0.6 }),
      teto: material(tTeto, { rep: [1, 1], normal: 0.8, rug: 0.95, env: 0.5, emis: 0.22 }),
      piso: material(tPiso, { rep: [15, 17], normal: 1.0, rug: 0.95, env: 0.6 }),
    };

    const salao = salaoHipostilo({ filas: 7, espaco: 9.6, naveLarg: 13, R1: 1.75, H1: 19, R2: 1.25, H2: 12.5, laterais: 4, esp2: 6.4, mats, seed });
    cena.add(salao);
    const dim = salao.userData.dim;
    const zFim = -dim.comp - 4.8, X = dim.larguraTotal + 1.5;

    // paredes externas e parede do fundo com portal
    const hP = 13.5, lp = dim.comp + 22;
    for (const s of [-1, 1]) cena.add(malha(caixa(2.4, hP, lp, { raio: 0.06, esc: 0.22 }), mats.parede, { pos: [s * X, hP / 2, -dim.comp / 2 - 4] }));
    const vao = 9, hv = 17, hMuro = 25;
    for (const s of [-1, 1]) cena.add(malha(caixa(X - vao / 2, hMuro, 3.6, { raio: 0.08, esc: 0.2 }), mats.parede, { pos: [s * (vao / 2 + (X - vao / 2) / 2), hMuro / 2, zFim] }));
    cena.add(malha(caixa(vao + 1, hMuro - hv, 3.6, { raio: 0.08, esc: 0.2 }), mats.pedra, { pos: [0, hv + (hMuro - hv) / 2, zFim] }));
    // batentes do portal
    for (const s of [-1, 1]) cena.add(malha(caixa(1.1, hv, 3.9, { raio: 0.06, esc: 0.3 }), mats.pedra, { pos: [s * (vao / 2 + 0.2), hv / 2, zFim] }));
    // tapa-sol: parede e teto atrás da câmera (o salão é fechado também na entrada)
    cena.add(malha(caixa(2 * X, hMuro, 2, { raio: 0.06, esc: 0.2 }), mats.parede, { pos: [0, hMuro / 2, 12] }));

    // pátio pavimentado diante do portal e deserto além (dunas crescem com a distância; nada fura o piso do salão)
    const R = tex.criarRuido(seed + 40);
    const dunas = terreno({ larg: 900, prof: 900, nx: 170, nz: 170, centro: [0, zFim - 450], esc: 0.05,
      altura: (x, z) => { const d = Math.max(0, zFim - z - 55); const k = smooth(Math.min(1, d / 220)); return -0.35 - 2.0 * k + 12 * k * Math.pow(R.fbm(x * 0.007, z * 0.007, 4), 2); } });
    const mAreia = material(tAreia, { rep: [1, 1], normal: 1.0, rug: 1, env: 0.5 });
    cena.add(malha(dunas, mAreia, { sombra: false }));
    const patio = new THREE.Mesh(new THREE.PlaneGeometry(120, 62), material(tPiso, { rep: [18, 9], rug: 0.95 }));
    patio.rotation.x = -Math.PI / 2; patio.position.set(0, -0.02, zFim - 31); patio.receiveShadow = true; cena.add(patio);
    // obelisco e pilone distantes (silhuetas que dão profundidade ao portal)
    const ob = obelisco({ base: 3.2, alt: 32, mats }); ob.position.set(-13, 0, zFim - 70); cena.add(ob);
    const halo = brilhoPortal(); halo.position.set(0, hv * 0.55, zFim + 1.2); halo.scale.set(26, 32, 1); cena.add(halo);

    // luzes
    const sol = criarSol({ cor: 0xfff0d2, intensidade: 5.2, dir: paraSol, alvo: [0, 8, -dim.comp / 2], dist: 140, caixa: 75, mapa: 4096, bias: -0.00025, normalBias: 0.06, near: 20, far: 320 });
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(0x8a7a62, 0x3a2a1a, 0.16));
    for (let i = 0; i < 4; i++) { const p = new THREE.PointLight(0xff9a48, 26, 15, 1.8); p.position.set(((i % 2) ? 1 : -1) * 3.2, 3.4, -10 - i * 13); cena.add(p); }

    // feixes de luz nas frestas do claristório (lado do sol)
    const dirFeixe = paraSol.map((x) => -x);
    const nFr = Math.floor((dim.comp + dim.espaco) / 2.6), passo = (dim.comp + dim.espaco) / nFr;
    const feixes = [];
    for (let i = 0; i < nFr; i++) {
      const z = dim.espaco / 2 - (i + 0.5) * passo;
      const f = criarFeixe({ origem: [-(dim.naveLarg / 2 + 1.75 * 1.1 + 0.6), 19.6, z], dir: dirFeixe, comp: 26, larg: 1.9, cor: 0xffd596, op: 0.38, esp: 0.9, fase: i * 0.9 });
      cena.add(f); feixes.push(f);
    }
    const poeira = criarPoeira3D({ semente: seed, n: 700, caixa: [-9, 0.5, -64, 9, 19, 4], vel: [0.06, 0.03, 0.04], cor: 0xffe2b0, tam: 1.6, op: 0.7 });
    cena.add(poeira);

    const trilho = criarTrilho({
      pos: [[-5.2, 1.7, -2], [-3.0, 2.1, -14], [0.4, 2.7, -26], [0.8, 3.3, -37]],
      alvo: [[-1.2, 8.0, -16], [0.0, 8.5, -30], [0.2, 7.0, -46], [0.0, 6.2, -62]],
      fov: [46, 38], curva: (x) => 0.35 * x + 0.65 * smooth(x),
    });
    return {
      ceu, trilho, ibl: 0.10, vinheta: 0.5, poeiraTela: 14,
      eventos: [{ t: 0.05, tipo: 'whoosh' }],
      atualizar(t) {
        poeira.material.uniforms.uT.value = t;
        for (const f of feixes) for (const m of f.userData.mats) m.uniforms.uT.value = t;
      },
    };
  },
};

export const cena3d_egito = { build: (palco, spec) => iniciar3D(palco, spec, def) };
