// Mar (lago) da Galileia ao amanhecer — PAISAGEM ARTÍSTICA por código: margem de seixos com juncos, barco de pesca puxado
// para a areia (escala do barco do século I achado em 1986), redes secando em varas, névoa sobre a água e as colinas da
// outra margem contra o sol nascente. Não reproduz um ponto exato da margem; não mostra pessoas.
// Vistas (params.vista): 'margem' (câmera baixa na praia, junto ao barco), 'lago' (rente à água, rumo a um barco ancorado),
//                        'colinas' (do alto da encosta, o lago inteiro abaixo), 'noite' (na beira d'água, lua e lamparina de um
//                        barco de pesca) e 'colinas_noite' (da encosta, a lua sobre o lago).
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho, criarNevoa } from '../engine/cena3d.js';
import { material, malha, terreno, rochedo, barcoPesca, texturaRede, oliveira, caixa, bosque } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

function brilho(op) {                              // brilho quente de chama (sprite aditivo, sempre de frente para a câmera)
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,236,200,1)'); gr.addColorStop(0.12, 'rgba(255,184,96,0.8)'); gr.addColorStop(0.4, 'rgba(255,140,60,0.18)'); gr.addColorStop(1, 'rgba(255,120,40,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, opacity: op }));
}

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };

function rede(w, h, mats) {                                 // rede pendurada entre duas varas (catenária + ondulação)
  const geo = new THREE.PlaneGeometry(w, h, 24, 12); const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), k = (x / w + 0.5); p.setY(i, y - 0.35 * Math.sin(Math.PI * k) * (0.5 - y / h)); p.setZ(i, 0.08 * Math.sin(x * 2.3 + y * 3)); }
  geo.computeVertexNormals();
  const g = new THREE.Group();
  const m = malha(geo, mats.rede, { pos: [0, h / 2 + 0.25, 0] }); m.castShadow = true; g.add(m);
  for (const s of [-1, 1]) g.add(malha(new THREE.CylinderGeometry(0.04, 0.05, h + 0.7, 6), mats.madeira, { pos: [s * w / 2, (h + 0.7) / 2, 0] }));
  return g;
}

