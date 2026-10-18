// Túmulo vazio — RECONSTRUÇÃO ARTÍSTICA por código de um túmulo escavado na rocha, do tipo usado na Judeia do século I
// (fachada de calcário, entrada baixa, pedra circular rolada para o lado, câmara com banco de sepultamento). Os Evangelhos
// falam de um jardim junto ao lugar (João 19:41), da pedra removida (Marcos 16:3–4) e dos panos de linho deixados na
// câmara (João 20:5–7). NÃO é o local histórico; não mostra pessoas.
// Vistas (params.vista): 'exterior' (jardim ao amanhecer, câmera chega à entrada), 'interior' (feixe de luz sobre o banco
// com os panos), 'saida' (de dentro da câmara para a luz da manhã).
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho, criarFeixe } from '../engine/cena3d.js';
import { caixa, material, malha, terreno, rochedo, oliveira } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };
const PORTA = { x0: -0.62, x1: 0.62, y1: 1.65 };          // abertura da entrada (m)
const CAM = { x0: -1.9, x1: 1.9, y1: 2.25, z0: -0.55, z1: -4.1 };   // câmara interna

// Topo irregular do maciço (altura da borda em x).
export const topoRocha = (N, x) => 8.6 + 2.6 * N.fbm(x * 0.045 + 11, 3.3, 4) + 1.2 * Math.sin(x * 0.07 + 1);

// Parede de rocha (plano vertical em z=0 voltado para +z) com forma em grande escala (convexa/côncava), estratos, borda
// superior arredondada e manchas de intempérie (cor por vértice). Perto da porta a superfície é lavrada (plana).
function paredeRocha(x0, x1, y0, y1, N, nx, ny) {
  const g = new THREE.PlaneGeometry(x1 - x0, y1 - y0, nx, ny); g.translate((x0 + x1) / 2, (y0 + y1) / 2, 0);
  const p = g.attributes.position, uv = g.attributes.uv; const cores = new Float32Array(p.count * 3);
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y0v = p.getY(i);
    const topo = topoRocha(N, x);
    const y = Math.min(y0v, topo + 0.6);
    const dx = Math.max(0, Math.abs(x) - 1.5), dy = Math.max(0, y - 2.5);      // painel lavrado de 3 × 2,5 m em volta da entrada
    const bruto = smooth(Math.min(1, Math.hypot(dx, dy) / 1.1));
    const forma = 1.6 * Math.sin(x * 0.075 + 0.4) + 2.4 * (N.fbm(x * 0.028 + 5, 0.5, 3) - 0.5) + 0.04 * x * x * 0.02;
    const rel = 0.75 * N.fbm(x * 0.2, y * 0.2, 5) + 0.3 * N.cresta(x * 0.55, y * 0.55, 3) - 0.55 + 0.12 * Math.sin(y * 2.6 + 2 * N.fbm(x * 0.3, y * 0.1, 2));
    const arred = y > topo - 1.4 ? -Math.pow((y - (topo - 1.4)) / 2.0, 2) * 2.2 : 0;   // a borda de cima recua (arredondada)
    let z = (forma + rel - 0.7) * bruto + arred - 0.015 * N.fbm(x * 3, y * 3, 2);
    const perto = 1 - smooth(Math.min(1, Math.max(0, (Math.abs(x) - 3.5) / 4)));
    z = z - perto * Math.max(0, z);                                                              // perto da entrada a rocha nunca avança sobre a pedra (transição suave)
    p.setXYZ(i, x, y, z);
    uv.setXY(i, x * 0.16, y * 0.16);
    const fundo = smooth(Math.min(1, Math.max(0, 0.5 - rel) * 1.6)) * bruto;                        // reentrâncias mais escuras (oclusão aproximada)
    const mancha = (0.86 + 0.2 * N.fbm(x * 0.5 + 40, y * 0.05, 3) - 0.12 * smooth(Math.max(0, (topo - y) / topo)) * N.fbm(x * 1.5, 7, 2)) * (1 - 0.38 * fundo);
    cores[3 * i] = mancha; cores[3 * i + 1] = mancha * 0.98; cores[3 * i + 2] = mancha * 0.93;
  }
  g.setAttribute('color', new THREE.BufferAttribute(cores, 3));
  g.computeVertexNormals();
  return g;
}

