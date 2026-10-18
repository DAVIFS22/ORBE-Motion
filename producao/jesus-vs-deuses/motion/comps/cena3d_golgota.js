// Colina das cruzes (Gólgota) — RECONSTRUÇÃO ARTÍSTICA por código. Os Evangelhos situam a crucificação fora da cidade e
// perto dela (João 19:17–20); a localização exata, o relevo e a forma das cruzes não são conhecidos com certeza.
// Três cruzes de madeira VAZIAS no alto de uma colina pedregosa, muralha distante em silhueta. Sem pessoas, sem violência.
// Vistas (params.vista): 'tempestade' (céu carregado ao entardecer, câmera baixa subindo a encosta),
//                        'amanhecer' (as mesmas cruzes contra o nascer do sol, névoa baixa), 'distante' (plano geral com a muralha).
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho, criarFeixe } from '../engine/cena3d.js';
import { caixa, material, malha, terreno, rochedo as pedra, obelisco, colunaPapiro, temploDorico } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };
const TOPO = [0, -60];
const ESC_CRUZ_CAPA = 1.3;                                    // centro do cume (x, z)


function cruz({ alt, larg, mats, seed, titulo = false }) {
  const g = new THREE.Group(); const r = rngFor(seed, 7);
  const haste = malha(caixa(0.3, alt, 0.28, { raio: 0.02, esc: 0.6 }), mats.madeira, { pos: [0, alt / 2 - 0.6, 0] });
  const trave = malha(caixa(larg, 0.26, 0.26, { raio: 0.02, esc: 0.6 }), mats.madeira, { pos: [0, alt * 0.74 - 0.6, 0.04] });
  g.add(haste, trave);
  if (titulo) g.add(malha(caixa(0.7, 0.32, 0.05, { raio: 0.01 }), mats.placa, { pos: [0, alt - 0.45, 0.16] }));
  // pedras amontoadas na base
  for (let i = 0; i < 7; i++) { const a = r() * Math.PI * 2, d = 0.35 + r() * 0.35; g.add(malha(pedra(0.22 + r() * 0.2, seed * 10 + i), mats.pedra, { pos: [Math.cos(a) * d, 0.05, Math.sin(a) * d] })); }
  g.rotation.set((r() - 0.5) * 0.05, (r() - 0.5) * 0.3, (r() - 0.5) * 0.06);
  return g;
}

function muralha({ x0, x1, z, h, mats, seed }) {          // muralha com torres e ameias e o casario da cidade por trás, em silhueta
  const g = new THREE.Group(); const r = rngFor(seed, 11);
  for (let i = 0; i < 260; i++) {                          // casario baixo de teto plano (3–6 m) subindo devagar a encosta atrás do muro
    const x = x0 + r() * (x1 - x0), dz = 8 + r() * 110, w = 4 + r() * 7, d = 4 + r() * 6, hh = 3 + r() * 3;
    const base = 3 + dz * 0.07 + 2 * Math.sin(x * 0.02);
    g.add(malha(caixa(w, hh, d, { raio: 0.05, esc: 0.1 }), mats.casa, { pos: [x, base + hh / 2, z - dz] }));
  }
  const L = x1 - x0;
  g.add(malha(caixa(L, h, 6, { raio: 0.1, esc: 0.08 }), mats.muro, { pos: [(x0 + x1) / 2, h / 2, z] }));
  for (let x = x0 + 3; x < x1; x += 4.2) g.add(malha(caixa(2.2, 1.6, 6.2, { raio: 0.05, esc: 0.1 }), mats.muro, { pos: [x, h + 0.8, z] }));
  for (let x = x0 + 12; x < x1 - 8; x += 38 + r() * 14) {
    const th = h + 6 + r() * 5;
    g.add(malha(caixa(10, th, 10, { raio: 0.1, esc: 0.08 }), mats.muro, { pos: [x, th / 2, z + 1] }));
  }
  return g;
}