const VISTAS = {
  margem: {
    ceu: { hor: 0xffbf86, meio: 0xd8c2c8, zen: 0x5778a8, baixo: 0x6a6050, sol: 0xffd4a0, expo: 0.42, brilho: 1.2, nuvens: 0.6, cobertura: 0.3, nuvem: 0xffe0c4, nuvemSombra: 0x8a8098 },
    paraSol: [0.3, 0.07, -0.95], sol: [0xffcf98, 3.8], hemi: [0xa6b6d4, 0x6a604c, 0.9], nevoa: [0xd8c4b4, 0.0012], exposicao: 0.95,
    trilho: { pos: [[-16, 1.5, 16], [-11, 1.45, 12.5], [-6.5, 1.35, 10.5]], alvo: [[5, 0.9, -6], [5.5, 0.8, -10], [6, 0.6, -16]], fov: [40, 34] },
  },
  lago: {
    ceu: { hor: 0xffb070, meio: 0xd4b0b8, zen: 0x4c6c9c, baixo: 0x5a5448, sol: 0xffcc90, expo: 0.4, brilho: 1.25, nuvens: 0.7, cobertura: 0.36, nuvem: 0xffd8b8, nuvemSombra: 0x7a7090 },
    paraSol: [0.12, 0.06, -0.99], sol: [0xffc890, 3.4], hemi: [0x9aaccc, 0x5a5444, 0.85], nevoa: [0xd0b4a8, 0.0011], exposicao: 0.92,
    trilho: { pos: [[-22, 1.1, -30], [-12, 1.2, -58], [-2, 1.3, -86]], alvo: [[18, 1.2, -128], [16, 1.4, -134], [14, 1.6, -140]], fov: [36, 30] },
  },
  noite: {
    ceu: { hor: 0x2a3660, meio: 0x111a3c, zen: 0x04061a, baixo: 0x080a14, sol: 0xb8c6f0, expo: 0.6, brilho: 0.42, nuvens: 0, estrelas: 2.6, via: 2.8, disco: 1.6 },
    paraSol: [-0.26, 0.3, -0.92], sol: [0x9fb4ff, 0.55], hemi: [0x4a5a8a, 0x1a1c24, 0.35], nevoa: [0x1a2238, 0.0007], exposicao: 1.15, noite: true,
    trilho: { pos: [[7, 1.5, -2], [8, 1.55, -5], [9, 1.6, -8]], alvo: [[10, 11, -80], [12, 14, -82], [14, 17, -84]], fov: [54, 50] },   // na beira d'água, avançando sobre o lago
  },
  colinas_noite: {
    ceu: { hor: 0x2a3660, meio: 0x111a3c, zen: 0x04061a, baixo: 0x080a14, sol: 0xb8c6f0, expo: 0.6, brilho: 0.42, nuvens: 0, estrelas: 2.6, via: 2.8, disco: 1.6 },
    paraSol: [-0.12, 0.17, -0.98], sol: [0x9fb4ff, 0.7], hemi: [0x4a5a8a, 0x1a1c24, 0.4], nevoa: [0x1a2238, 0.0005], exposicao: 1.25, noite: true,
    trilho: { pos: [[-46, 44, 196], [-30, 46, 182], [-12, 48, 170]], alvo: [[0, 22, -40], [8, 20, -70], [14, 18, -100]], fov: [42, 38] },   // da encosta, a lua sobre o lago
  },
  colinas: {
    ceu: { hor: 0xffc890, meio: 0xc8c6d8, zen: 0x5a80b4, baixo: 0x6a6050, sol: 0xffd8a8, expo: 0.45, brilho: 1.15, nuvens: 0.55, cobertura: 0.32, nuvem: 0xfff0dc, nuvemSombra: 0x9090a8 },
    paraSol: [0.45, 0.14, -0.88], sol: [0xffd6a6, 3.6], hemi: [0xa8bad8, 0x6a6448, 0.9], nevoa: [0xcfc6c0, 0.0009], exposicao: 0.95,
    trilho: { pos: [[-46, 44, 196], [-30, 46, 182], [-12, 48, 170]], alvo: [[0, 2, -40], [8, 0, -70], [14, -2, -100]], fov: [42, 38] },
  },
};

