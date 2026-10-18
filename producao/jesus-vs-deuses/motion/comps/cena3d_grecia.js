// Templo dórico — RECONSTRUÇÃO ARTÍSTICA por código, inspirada no Templo de Zeus em Olímpia (c. 470–457 a.C.): 6 × 13 colunas,
// crepidoma de três degraus, entablamento com tríglifos e métopas, frontões, telhado e cela. Luz de fim de tarde com sombras,
// colinas procedurais, cipreste instanciados e câmera em guindaste. Nada aqui é evidência arqueológica (sem policromia, sem esculturas).
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho } from '../engine/cena3d.js';
import { temploDorico, material, malha, terreno } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };

const def = {
  render: { exposicao: 1.0 },
  async montar({ cena, P, D, spec }) {
    const seed = spec.seed ?? 1;
    const paraSol = norm([-0.78, 0.36, 0.5]);            // sol baixo, à esquerda e à frente do templo (luz rasante dourada)
    const ceu = criarCeu({ hor: 0xffd9a8, meio: 0x9fc4ec, zen: 0x2c63b4, baixo: 0x6a5a40, sol: 0xffd49a, sunDir: paraSol, expo: 0.38, brilho: 1.25, nuvens: 0.8, cobertura: 0.32, nuvem: 0xfff0dc, nuvemSombra: 0x8a8aa8 });
    cena.fog = new THREE.FogExp2(0xefc99a, 0.0017);

    const tM1 = tex.marmore({ tam: 1024, semente: 52, tambores: 11, base: [232, 222, 200], veios: 0.35 });
    const tM2 = tex.marmore({ tam: 1024, semente: 54, tambores: 1, base: [232, 222, 202], veios: 0.3 });
    const tBloco = tex.blocos({ tam: 1024, semente: 56, fiadas: 5, comprimento: [0.5, 0.9], base: [222, 208, 180], desgaste: 0.5 });
    const tTerra = tex.terra({ tam: 1024, semente: 58, base: [140, 120, 78] });
    const tRocha = tex.rocha({ tam: 1024, semente: 59, base: [150, 140, 120] });
    const mats = {
      fuste: material(tM1, { rep: [1, 1], normal: 0.8, rug: 0.78, env: 0.9 }),
      capitel: material(tM1, { rep: [1, 1], normal: 0.8, rug: 0.8, env: 0.9 }),
      arquitrave: material(tM2, { rep: [0.35, 0.35], normal: 0.8, rug: 0.8, env: 0.9 }),
      triglifo: material(tM2, { rep: [0.5, 0.5], normal: 0.6, rug: 0.8, vertexColors: true, cor: 0xe6d8b8 }),
      metopa: material(tM2, { rep: [0.35, 0.35], normal: 0.6, rug: 0.85, cor: 0xcdb99a }),
      cornija: material(tM2, { rep: [0.35, 0.35], normal: 0.8, rug: 0.8, env: 0.9 }),
      timpano: material(tM2, { rep: [0.25, 0.25], normal: 0.6, rug: 0.9, cor: 0x8c8f98 }),
      telha: material(tM2, { rep: [0.3, 0.3], normal: 0.9, rug: 0.7, cor: 0xe8d6b4 }),
      degrau: material(tBloco, { rep: [1, 1], normal: 0.9, rug: 0.9, env: 0.8 }),
      cela: material(tBloco, { rep: [1, 1], normal: 0.9, rug: 0.9, env: 0.8, cor: 0xe6dcc6 }),
    };
    const templo = temploDorico({ nF: 6, nL: 13, D: 2.25, H: 10.4, entre: 5.2, mats, estrias: 20 });
    cena.add(templo);
    const dim = templo.userData.dim;

    // terraço, colinas e rocha: altura procedural determinística
    const R = tex.criarRuido(seed + 70);
    const hx = 58, hz = 82;
    const altura = (x, z) => {
      const dx = Math.max(0, Math.abs(x) - hx), dz = Math.max(0, Math.abs(z) - hz), d = Math.hypot(dx, dz);
      const k = smooth(Math.min(1, d / 90));
      const colinas = 38 * Math.pow(R.fbm(x * 0.008 + 3, z * 0.008, 5), 2.2) + 26 * smooth(Math.min(1, Math.max(0, (-z - 60) / 260)));
      const beira = -2.2 * smooth(Math.min(1, d / 14));                  // talude suave do terraço
      return -1.72 + beira + k * (colinas - 2) + 0.35 * R.fbm(x * 0.05, z * 0.05, 3) * k;
    };
    const solo = terreno({ larg: 1100, prof: 1100, nx: 190, nz: 190, centro: [0, -140], esc: 0.06, altura,
      cor: (x, y, z, ny) => { const verde = Math.min(1, Math.max(0, (ny - 0.72) / 0.2)); const alt = Math.min(1, Math.max(0, (y + 2) / 40));
        const g = [0.52 - 0.10 * alt, 0.55 - 0.08 * alt, 0.28 + 0.05 * alt], r = [0.80, 0.68, 0.46]; return [r[0] + (g[0] - r[0]) * verde, r[1] + (g[1] - r[1]) * verde, r[2] + (g[2] - r[2]) * verde]; } });
    const mSolo = material(tTerra, { rep: [1, 1], normal: 1.0, rug: 1, env: 0.6, vertexColors: true });
    cena.add(malha(solo, mSolo, { sombra: false }));
    // pavimento do terraço
    const tLaje = tex.lajes({ tam: 1024, semente: 61, n: 5, base: [190, 176, 150] });
    const pav = new THREE.Mesh(new THREE.PlaneGeometry(2 * hx, 2 * hz), material(tLaje, { rep: [16, 22], normal: 0.9, rug: 0.95 }));
    pav.rotation.x = -Math.PI / 2; pav.position.set(0, -1.7, 0); pav.receiveShadow = true; cena.add(pav);

    // ciprestes instanciados (cones estreitos) nas bordas do terraço e encostas
    const nC = 90, geo = new THREE.ConeGeometry(0.85, 9, 7, 1); geo.translate(0, 4.5, 0);
    const cip = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0x24341f, roughness: 1 }), nC);
    const rr = rngFor(seed, 88), M = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), sc = new THREE.Vector3();
    let n = 0;
    for (let tent = 0; n < nC && tent < 4000; tent++) {
      const x = (rr() - 0.5) * 420, z = 40 - rr() * 380;
      if (Math.abs(x) < hx + 8 && Math.abs(z) < hz + 8) continue;                       // não invade o terraço
      const y = altura(x, z); if (y > 30) continue;
      const s = 0.7 + rr() * 1.1; q.setFromEuler(new THREE.Euler(0, rr() * 6.28, 0));
      p.set(x, y - 0.2, z); sc.set(s, s * (0.9 + rr() * 0.5), s); M.compose(p, q, sc); cip.setMatrixAt(n++, M);
    }
    cip.count = n; cip.castShadow = true; cip.receiveShadow = true; cip.instanceMatrix.needsUpdate = true; cena.add(cip);

    // luzes
    const sol = criarSol({ cor: 0xffd29a, intensidade: 5.6, dir: paraSol, alvo: [0, 4, 0], dist: 160, caixa: 62, mapa: 4096, bias: -0.0003, normalBias: 0.07, near: 30, far: 380 });
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(0xa4aabc, 0x7a6040, 0.55));          // céu menos saturado: a sombra não fica azul demais
    const poeira = criarPoeira3D({ semente: seed, n: 500, caixa: [-45, 0, -45, 45, 22, 80], vel: [0.2, 0.04, -0.08], cor: 0xffe2b0, tam: 1.8, op: 0.6 });
    cena.add(poeira);

    // guindaste: sobe e contorna a fachada em arco; pedimento e colunas entram em quadro
    const trilho = criarTrilho({
      pos: [[-36, 1.9, 58], [-24, 4.2, 70], [-3, 8.5, 80], [22, 12.5, 74], [38, 15, 58]],
      alvo: [[-7, 5.5, 33], [-4, 8.5, 28], [0, 10.5, 18], [2, 10, 10], [3, 8.5, 2]],
      fov: [44, 34], curva: (x) => 0.3 * x + 0.7 * smooth(x),
    });
    return {
      ceu, trilho, ibl: 0.55, vinheta: 0.5, poeiraTela: 18,
      eventos: [{ t: 0.05, tipo: 'whoosh' }],
      atualizar(t) { poeira.material.uniforms.uT.value = t; },
    };
  },
};

export const cena3d_grecia = { build: (palco, spec) => iniciar3D(palco, spec, def) };