const VISTAS = {
  tempestade: {
    ceu: { hor: 0xb86c46, meio: 0x4a4250, zen: 0x12141c, baixo: 0x2a221c, sol: 0xffa060, expo: 0.62, brilho: 0.95, nuvens: 1.0, cobertura: 0.82, nuvem: 0x7a6a66, nuvemSombra: 0x18161c },
    paraSol: [0.86, 0.07, -0.5], sol: [0xffa070, 2.8], hemi: [0x5a5e74, 0x3a2e22, 0.62], nevoa: [0x4a3e3c, 0.0042], exposicao: 1.32,     // fim de tarde sob nuvens pesadas: escuro, mas legível
    trilho: { pos: [[-9, 4.5, 34], [-5, 7.5, 10], [-1.5, 12.5, -16]], alvo: [[0, 21, -60], [0, 23.5, -61], [0, 25, -62]], fov: [38, 30] },
    poeira: { n: 900, vel: [1.6, 0.15, 0.4], op: 0.55 }, feixes: 0,
  },
  amanhecer: {
    ceu: { hor: 0xffa458, meio: 0xf0b48c, zen: 0x4a6a9c, baixo: 0x5a4436, sol: 0xffd09a, expo: 0.38, brilho: 1.15, nuvens: 0.75, cobertura: 0.42, nuvem: 0xffd0a8, nuvemSombra: 0x7a6070 },
    paraSol: [-0.42, 0.1, -0.9], sol: [0xffc48a, 3.2], hemi: [0x98a6c8, 0x5a4638, 0.8], nevoa: [0xc89a80, 0.0036], exposicao: 0.86,
    trilho: { pos: [[-26, 15.5, 8], [-12, 16.5, 2], [6, 17.5, 4]], alvo: [[-2, 23, -60], [0, 23.5, -60], [2, 23.5, -60]], fov: [30, 28] },
    poeira: { n: 500, vel: [0.25, 0.06, 0.1], op: 0.8 }, feixes: 4,
  },
  capa: {        // capa do vídeo: câmera baixa na encosta, o sol nascendo atrás da cruz central, tempestade se abrindo
    ceu: { hor: 0xff8a3a, meio: 0x8a3a3a, zen: 0x0c0e1c, baixo: 0x1a1210, sol: 0xffa850, expo: 0.5, brilho: 0.55, nuvens: 1.0, cobertura: 0.7, nuvem: 0xff9a5a, nuvemSombra: 0x120e16, disco: 0.55 },
    paraSol: [0.27, 0.36, -0.89], sol: [0xffb878, 3.2], hemi: [0x5a4a68, 0x1e1410, 0.28], nevoa: [0x5a3028, 0.0026], exposicao: 0.9,
    trilho: { pos: [[-10, 12.5, -28], [-10, 12.5, -28]], alvo: [[-13, 22.5, -61], [-13, 22.5, -61]], fov: [30, 30] },
    poeira: { n: 600, vel: [0.3, 0.05, 0.1], op: 0.9 }, feixes: 6,
  },
  distante: {
    ceu: { hor: 0xe49a62, meio: 0x86728a, zen: 0x283050, baixo: 0x3a3028, sol: 0xffc08a, expo: 0.5, brilho: 1.1, nuvens: 0.85, cobertura: 0.55, nuvem: 0xd8a890, nuvemSombra: 0x3a3448 },
    paraSol: [-0.62, 0.12, -0.78], sol: [0xffbe8a, 3.0], hemi: [0x8a8aa8, 0x4a3a2e, 0.75], nevoa: [0x9a8478, 0.0026], exposicao: 1.0,
    trilho: { pos: [[58, 19, 150], [42, 21, 132]], alvo: [[2, 20, -60], [0, 21, -62]], fov: [24, 22] },
    poeira: { n: 300, vel: [0.6, 0.05, 0.2], op: 0.5 }, feixes: 0,
  },
};