// Plano interno da câmara (normal voltada para dentro), com leve irregularidade de rocha escavada.
function planoCamara(w, h, N, transf) {
  const g = new THREE.PlaneGeometry(w, h, 24, 16); const p = g.attributes.position, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i); p.setZ(i, 0.04 * N.fbm(x * 1.4 + 9, y * 1.4, 3)); uv.setXY(i, x * 0.45, y * 0.45); }
  g.computeVertexNormals(); transf(g);
  return g;
}

function linho(w, d, seed) {                               // pano de linho com dobras (grade deslocada)
  const g = new THREE.PlaneGeometry(w, d, 40, 18); g.rotateX(-Math.PI / 2);
  const p = g.attributes.position; const N = tex.criarRuido(seed);
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), z = p.getZ(i); p.setY(i, 0.035 * Math.sin(x * 9 + 2 * N.noise(x * 2, z * 2)) * (0.6 + 0.4 * N.fbm(x * 3, z * 3, 3)) + 0.05 * N.fbm(x * 1.5, z * 1.5, 3)); }
  g.computeVertexNormals();
  return g;
}

const VISTAS = {
  exterior: {
    ceu: { hor: 0xffc08a, meio: 0xc8c4d8, zen: 0x5a7cb0, baixo: 0x6a5844, sol: 0xffd6a0, expo: 0.45, brilho: 1.2, nuvens: 0.55, cobertura: 0.32, nuvem: 0xffe4c8, nuvemSombra: 0x8a8098 },
    paraSol: [-0.86, 0.26, 0.44], sol: [0xffd0a0, 4.6], hemi: [0xa8b8d8, 0x6a5a44, 0.85], ibl: 0.9, nevoa: [0xe8cdb0, 0.006], exposicao: 0.95,
    trilho: { pos: [[-5.5, 1.1, 15], [-3.2, 1.0, 10.5], [-1.4, 0.95, 6.2]], alvo: [[1.2, 2.4, 0], [1.0, 1.7, 0], [0.6, 1.2, -1]], fov: [46, 40] },
    feixes: false,
  },
  interior: {
    ceu: { hor: 0xffc890, meio: 0xd0c8d8, zen: 0x6a88b8, baixo: 0x6a5844, sol: 0xffdcb0, expo: 0.45, brilho: 1.2, nuvens: 0.4, cobertura: 0.3, nuvem: 0xffe8d0, nuvemSombra: 0x9a90a8 },
    paraSol: [0.08, 0.26, 0.96], sol: [0xffd8a8, 7.5], hemi: [0x6a6a78, 0x3a3028, 0.16], ibl: 0.1, nevoa: [0x2a2420, 0.02], exposicao: 1.2, rebate: 1.6,
    trilho: { pos: [[-1.25, 1.55, -1.1], [-0.7, 1.4, -1.9], [-0.15, 1.3, -2.45]], alvo: [[0.3, 0.8, -3.6], [0.35, 0.78, -3.65], [0.4, 0.75, -3.7]], fov: [56, 48] },
    feixes: true,
  },
  saida: {
    ceu: { hor: 0xffd0a0, meio: 0xd8d0e0, zen: 0x6a8cc0, baixo: 0x6a5844, sol: 0xffe0b8, expo: 0.45, brilho: 1.3, nuvens: 0.45, cobertura: 0.3, nuvem: 0xfff0dc, nuvemSombra: 0xa098b0 },
    paraSol: [0.2, 0.16, 0.97], sol: [0xffdcb0, 5.0], hemi: [0x5a5a68, 0x2a2420, 0.18], ibl: 0.12, nevoa: [0xf0dcc0, 0.008], exposicao: 0.82, rebate: 1.2,
    trilho: { pos: [[0.5, 1.2, -3.5], [0.25, 1.15, -2.8], [0.05, 1.1, -2.1]], alvo: [[0, 1.3, 4], [0, 1.3, 5], [0, 1.3, 6]], fov: [52, 46] },
    feixes: true,
  },
};

