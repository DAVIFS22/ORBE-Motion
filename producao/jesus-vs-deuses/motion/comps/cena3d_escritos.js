// Rolo e lamparina — COMPOSIÇÃO ARTÍSTICA por código para os trechos sobre as Escrituras: um rolo aberto sobre uma mesa de
// madeira, lamparina de barro acesa, sala de pedra na penumbra. A "escrita" do rolo é ESTILIZADA (traços abstratos em colunas):
// não reproduz nenhum manuscrito nem texto real.
// Vistas (params.vista): 'mesa' (câmera desliza sobre o rolo), 'lamparina' (a chama em primeiro plano, o rolo atrás),
//                        'rolo' (rente ao pergaminho, ao longo das colunas).
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarPoeira3D, criarTrilho } from '../engine/cena3d.js';
import { caixa, material, malha, revolucao, juntar } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

// Textura do pergaminho: fibras, manchas e colunas de traços abstratos (não é escrita real).
function texturaRolo(seed, colunas = 5) {
  const W = 2048, H = 512; const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  const R = tex.criarRuido(seed), r = rngFor(seed, 3);
  const im = g.createImageData(W, H);
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
    const u = i / W, v = j / H, k = 0.82 + 0.12 * R.fbm(u * 12, v * 3, 5) + 0.04 * R.noise(u * 300, v * 80) - 0.18 * Math.pow(R.fbm(u * 3 + 7, v * 2, 3), 3);
    const q = (j * W + i) * 4; im.data[q] = 226 * k; im.data[q + 1] = 204 * k; im.data[q + 2] = 160 * k; im.data[q + 3] = 255;
  }
  g.putImageData(im, 0, 0);
  g.fillStyle = 'rgba(52,36,24,0.78)';
  const larg = W / colunas;
  for (let cI = 0; cI < colunas; cI++) {
    const x0 = cI * larg + larg * 0.12, x1 = x0 + larg * 0.74;
    for (let y = 46; y < H - 40; y += 17) {
      let x = x0 + r() * 6;
      while (x < x1 - 8) { const w = 4 + r() * 16; g.globalAlpha = 0.55 + 0.4 * r(); g.fillRect(x, y + r() * 2, w, 2.4 + r() * 1.4); x += w + 3 + r() * 6; }
    }
  }
  g.globalAlpha = 1;
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}

const VISTAS = {
  mesa: { pos: [[-0.25, 1.6, 1.05], [0.02, 1.5, 0.92], [0.28, 1.42, 0.82]], alvo: [[0.12, 0.79, -0.08], [0.2, 0.79, -0.09], [0.3, 0.79, -0.1]], fov: [40, 34] },
  lamparina: { pos: [[1.62, 0.96, 0.18], [1.55, 0.95, 0.12], [1.48, 0.94, 0.08]], alvo: [[0.9, 0.82, -0.4], [0.82, 0.82, -0.38], [0.72, 0.82, -0.34]], fov: [36, 32] },
  rolo: { pos: [[-0.62, 0.91, 0.22], [-0.4, 0.89, 0.19], [-0.15, 0.88, 0.16]], alvo: [[0.3, 0.8, -0.12], [0.5, 0.8, -0.12], [0.72, 0.8, -0.12]], fov: [40, 36] },
};