const def = {
  render: { exposicao: 1.0 },
  async montar({ cena, P, spec, r }) {
    const seed = spec.seed ?? 1;
    const V = VISTAS[P.vista] ?? VISTAS.margem;
    r.toneMappingExposure = V.exposicao;
    const paraSol = norm(V.paraSol);
    const ceu = criarCeu({ ...V.ceu, sunDir: paraSol });
    cena.fog = new THREE.FogExp2(V.nevoa[0], V.nevoa[1]);

    const tTerra = tex.terra({ tam: 1024, semente: 171, base: [150, 136, 110], seixos: 0.25 });
    const tRocha = tex.rocha({ tam: 1024, semente: 172, base: [96, 90, 84] });           // basalto escuro da região
    const tMad = tex.madeira({ tam: 512, semente: 173, base: [104, 74, 50] });
    const tAgua = tex.agua({ tam: 512, semente: 174 });
    const tVela = tex.pano({ tam: 512, semente: 175, cores: [[222, 210, 186], [206, 192, 166]], listras: 2 });
    const tRede = texturaRede(512, 20); tRede.repeat.set(3, 2);
    const mats = {
      chao: material(tTerra, { rep: [1, 1], normal: 0.6, rug: 1, env: 0.6, vertexColors: true }),
      rocha: material(tRocha, { rep: [1, 1], normal: 1.2, rug: 0.95, env: 0.6 }),
      madeira: material(tMad, { rep: [1, 1], normal: 0.8, rug: 0.85, env: 0.5 }),
      casco: material(tMad, { rep: [1, 1], normal: 1.0, rug: 0.8, env: 0.6, cor: 0xb89878 }),
      vela: material(tVela, { rep: [1, 2], normal: 0.4, rug: 1, env: 0.5 }),
      rede: new THREE.MeshStandardMaterial({ map: tRede, transparent: true, alphaTest: 0.35, side: THREE.DoubleSide, roughness: 1 }),
      junco: new THREE.MeshStandardMaterial({ color: 0x7a7c4a, roughness: 0.95 }),
      folha: new THREE.MeshStandardMaterial({ color: 0x5f6b4a, roughness: 0.95 }),
    };
    const N = tex.criarRuido(seed + 180);

    // margem próxima: praia de seixos que entra na água (z < 0), terra e capim subindo a encosta (z > 0)
    const altPerto = (x, z) => {
      const praia = z < 0 ? -1.6 * smooth(Math.min(1, -z / 14)) : 0.045 * z;
      const enc = z > 26 ? 0.0011 * Math.pow(z - 26, 2) * (0.8 + 0.4 * N.fbm(x * 0.01, z * 0.01, 3)) : 0;
      return praia + enc + 0.12 * N.fbm(x * 0.3, z * 0.3, 3) + 0.6 * N.fbm(x * 0.03, z * 0.03, 3) * smooth(Math.min(1, Math.max(0, z / 10)));
    };
    const perto = terreno({ larg: 520, prof: 360, nx: 260, nz: 200, centro: [0, 120], esc: 0.25, altura: altPerto,
      cor: (x, y, z) => { const molhado = 1 - smooth(Math.min(1, Math.max(0, (z + 1) / 4))); const capim = smooth(Math.min(1, Math.max(0, (z - 14) / 18)));
        const c = [0.86 - 0.3 * molhado, 0.82 - 0.3 * molhado, 0.74 - 0.28 * molhado];
        const v = N.fbm(x * 0.04 + 50, z * 0.04, 4), seco = smooth(Math.min(1, Math.max(0, v - 0.35) * 3));       // manchas de capim verde e capim seco
        return [c[0] - capim * (0.28 - 0.14 * seco), c[1] - capim * (0.06 - 0.02 * seco), c[2] - capim * (0.36 - 0.12 * seco)]; } });
    cena.add(malha(perto, mats.chao, { sombra: false }));
    // outra margem: colinas largas a ~2,5 km, sob névoa
    const altLonge = (x, z) => { const d = -z - 2100; if (d < 0) return -8; return 380 * smooth(Math.min(1, d / 900)) * (0.55 + 0.6 * N.cresta(x * 0.0011 + 3, z * 0.0011, 4)) - 8; };
    const longe = terreno({ larg: 9000, prof: 3000, nx: 240, nz: 90, centro: [0, -3400], esc: 0.01, altura: altLonge,
      cor: (x, y) => { const k = Math.min(1, Math.max(0, y / 300)); return [0.62 + 0.1 * k, 0.6 + 0.06 * k, 0.5 + 0.06 * k]; } });
    cena.add(malha(longe, mats.chao, { sombra: false }));

    // água
    const mAgua = new THREE.MeshStandardMaterial({ color: 0x2c4a50, roughness: 0.06, metalness: 0.0, envMapIntensity: 1.5 });
    mAgua.normalMap = tAgua.normalMap.clone(); mAgua.normalMap.repeat.set(900, 900); mAgua.normalMap.needsUpdate = true; mAgua.normalScale = new THREE.Vector2(0.35, 0.35);
    const agua = new THREE.Mesh(new THREE.PlaneGeometry(9000, 9000), mAgua); agua.rotation.x = -Math.PI / 2; agua.position.y = 0; cena.add(agua);

    // barco na areia, barco ancorado, redes, juncos, pedras de basalto e oliveiras na encosta
    const b1 = barcoPesca({ mats }); b1.position.set(5.5, 0.62, 0.6); b1.rotation.set(0.04, -0.55, 0.09); cena.add(b1);
    const b2 = barcoPesca({ mats, remos: false }); b2.position.set(16, 0.55, -132); b2.rotation.y = 0.8; cena.add(b2);
    // à noite, uma lamparina de óleo no barco ancorado (pesca noturna, Lc 5,5) e o seu reflexo alongado na água
    const lamparina = V.noite ? brilho(0.9) : null, reflexo = V.noite ? brilho(0.32) : null;
    if (lamparina) {
      lamparina.scale.set(5, 5, 1); reflexo.scale.set(1.4, 7, 1); reflexo.position.set(16, -2.6, -131);
      reflexo.material.depthTest = false; reflexo.renderOrder = 2;                // o reflexo fica sob o plano opaco da água
      cena.add(lamparina, reflexo);
      const luzB = new THREE.PointLight(0xffa050, 6, 26, 1.6); luzB.position.set(16, 1.9, -131.5); cena.add(luzB);
    }
    const r1 = rede(3.6, 1.7, mats); r1.position.set(-1.0, altPerto(-1.0, 4.2), 4.2); r1.rotation.y = 0.5; cena.add(r1);
    const r2 = rede(3.0, 1.5, mats); r2.position.set(2.6, altPerto(2.6, 7.5), 7.5); r2.rotation.y = -0.2; cena.add(r2);
    const rr = rngFor(seed, 41);
    const geoJ = new THREE.ConeGeometry(0.025, 1, 4); geoJ.translate(0, 0.5, 0);
    const nJ = 2600, juncos = new THREE.InstancedMesh(geoJ, mats.junco, nJ); const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    for (let i = 0; i < nJ; i++) {
      const tufo = Math.floor(rr() * 26), cx = -60 + (tufo * 37) % 120 + (tufo % 3) * 4, x = cx + (rr() - 0.5) * 3.5, z = -1.2 + (rr() - 0.3) * 2.6;
      if (x > 0 && x < 12) { m4.makeScale(0, 0, 0); juncos.setMatrixAt(i, m4); continue; }
      e.set((rr() - 0.5) * 0.3, rr() * 6, (rr() - 0.5) * 0.3); q.setFromEuler(e);
      const h = 0.9 + rr() * 1.4; m4.compose(new THREE.Vector3(x, altPerto(x, z) - 0.05, z), q, new THREE.Vector3(1, h, 1)); juncos.setMatrixAt(i, m4);
    }
    juncos.castShadow = true; cena.add(juncos);
    for (let i = 0; i < 40; i++) { const x = (rr() - 0.5) * 60, z = -2 + rr() * 9; if (x > 2 && x < 10 && z < 4) continue; cena.add(malha(rochedo(0.15 + Math.pow(rr(), 2) * 0.7, seed * 90 + i), mats.rocha, { pos: [x, altPerto(x, z) - 0.05, z] })); }
    for (const [x, z, h, sd] of [[-18, 34, 4.6, 1], [-6, 44, 5.0, 2], [9, 38, 4.2, 3], [22, 52, 4.8, 4], [-30, 58, 4.4, 5], [36, 70, 5.0, 6], [-44, 82, 4.6, 7], [4, 90, 4.4, 8]]) {
      const o = oliveira({ h, mats, seed: sd + seed * 10 }); o.position.set(x, altPerto(x, z), z); cena.add(o);
    }
    // bosques de oliveiras na encosta (instanciados)
    const pts = [];
    // olivais plantados em fileiras (talhões com orientação própria), com falhas e variação de tamanho
    for (let tz = 0; tz < 6; tz++) for (let tx = 0; tx < 9; tx++) {
      const cx = -220 + tx * 52 + (rr() - 0.5) * 12, cz = 48 + tz * 42 + (rr() - 0.5) * 10;
      if (Math.abs(cx + 30) < 40 && cz > 140 && cz < 240) continue;                 // clareira onde a câmera fica
      if (N.fbm(cx * 0.01 + 9, cz * 0.01, 3) < 0.42) continue;                      // nem todo talhão é olival
      const ang = (rr() - 0.5) * 0.5, ca = Math.cos(ang), sa = Math.sin(ang);
      for (let i = 0; i < 6; i++) for (let j = 0; j < 5; j++) {
        if (rr() < 0.12) continue;
        const lx = (i - 2.5) * 7.5 + (rr() - 0.5) * 1.2, lz = (j - 2) * 7.5 + (rr() - 0.5) * 1.2;
        const x = cx + lx * ca - lz * sa, z = cz + lx * sa + lz * ca;
        pts.push([x, altPerto(x, z) - 0.1, z, 0.75 + rr() * 0.45, rr() * 6]);
      }
    }
    cena.add(bosque({ pontos: pts, mats, seed }));
    // um muro baixo de pedra seca na encosta (terraços)
    for (let i = 0; i < 18; i++) { const x = -40 + i * 4.6, z = 30 + 2 * Math.sin(i * 0.7); cena.add(malha(caixa(4.4, 0.7, 0.8, { raio: 0.15, esc: 0.6 }), mats.rocha, { pos: [x, altPerto(x, z) + 0.3, z] })); }

    // vista do alto (colinas), a névoa rasante vira mancha sobre a água: fica só um véu
    const nv1 = criarNevoa({ y: 1.2, cor: V.noite ? 0x3a4668 : 0xffe6d0, op: V.noite ? 0.35 : P.vista === 'colinas' ? 0.16 : 0.5, esc: 0.006, perto: 40, longe: 2600, tam: 6000 });
    const nv2 = criarNevoa({ y: 18, cor: V.noite ? 0x2a3450 : 0xf0dccc, op: V.noite ? 0.2 : 0.3, esc: 0.003, perto: 300, longe: 3200, tam: 7000 });
    cena.add(nv1, nv2);
    const sol = criarSol({ cor: V.sol[0], intensidade: V.sol[1], dir: paraSol, alvo: (P.vista || '').startsWith('colinas') ? [0, 10, 60] : [0, 1, 0], dist: 200, caixa: (P.vista || '').startsWith('colinas') ? 140 : 40, mapa: 4096, bias: -0.0003, normalBias: 0.05, near: 20, far: 500 });
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(V.hemi[0], V.hemi[1], V.hemi[2]));
    const poeira = criarPoeira3D({ semente: seed, n: V.noite ? 0 : 160, caixa: [-20, 0.3, -20, 20, 6, 16], vel: [0.12, 0.03, 0.05], cor: 0xffe8c8, tam: 1.2, op: 0.45 });
    cena.add(poeira);

    const T = V.trilho;
    const trilho = criarTrilho({ pos: T.pos, alvo: T.alvo, fov: T.fov, curva: (x) => 0.35 * x + 0.65 * smooth(x) });
    return {
      ceu, trilho, ibl: 0.9, vinheta: 0.5, poeiraTela: 0, tremor: { pos: 0.006, ang: 0.025 },
      eventos: [],
      atualizar(t) {
        poeira.material.uniforms.uT.value = t;
        nv1.material.uniforms.uT.value = t; nv2.material.uniforms.uT.value = t;
        mAgua.normalMap.offset.set((t * 0.0012) % 1, (t * 0.0005) % 1);
        b2.position.y = 0.55 + 0.03 * Math.sin(t * 0.9); b2.rotation.z = 0.02 * Math.sin(t * 0.7);    // o barco ancorado balança de leve
        if (lamparina) { const f = 0.9 + 0.06 * Math.sin(t * 7.1) + 0.04 * Math.sin(t * 12.7); lamparina.position.set(16, 1.9 + b2.position.y - 0.55, -131.5); lamparina.material.opacity = 0.9 * f; reflexo.material.opacity = 0.32 * f; }
      },
    };
  },
};

export const cena3d_galileia = { build: (palco, spec) => iniciar3D(palco, spec, def) };