const def = {
  render: { exposicao: 1.0 },
  async montar({ cena, P, D, spec, r }) {
    const seed = spec.seed ?? 1;
    const V = VISTAS[P.vista] ?? VISTAS.tempestade;
    r.toneMappingExposure = V.exposicao;
    let paraSol = norm(V.paraSol);
    cena.fog = new THREE.FogExp2(V.nevoa[0], V.nevoa[1]);

    const tRocha = tex.rocha({ tam: 1024, semente: 131, base: [150, 136, 116] });
    const tTerra = tex.terra({ tam: 1024, semente: 132, base: [138, 116, 86], seixos: 0.35 });
    const tMad = tex.madeira({ tam: 512, semente: 133, base: [86, 60, 40] });
    const tMuro = tex.blocos({ tam: 1024, semente: 134, fiadas: 8, comprimento: [0.3, 0.5], base: [190, 172, 140], desgaste: 0.7 });
    const mats = {
      madeira: material(tMad, { rep: [1, 1], normal: 1.4, rug: 0.95, env: 0.5 }),
      placa: material(tMad, { rep: [1, 1], normal: 0.6, rug: 0.9, cor: 0xc8b496 }),
      pedra: material(tRocha, { rep: [1, 1], normal: 1.2, rug: 1, env: 0.45, cor: 0x9c8c78 }),
      muro: material(tMuro, { rep: [1, 1], normal: 0.8, rug: 1, env: 0.4 }),
      casa: material(tex.reboco({ tam: 512, semente: 135, base: [200, 186, 160], remendos: 0.3 }), { rep: [1, 1], normal: 0.5, rug: 1, env: 0.4 }),
    };

    // colina: cúpula alongada com saliências de rocha, sobre uma planície ondulada
    const R = tex.criarRuido(seed + 140);
    const altura = (x, z) => {
      const dx = (x - TOPO[0]) / 52, dz = (z - TOPO[1]) / 40;
      const colina = 22 * Math.exp(-(dx * dx + dz * dz) * 1.15);
      const rocha = 2.4 * R.cresta(x * 0.05, z * 0.05, 4) * Math.min(1, colina / 6);
      return colina + rocha + 2.2 * R.fbm(x * 0.01, z * 0.01, 4) - 1.5;
    };
    const chao = terreno({ larg: 1400, prof: 1400, nx: 260, nz: 260, centro: [0, -200], esc: 0.08, altura,
      cor: (x, y, z, ny) => { const k = smooth(Math.min(1, Math.max(0, (0.93 - ny) / 0.2))); return [0.78 + 0.14 * k, 0.70 + 0.1 * k, 0.56 + 0.1 * k]; } });
    const mChao = material(tTerra, { rep: [1, 1], normal: 0.8, rug: 1, env: 0.6, vertexColors: true });
    const mc = malha(chao, mChao, { sombra: false });
    if (P.dbg === 'semSombraChao') mc.receiveShadow = false;
    if (P.dbg === 'semNormalChao') mChao.normalMap = null;
    cena.add(mc);

    // afloramentos de rocha na encosta (instanciados)
    const rr = rngFor(seed, 21);
    const geoPedra = pedra(1, seed + 5);
    const nP = 140, inst = new THREE.InstancedMesh(geoPedra, mats.pedra, nP);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    for (let i = 0; i < nP; i++) {
      const a = rr() * Math.PI * 2, d = 6 + Math.pow(rr(), 0.7) * 60;
      const x = TOPO[0] + Math.cos(a) * d * 1.25, z = TOPO[1] + Math.sin(a) * d;
      const s = 0.4 + Math.pow(rr(), 2.2) * 2.6;
      e.set(rr() * 3, rr() * 3, rr() * 3); q.setFromEuler(e);
      m4.compose(new THREE.Vector3(x, altura(x, z) - 0.2 * s, z), q, new THREE.Vector3(s, s * 0.8, s));
      inst.setMatrixAt(i, m4);
    }
    inst.castShadow = true; inst.receiveShadow = true;
    cena.add(inst);
    // blocos de rocha perto do início dos trilhos de câmera (paralaxe de primeiro plano)
    for (const [x, z, s, sd] of [[-14, 22, 2.6, 1], [-3, 30, 1.6, 2], [4, 18, 2.2, 3], [-20, 6, 3.0, 4], [10, 26, 1.4, 5], [-30, 12, 2.4, 6], [18, 4, 2.8, 7]]) {
      const m = malha(pedra(s, seed * 7 + sd), mats.pedra, { pos: [x, altura(x, z) - 0.25 * s, z] }); m.rotation.y = sd; cena.add(m);
    }

    // vegetação rala de colina seca: arbustos baixos e touceiras de capim (escala e textura de primeiro plano)
    const mArb = new THREE.MeshStandardMaterial({ color: 0x55573a, roughness: 1 }), mCap = new THREE.MeshStandardMaterial({ color: 0xb09a64, roughness: 1 });
    const nA = 260, arb = new THREE.InstancedMesh(pedra(1, seed + 9), mArb, nA);
    for (let i = 0; i < nA; i++) {
      const a = rr() * Math.PI * 2, d = 9 + Math.pow(rr(), 0.6) * 90, x = TOPO[0] + Math.cos(a) * d * 1.25, z = TOPO[1] + Math.sin(a) * d, s = 0.6 + rr() * 0.9;
      e.set(0, rr() * 6, 0); q.setFromEuler(e); m4.compose(new THREE.Vector3(x, altura(x, z) - 0.1 * s, z), q, new THREE.Vector3(s * 1.2, s * 1.05, s * 1.1)); arb.setMatrixAt(i, m4);
    }
    arb.castShadow = true; arb.receiveShadow = true; cena.add(arb);
    const geoC = new THREE.ConeGeometry(0.035, 1, 3); geoC.translate(0, 0.5, 0);
    const nC = 36000, cap = new THREE.InstancedMesh(geoC, mCap, nC);
    for (let i = 0, k = 0; i < nC; i++) {
      if (i % 12 === 0) k = i;                                                                // touceiras de 12 folhas
      const r0 = rngFor(seed * 31 + k, 3), a = r0() * Math.PI * 2, d = 7 + Math.sqrt(r0()) * 95;                  // densidade uniforme na encosta
      const x = TOPO[0] + Math.cos(a) * d * 1.25 + (rr() - 0.5) * 0.5, z = TOPO[1] + Math.sin(a) * d + (rr() - 0.5) * 0.5;
      e.set((rr() - 0.5) * 0.7, rr() * 6, (rr() - 0.5) * 0.7); q.setFromEuler(e);
      m4.compose(new THREE.Vector3(x, altura(x, z) - 0.05, z), q, new THREE.Vector3(1.2, 0.45 + rr() * 0.6, 1.2)); cap.setMatrixAt(i, m4);
    }
    cap.castShadow = true; cena.add(cap);

    // as três cruzes (a do centro mais alta, com a placa do título), no cume
    const yTopo = altura(TOPO[0], TOPO[1]);
    // capa: câmera 1,7 m acima do chão e o sol exatamente atrás do cruzamento da cruz central
    let T = V.trilho, camCapa = null;
    if (P.vista === 'capa') {
      const cx = P.capa?.cam?.[0] ?? -22, cz = P.capa?.cam?.[1] ?? 48, cy = altura(cx, cz) + (P.capa?.cam?.[2] ?? 2.5);     // fora do campo de pedras: lente longa
      const al = P.capa?.alvo ?? [-12, yTopo + 1.5, -61];
      T = { ...T, pos: [[cx, cy, cz], [cx, cy, cz]], alvo: [al, al], fov: [P.capa?.fov ?? 12, P.capa?.fov ?? 12] }; camCapa = [cx, cy, cz];
      const alvoSol = [TOPO[0] - cx, yTopo + ESC_CRUZ_CAPA * (6.6 * 0.74 - 0.6) - cy, TOPO[1] - 1.2 - cz];
      paraSol = norm(alvoSol);
    }
    const ceu = criarCeu({ ...V.ceu, sunDir: paraSol });
    if (camCapa) ceu.malha.position.set(...camCapa);         // céu centrado na câmera: o sol fica exatamente atrás da cruz (sem paralaxe da cúpula)
    for (const [dx, alt, sd, tit] of [[-5.2, 5.4, 1, false], [0, 6.6, 2, true], [5.4, 5.3, 3, false]]) {
      const c = cruz({ alt, larg: 2.4, mats, seed: seed * 10 + sd, titulo: tit });
      const x = TOPO[0] + dx, z = TOPO[1] + (dx === 0 ? -1.2 : 0.6);
      c.position.set(x, altura(x, z) - 0.15, z);
      if (P.vista === 'capa') c.scale.setScalar(ESC_CRUZ_CAPA);                         // na capa as cruzes precisam ler em miniatura
      cena.add(c);
    }

    // muralha da cidade ao longe (silhueta na névoa)
    const mu = muralha({ x0: -260, x1: 140, z: -330, h: 13, mats, seed });
    mu.rotation.y = 0.12; cena.add(mu);

    const sol = criarSol({ cor: V.sol[0], intensidade: V.sol[1], dir: paraSol, alvo: [0, yTopo, TOPO[1]], dist: 160, caixa: 70, mapa: 4096, bias: -0.0003, normalBias: 0.06, near: 20, far: 360 });
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(V.hemi[0], V.hemi[1], V.hemi[2]));

    const feixes = [];
    for (let i = 0; i < V.feixes; i++) {
      const f = criarFeixe({ origem: [TOPO[0] - 30 + i * 18, 70, TOPO[1] - 70], dir: [-paraSol[0] * 0.6 + (i - 1.5) * 0.04, -1, -paraSol[2] * 0.5], comp: 90, larg: 7 + i, cor: 0xffd8a8, op: 0.07, esp: 2, fase: i * 1.7 });
      cena.add(f); feixes.push(f);
    }
    const poeira = criarPoeira3D({ semente: seed, n: V.poeira.n, caixa: [-40, yTopo - 8, TOPO[1] - 40, 40, yTopo + 18, 40], vel: V.poeira.vel, cor: 0xffe0b8, tam: 2.4, op: V.poeira.op });
    cena.add(poeira);

    const trilho = criarTrilho({ pos: T.pos, alvo: T.alvo, fov: T.fov, curva: (x) => 0.35 * x + 0.65 * smooth(x) });
    return {
      ceu, trilho, ibl: 0.8, vinheta: 0.55, poeiraTela: 0,
      eventos: [],
      atualizar(t) { poeira.material.uniforms.uT.value = t; for (const f of feixes) for (const m of f.userData.mats) m.uniforms.uT.value = t; },
    };
  },
};

export const cena3d_golgota = { build: (palco, spec) => iniciar3D(palco, spec, def) };