const def = {
  render: { exposicao: 1.0 },
  async montar({ cena, P, spec, r }) {
    const seed = spec.seed ?? 1;
    r.toneMappingExposure = 1.1;
    cena.background = new THREE.Color(0x0a0806);
    cena.fog = new THREE.FogExp2(0x0e0906, 0.22);

    const tMad = tex.madeira({ tam: 1024, semente: 191, base: [110, 76, 48] });
    const tPedra = tex.blocos({ tam: 1024, semente: 192, fiadas: 6, comprimento: [0.3, 0.5], base: [150, 132, 104], desgaste: 0.8 });
    const tBarro = tex.terra({ tam: 512, semente: 193, base: [168, 104, 62], seixos: 0 });
    const mats = {
      mesa: material(tMad, { rep: [1, 1], normal: 1.0, rug: 0.75, env: 0.3 }),
      madeira: material(tMad, { rep: [1, 1], normal: 0.8, rug: 0.7, env: 0.3, cor: 0x8a6448 }),
      parede: material(tPedra, { rep: [1, 1], normal: 1.0, rug: 1, env: 0.2, cor: 0x7a6a58 }),
      barro: material(tBarro, { rep: [1, 1], normal: 0.6, rug: 0.85, env: 0.3 }),
      rolo: new THREE.MeshStandardMaterial({ map: texturaRolo(seed + 7), roughness: 0.92, side: THREE.DoubleSide }),
      verso: new THREE.MeshStandardMaterial({ color: 0xc8b088, roughness: 0.95 }),
    };

    // sala: piso, parede ao fundo e à esquerda (pedra), mesa
    cena.add(malha(caixa(8, 0.1, 8, { raio: 0.01, esc: 0.6 }), mats.parede, { pos: [0, -0.05, 0] }));
    cena.add(malha(caixa(8, 3.2, 0.3, { raio: 0.02, esc: 0.6 }), mats.parede, { pos: [0, 1.6, -1.6] }));
    cena.add(malha(caixa(0.3, 3.2, 8, { raio: 0.02, esc: 0.6 }), mats.parede, { pos: [-2.4, 1.6, 0] }));
    cena.add(malha(caixa(2.2, 0.07, 1.1, { raio: 0.01, esc: 0.9 }), mats.mesa, { pos: [0.2, 0.74, -0.1] }));
    for (const [x, z] of [[-0.75, -0.55], [1.15, -0.55], [-0.75, 0.35], [1.15, 0.35]]) cena.add(malha(caixa(0.08, 0.72, 0.08, { raio: 0.01 }), mats.mesa, { pos: [x, 0.36, z] }));

    // rolo aberto: folha levemente curva entre dois cilindros enrolados
    const Lf = 1.25, Hf = 0.36;
    const folha = new THREE.PlaneGeometry(Lf, Hf, 80, 12); folha.rotateX(-Math.PI / 2);
    { const p = folha.attributes.position; for (let i = 0; i < p.count; i++) { const x = p.getX(i), z = p.getZ(i); p.setY(i, 0.006 * Math.sin(x * 9) + 0.012 * Math.pow(Math.abs(z) / (Hf / 2), 4) + 0.03 * Math.pow(Math.abs(x) / (Lf / 2), 6)); } folha.computeVertexNormals(); }
    const rolo = new THREE.Group(); rolo.position.set(0.2, 0.785, -0.08); rolo.rotation.y = -0.08;
    rolo.add(malha(folha, mats.rolo));
    for (const s of [-1, 1]) {
      const cil = new THREE.CylinderGeometry(0.058, 0.058, Hf + 0.01, 32); cil.rotateX(Math.PI / 2);
      rolo.add(malha(cil, mats.verso, { pos: [s * (Lf / 2 + 0.045), 0.052, 0] }));
      for (const z of [-1, 1]) { const pino = new THREE.CylinderGeometry(0.014, 0.018, 0.09, 12); pino.rotateX(Math.PI / 2); rolo.add(malha(pino, mats.madeira, { pos: [s * (Lf / 2 + 0.045), 0.052, z * (Hf / 2 + 0.05)] })); }
    }
    cena.add(rolo);
    // outro rolo fechado, um jarro e a lamparina
    const fechado = new THREE.CylinderGeometry(0.07, 0.07, 0.4, 32); fechado.rotateZ(Math.PI / 2);
    const rf = malha(fechado, mats.verso, { pos: [-0.55, 0.81, 0.22] }); rf.rotation.y = 0.5; cena.add(rf);
    const jarro = revolucao(juntar([[0.0, 0], [0.09, 0.01], [0.13, 0.12], [0.12, 0.24], [0.06, 0.32], [0.065, 0.36], [0.0, 0.36]]), { seg: 40, escV: 0.6 });
    cena.add(malha(jarro, mats.barro, { pos: [-0.62, 0.775, -0.42] }));
    const lamp = revolucao(juntar([[0.0, 0], [0.05, 0.004], [0.07, 0.025], [0.06, 0.045], [0.02, 0.05], [0.0, 0.048]]), { seg: 40, escV: 0.6 });
    const lampada = malha(lamp, mats.barro, { pos: [1.12, 0.775, -0.42] }); lampada.scale.set(1.25, 1, 0.85); cena.add(lampada);
    const bico = malha(caixa(0.06, 0.02, 0.03, { raio: 0.008 }), mats.barro, { pos: [1.21, 0.81, -0.42] }); cena.add(bico);
    const gChama = new THREE.SphereGeometry(0.007, 16, 12); gChama.scale(1, 2.6, 1); gChama.translate(0, 0.016, 0);       // chama em gota
    const chama = new THREE.Mesh(gChama, new THREE.MeshBasicMaterial({ color: 0xffe2a8 }));
    chama.position.set(1.24, 0.818, -0.42); cena.add(chama);
    const halo = new THREE.Mesh(new THREE.SphereGeometry(0.02, 16, 12), new THREE.MeshBasicMaterial({ color: 0xff9a40, transparent: true, opacity: 0.25, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.position.copy(chama.position).add(new THREE.Vector3(0, 0.016, 0)); cena.add(halo);

    const luz = new THREE.PointLight(0xffb060, 2.9, 6, 1.5); luz.position.set(1.24, 0.86, -0.42); luz.castShadow = true;
    luz.shadow.mapSize.set(2048, 2048); luz.shadow.bias = -0.0015; luz.shadow.radius = 6; cena.add(luz);
    const janela = new THREE.DirectionalLight(0x6a86c8, 0.35); janela.position.set(-2, 3, 2); cena.add(janela);
    cena.add(new THREE.HemisphereLight(0x3a3a50, 0x1a120c, 0.28));
    const poeira = criarPoeira3D({ semente: seed, n: 140, caixa: [-0.6, 0.8, -0.7, 1.4, 1.8, 0.6], vel: [0.008, 0.004, 0.006], cor: 0xffd8a8, tam: 0.12, op: 0.5 });
    cena.add(poeira);

    const T = VISTAS[P.vista] ?? VISTAS.mesa;
    const trilho = criarTrilho({ pos: T.pos, alvo: T.alvo, fov: T.fov, curva: (x) => 0.35 * x + 0.65 * smooth(x) });
    return {
      ceu: null, trilho, ibl: false, vinheta: 0.6, poeiraTela: 0, tremor: { pos: 0.0015, ang: 0.01 },
      eventos: [],
      atualizar(t) {
        const f = 1 + 0.06 * Math.sin(t * 9.1) + 0.04 * Math.sin(t * 15.7 + 1.3) + 0.03 * Math.sin(t * 23.3 + 0.4);   // a chama tremula (função de t)
        luz.intensity = 2.6 * f; chama.scale.set(1, 0.9 + 0.12 * Math.sin(t * 11.3), 1); halo.material.opacity = 0.3 * f;
        poeira.material.uniforms.uT.value = t;
      },
    };
  },
};

export const cena3d_escritos = { build: (palco, spec) => iniciar3D(palco, spec, def) };