const def = {
  render: { exposicao: 1.0 },
  async montar({ cena, P, spec, r }) {
    const seed = spec.seed ?? 1;
    const V = VISTAS[P.vista] ?? VISTAS.exterior;
    r.toneMappingExposure = V.exposicao;
    const paraSol = norm(V.paraSol);
    const ceu = criarCeu({ ...V.ceu, sunDir: paraSol });
    cena.fog = new THREE.FogExp2(V.nevoa[0], V.nevoa[1]);

    const tCal = tex.calcario({ tam: 1024, semente: 151, base: [214, 200, 172] });
    const tTerra = tex.terra({ tam: 1024, semente: 152, base: [116, 106, 74], seixos: 0.4 });
    const tMad = tex.madeira({ tam: 512, semente: 153, base: [92, 66, 44] });
    const tPano = tex.pano({ tam: 512, semente: 154, cores: [[226, 218, 198], [214, 206, 186]], listras: 1 });
    const mats = {
      calcario: material(tCal, { rep: [1, 1], normal: 1.7, rug: 0.95, env: 0.5, vertexColors: true }),
      camara: material(tCal, { rep: [1, 1], normal: 0.9, rug: 0.95, env: 0.2, cor: 0xd8c8b0 }),
      lavrado: material(tCal, { rep: [1, 1], normal: 0.5, rug: 0.9, env: 0.5, cor: 0xf0e4cc }),
      pedra: material(tCal, { rep: [1, 1], normal: 1.6, rug: 0.95, env: 0.5, cor: 0xb8a890 }),
      chao: material(tTerra, { rep: [1, 1], normal: 0.9, rug: 1, env: 0.6, vertexColors: true }),
      madeira: material(tMad, { rep: [1, 1], normal: 0.8, rug: 0.9, env: 0.5 }),
      folha: new THREE.MeshStandardMaterial({ color: 0x7a8668, roughness: 0.95 }),
      arbusto: new THREE.MeshStandardMaterial({ color: 0x4a5636, roughness: 1 }),
      linho: material(tPano, { rep: [2, 2], normal: 0.3, rug: 0.9, env: 0.5, cor: 0xfffaf0 }),
    };
    const N = tex.criarRuido(seed + 160);

    // fachada de rocha em três peças (esquerda, direita, sobre a porta) com o mesmo ruído: as bordas coincidem
    const fach = new THREE.Group(); cena.add(fach);
    for (const [x0, x1, y0, y1, nx, ny] of [[-34, PORTA.x0, 0, 13, 170, 70], [PORTA.x1, 34, 0, 13, 170, 70], [PORTA.x0, PORTA.x1, PORTA.y1, 13, 8, 64]]) {
      fach.add(malha(paredeRocha(x0, x1, y0, y1, N, nx, ny), mats.calcario));
    }
    // topo do maciço, ligeiramente irregular, com oliveiras e arbustos em silhueta
    const topo = terreno({ larg: 70, prof: 40, nx: 90, nz: 40, centro: [0, -21.2], esc: 0.2, altura: (x, z) => topoRocha(N, x) - 0.2 - 1.6 * Math.exp(-Math.pow((z + 1.4) / 1.2, 2)) * 0 + 0.6 * N.fbm(x * 0.08, z * 0.08, 4) + Math.max(0, -z - 3) * 0.05 });
    cena.add(malha(topo, mats.chao, { sombra: false }));
    for (const [x, z, h, sd] of [[-14, -6, 4.4, 11], [9, -9, 4.8, 12], [21, -5, 3.9, 13], [-25, -10, 5.0, 14], [2, -12, 4.2, 15]]) { const o = oliveira({ h, mats, seed: sd }); o.position.set(x, topoRocha(N, x) + 0.2, z); cena.add(o); }

    // passagem da porta (espessura da rocha) e câmara interna
    const esp = Math.abs(CAM.z0);
    fach.add(malha(caixa(0.06, PORTA.y1, esp, { raio: 0.01 }), mats.lavrado, { pos: [PORTA.x0 - 0.03, PORTA.y1 / 2, -esp / 2] }));
    fach.add(malha(caixa(0.06, PORTA.y1, esp, { raio: 0.01 }), mats.lavrado, { pos: [PORTA.x1 + 0.03, PORTA.y1 / 2, -esp / 2] }));
    fach.add(malha(caixa(PORTA.x1 - PORTA.x0 + 0.12, 0.06, esp, { raio: 0.01 }), mats.lavrado, { pos: [0, PORTA.y1 + 0.03, -esp / 2] }));
    const W = CAM.x1 - CAM.x0, H = CAM.y1, D = Math.abs(CAM.z1 - CAM.z0), zc = (CAM.z0 + CAM.z1) / 2;
    const cam = new THREE.Group(); cena.add(cam);
    cam.add(malha(planoCamara(W, H, N, (g) => g.translate(0, H / 2, CAM.z1)), mats.camara));                                   // fundo
    cam.add(malha(planoCamara(D, H, N, (g) => { g.rotateY(Math.PI / 2); g.translate(CAM.x0, H / 2, zc); }), mats.camara));      // esquerda
    cam.add(malha(planoCamara(D, H, N, (g) => { g.rotateY(-Math.PI / 2); g.translate(CAM.x1, H / 2, zc); }), mats.camara));     // direita
    cam.add(malha(planoCamara(W, D, N, (g) => { g.rotateX(Math.PI / 2); g.translate(0, H, zc); }), mats.camara));               // teto
    cam.add(malha(planoCamara(W, D, N, (g) => { g.rotateX(-Math.PI / 2); g.translate(0, 0, zc); }), mats.camara));              // piso
    // parede da frente da câmara, com o vão da porta (voltada para dentro)
    const sh = new THREE.Shape([new THREE.Vector2(CAM.x0, 0), new THREE.Vector2(CAM.x1, 0), new THREE.Vector2(CAM.x1, H), new THREE.Vector2(CAM.x0, H)]);
    sh.holes.push(new THREE.Path([new THREE.Vector2(PORTA.x0, 0), new THREE.Vector2(PORTA.x0, PORTA.y1), new THREE.Vector2(PORTA.x1, PORTA.y1), new THREE.Vector2(PORTA.x1, 0)]));
    const gf = new THREE.ShapeGeometry(sh); gf.rotateY(Math.PI); gf.translate(0, 0, CAM.z0);
    { const uv = gf.attributes.uv, p = gf.attributes.position; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) * 0.45, p.getY(i) * 0.45); }
    cam.add(malha(gf, mats.camara));
    // banco de sepultamento ao fundo e os panos de linho
    cam.add(malha(caixa(W - 0.2, 0.72, 0.85, { raio: 0.03, esc: 0.45 }), mats.lavrado, { pos: [0, 0.36, CAM.z1 + 0.45] }));
    const pano = malha(linho(1.7, 0.62, seed + 3), mats.linho, { pos: [0.15, 0.735, CAM.z1 + 0.47] }); pano.rotation.y = 0.04; cam.add(pano);
    const lenco = malha(caixa(0.36, 0.06, 0.28, { raio: 0.025 }), mats.linho, { pos: [-1.15, 0.76, CAM.z1 + 0.42] }); lenco.rotation.y = 0.3; cam.add(lenco);   // o lenço dobrado à parte (João 20:7)

    // pedra circular rolada para o lado, apoiada na fachada, e o canal à frente da entrada
    const disco = new THREE.CylinderGeometry(0.98, 0.98, 0.4, 56, 1); disco.rotateX(Math.PI / 2);
    { const p = disco.attributes.position, uv = disco.attributes.uv;
      for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i), rr2 = Math.hypot(x, y), a = Math.atan2(y, x);
        const f = 1 + 0.035 * N.fbm(Math.cos(a) * 2 + 4, Math.sin(a) * 2 + z, 3) - (rr2 > 0.9 ? 0.03 * Math.abs(z) / 0.2 : 0);   // borda gasta e irregular
        p.setXYZ(i, x * f, y * f, z * (1 + 0.15 * N.fbm(x * 1.5, y * 1.5, 3) - 0.07)); uv.setXY(i, x * 0.4 + z, y * 0.4); }
      disco.computeVertexNormals(); }
    const roda = malha(disco, mats.pedra, { pos: [1.75, 0.98, 0.3] }); roda.rotation.y = -0.05; cena.add(roda);
    cena.add(malha(caixa(5.4, 0.12, 0.5, { raio: 0.02 }), mats.lavrado, { pos: [0.9, -0.03, 0.3] }));

    // jardim: chão, caminho, oliveiras, arbustos e rochas soltas
    const chao = terreno({ larg: 180, prof: 160, nx: 140, nz: 120, centro: [0, 70], esc: 0.22,
      altura: (x, z) => 0.25 * N.fbm(x * 0.05, z * 0.05, 4) * smooth(Math.min(1, z / 3)) + 0.004 * z * z * 0.02,
      cor: (x, y, z) => { const verde = 0.5 + 0.5 * N.fbm(x * 0.07 + 20, z * 0.07, 4); const caminho = Math.exp(-Math.pow((x - 0.6 + 0.1 * z) / 1.3, 2)) * (z > 0.8 ? 1 : 0);
        return [0.82 - 0.18 * verde + 0.15 * caminho, 0.8 + 0.06 * verde + 0.08 * caminho, 0.62 - 0.12 * verde + 0.12 * caminho]; } });
    cena.add(malha(chao, mats.chao, { sombra: false }));
    const rr = rngFor(seed, 31);
    for (const [x, z, h, sd] of [[-9, 9, 4.6, 1], [7.5, 13, 4.2, 2], [-15, 22, 5.0, 3], [12, 25, 4.8, 4], [-3.2, 17, 4.4, 5], [17, 7, 3.8, 6], [-22, 6, 4.4, 7], [2.8, 24, 4.6, 8]]) {
      const o = oliveira({ h, mats, seed: sd + seed * 10 }); o.position.set(x, 0, z); o.rotation.y = rr() * 6; cena.add(o);
    }
    for (let i = 0; i < 26; i++) { const x = (rr() - 0.5) * 30, z = 1.5 + rr() * 24; if (Math.abs(x - 0.6 + 0.1 * z) < 1.8) continue;
      const s = 0.22 + rr() * 0.3; const m = malha(rochedo(1, seed * 70 + i), mats.arbusto, { pos: [x, s * 0.25, z] }); m.scale.set(s * 1.4, s * 0.9, s * 1.3); cena.add(m); }
    for (let i = 0; i < 16; i++) { const x = (rr() - 0.5) * 26, z = 0.8 + rr() * 6; if (Math.abs(x) < 3.2) continue; cena.add(malha(rochedo(0.3 + rr() * 0.6, seed * 50 + i), mats.pedra, { pos: [x, 0.05, z] })); }

    const alvoSol = P.vista === 'exterior' ? [0, 2, 6] : [0, 1, -2];
    const sol = criarSol({ cor: V.sol[0], intensidade: V.sol[1], dir: paraSol, alvo: alvoSol, dist: 90, caixa: P.vista === 'exterior' ? 34 : 12, mapa: 4096, bias: -0.0002, normalBias: 0.03, near: 10, far: 220 });
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(V.hemi[0], V.hemi[1], V.hemi[2]));
    if (V.rebate) {                                         // luz rebatida pela poça de sol no chão da câmara (sem sombra)
      const pl = new THREE.PointLight(0xffc89a, V.rebate, 4.5, 1.6); pl.position.set(0.1, 0.25, -2.0); cena.add(pl);
      const p2 = new THREE.PointLight(0xffd6aa, V.rebate * 1.4, 3.2, 1.3); p2.position.set(0.1, 1.45, -2.55); cena.add(p2);   // a poça de sol rebate nos panos
    }
    const feixes = [];
    if (V.feixes) {                                         // a luz da manhã entra pela porta e alcança o banco
      const d = [-paraSol[0], -paraSol[1], -paraSol[2]];
      for (let i = 0; i < 2; i++) { const f = criarFeixe({ origem: [0.0 + (i - 0.5) * 0.4 - d[0] * 1.5, 1.2 - d[1] * 1.5, 0.6 - d[2] * 1.5], dir: d, comp: 6, larg: 0.9, cor: 0xffe2b8, op: 0.09, esp: 1.6, fase: i * 2 }); cena.add(f); feixes.push(f); }
    }
    const poeira = criarPoeira3D({ semente: seed, n: P.vista === 'exterior' ? 260 : 260, caixa: P.vista === 'exterior' ? [-8, 0.2, -1, 8, 6, 24] : [-1.8, 0.1, -4, 1.8, 2.2, 1.5], vel: [0.05, 0.02, 0.03], cor: 0xffe6c0, tam: P.vista === 'exterior' ? 1.4 : 0.22, op: 0.7 });
    cena.add(poeira);

    const T = V.trilho;
    const trilho = criarTrilho({ pos: T.pos, alvo: T.alvo, fov: T.fov, curva: (x) => 0.35 * x + 0.65 * smooth(x) });
    return {
      ceu, trilho, ibl: V.ibl, vinheta: 0.55, poeiraTela: 0, tremor: { pos: 0.004, ang: 0.02 },
      eventos: [],
      atualizar(t) { poeira.material.uniforms.uT.value = t; for (const f of feixes) for (const m of f.userData.mats) m.uniforms.uT.value = t; },
    };
  },
};

export const cena3d_tumulo = { build: (palco, spec) => iniciar3D(palco, spec, def) };
