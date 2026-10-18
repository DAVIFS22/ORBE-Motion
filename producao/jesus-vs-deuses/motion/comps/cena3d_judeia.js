// Aldeia da Galileia/Judeia do século I — RECONSTRUÇÃO ARTÍSTICA por código (casas de pedra e reboco, terraços planos, vielas de terra
// batida, panos ao sol, oliveiras). Baseada em tipos de construção modestos da região; NÃO reproduz um sítio específico (nem Nazaré)
// e não mostra pessoas. Contraluz de fim de tarde, poeira no ar e câmera em trilho.
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho } from '../engine/cena3d.js';
import { casaJudeia, banca, anfora, oliveira, caixa, material, malha, terreno, revolucao, bosque } from '../engine/arq.js';
import { rngFor } from '../engine/rng.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };

// Arco de pedra sobre a viela: parede com abertura em arco pleno.
function arcoPedra(larg, alt, esp, mats) {
  const w = larg + 2.2, h = alt + 1.2;
  const sh = new THREE.Shape([new THREE.Vector2(-w / 2, 0), new THREE.Vector2(w / 2, 0), new THREE.Vector2(w / 2, h), new THREE.Vector2(-w / 2, h)]);
  const furo = new THREE.Path(); const r = larg / 2, yc = alt - r;
  furo.moveTo(-r, 0); furo.lineTo(-r, yc); furo.absarc(0, yc, r, Math.PI, 0, true); furo.lineTo(r, 0); furo.lineTo(-r, 0);
  sh.holes.push(furo);
  const g = new THREE.ExtrudeGeometry(sh, { depth: esp, bevelEnabled: false, curveSegments: 18 });
  g.translate(0, 0, -esp / 2); g.computeVertexNormals();
  const uv = g.attributes.uv, p = g.attributes.position, n = g.attributes.normal;
  for (let i = 0; i < p.count; i++) { const ax = Math.abs(n.getX(i)), az = Math.abs(n.getZ(i)); uv.setXY(i, (az > ax ? p.getX(i) : p.getZ(i)) * 0.3, p.getY(i) * 0.3); }
  return malha(g, mats.pedra);
}

function varal(a, b, y, mats, seed, n = 5) {         // pano estendido entre duas paredes (catenária suave)
  const g = new THREE.Group(), r = rngFor(seed, 12);
  const L = Math.hypot(b[0] - a[0], b[2] - a[2]);
  const corda = [];
  for (let i = 0; i <= 12; i++) { const k = i / 12; corda.push(new THREE.Vector3(a[0] + (b[0] - a[0]) * k, y - 0.22 * Math.sin(Math.PI * k), a[2] + (b[2] - a[2]) * k)); }
  g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(corda), new THREE.LineBasicMaterial({ color: 0x3a2a1a })));
  for (let i = 0; i < n; i++) {
    const k = 0.1 + (i + r() * 0.5) / n * 0.8, c = corda[Math.round(k * 12)];
    const geo = new THREE.PlaneGeometry(0.55 + r() * 0.4, 0.8 + r() * 0.5, 4, 6); const p = geo.attributes.position;
    for (let j = 0; j < p.count; j++) p.setZ(j, 0.05 * Math.sin(p.getY(j) * 5 + i));
    geo.computeVertexNormals();
    const m = malha(geo, mats.pano[i % mats.pano.length], { pos: [c.x, c.y - 0.45, c.z] });
    m.material.side = THREE.DoubleSide; m.rotation.y = Math.atan2(b[0] - a[0], b[2] - a[2]) + Math.PI / 2;
    g.add(m);
  }
  return g;
}

const def = {
  render: { exposicao: 1.05 },
  async montar({ cena, P, D, spec }) {
    const seed = spec.seed ?? 1;
    const paraSol = norm([0.5, 0.3, -0.8]);                  // contraluz baixo, à direita e à frente da viela
    const ceu = criarCeu({ hor: 0xffcf94, meio: 0xa8c4e4, zen: 0x3b72b8, baixo: 0x7a6a50, sol: 0xffd9a0, sunDir: paraSol, expo: 0.4, brilho: 1.3, nuvens: 0.55, cobertura: 0.28, nuvem: 0xfff0d8, nuvemSombra: 0x9a9ab8 });
    const alto = P.vista === 'telhados';                     // do alto, a névoa abre para mostrar as colinas e as casas da encosta
    cena.fog = alto ? new THREE.FogExp2(0xc4c4b8, 0.0023) : new THREE.FogExp2(0xe6c196, 0.0085);

    const tReb1 = tex.reboco({ tam: 1024, semente: 81, base: [216, 200, 168], remendos: 0.55 });
    const tReb2 = tex.reboco({ tam: 1024, semente: 83, base: [204, 184, 150], remendos: 0.7 });
    const tPedra = tex.blocos({ tam: 1024, semente: 85, fiadas: 7, comprimento: [0.3, 0.55], base: [196, 178, 146], desgaste: 0.8 });
    const tTerra = tex.terra({ tam: 1024, semente: 87, base: [152, 124, 88] });
    const tMad = tex.madeira({ tam: 512, semente: 89, base: [96, 66, 40] });
    const tPano = [tex.pano({ tam: 512, semente: 91, cores: [[168, 66, 48], [226, 206, 168]], listras: 4 }), tex.pano({ tam: 512, semente: 92, cores: [[52, 96, 124], [214, 196, 160]], listras: 3 }),
      tex.pano({ tam: 512, semente: 93, cores: [[196, 150, 60], [232, 220, 190]], listras: 5 })];
    const mats = {
      reboco: material(tReb1, { rep: [1, 1], normal: 1.1, rug: 1, env: 0.6 }),
      pedra: material(tPedra, { rep: [1, 1], normal: 1.0, rug: 1, env: 0.6 }),
      terraco: material(tTerra, { rep: [1, 1], normal: 0.8, rug: 1, env: 0.5, cor: 0xcbb08a }),
      madeira: material(tMad, { rep: [1, 1], normal: 0.8, rug: 0.9, env: 0.5 }),
      porta: material(tMad, { rep: [1, 1], normal: 0.9, rug: 0.9, cor: 0xa08064 }),
      toldo: material(tPano[0], { rep: [1, 1], normal: 0.4, rug: 1 }),
      barro: material(tTerra, { rep: [2, 2], normal: 0.6, rug: 0.95, cor: 0xd29868 }),
      folha: new THREE.MeshStandardMaterial({ color: 0x707a50, roughness: 0.9 }),
      pano: tPano.map((t) => material(t, { rep: [1, 1], normal: 0.3, rug: 1 })),
    };
    const mReb2 = material(tReb2, { rep: [1, 1], normal: 1.1, rug: 1, env: 0.6 });

    // viela de terra batida (leve ondulação) e terreno em socalcos ao fundo
    const R = tex.criarRuido(seed + 120);
    const mTerra = material(tTerra, { rep: [1, 1], normal: 1.2, rug: 1, env: 0.8, cor: 0xf0d8b0 });
    // colinas: suaves junto da aldeia e mais altas ao fundo (a aldeia fica num vale, como as da Baixa Galileia)
    const alt = (x, z) => { const ax = Math.abs(x); const dentro = ax < 4.5 ? 0 : Math.min(1, (ax - 4.5) / 6); const fundo = Math.max(0, -z - 70), lateral = Math.max(0, ax - 60);
      const campo = Math.max(dentro, smooth(Math.min(1, fundo / 60)));                           // fora da aldeia a estrada sobe com o terreno
      return 0.1 * R.fbm(x * 0.4, z * 0.4, 3) * (1 - dentro) + campo * (2.4 * R.fbm(x * 0.03, z * 0.03, 4) + 9 * Math.pow(Math.min(1, fundo / 250), 1.4) * (0.5 + R.fbm(x * 0.012, z * 0.012, 4))
        + (alto ? 38 * Math.pow(Math.min(1, (fundo + lateral * 0.8) / 420), 1.3) * (0.45 + 0.8 * R.fbm(x * 0.006 + 4, z * 0.006, 4)) : 0)) - 0.12 * Math.sin(ax * 0.9) * dentro; };
    // do alto: calcário com capim seco e manchas de mato verde-acinzentado fora da aldeia (não um deserto de areia)
    const corCampo = alto ? (x, y, z) => { const fora = smooth(Math.min(1, Math.max(0, (Math.abs(x) - 44) / 30, (-z - 120) / 40)));
      const v = R.fbm(x * 0.02 + 11, z * 0.02, 4), mato = smooth(Math.min(1, Math.max(0, v - 0.4) * 3));
      return [1 - fora * (0.3 + 0.12 * mato), 1 - fora * (0.16 + 0.06 * mato), 1 - fora * (0.3 + 0.08 * mato)]; } : null;
    if (alto) mTerra.vertexColors = true;
    const chao = terreno({ larg: alto ? 1400 : 520, prof: alto ? 1200 : 700, nx: alto ? 220 : 130, nz: alto ? 220 : 160, centro: [0, alto ? -480 : -230], esc: 0.2, altura: alt, cor: corCampo });
    cena.add(malha(chao, mTerra, { sombra: false }));

    // casas dos dois lados da viela (portas voltadas para a viela), alturas e larguras variadas
    const r = rngFor(seed, 5);
    const casas = new THREE.Group(); cena.add(casas);
    for (const lado of [-1, 1]) {
      let z = 14;
      for (let i = 0; i < 12 && z > -95; i++) {
        const w = 4.8 + r() * 3.2, d = 5 + r() * 2.5, andares = r() < 0.28 ? 2 : 1, h = 3.1 + r() * 0.5;
        const c = casaJudeia({ w, d, h, andares, escada: andares === 2 && r() < 0.8, porta: true, mats: { ...mats, reboco: r() < 0.5 ? mats.reboco : mReb2 }, seed: seed * 100 + i * 3 + (lado > 0 ? 1 : 0) });
        const recuo = 2.1 + r() * 0.5;
        c.position.set(lado * (recuo + d / 2), 0, z - w / 2);
        c.rotation.y = lado > 0 ? -Math.PI / 2 : Math.PI / 2;      // fachada com a porta voltada para a viela
        casas.add(c);
        z -= w + 0.2 + r() * 1.4;
      }
    }
    // arcos, banca, jarros e panos
    for (const [z, h] of [[-18, 4.4], [-44, 4.0], [-72, 4.6]]) { const a = arcoPedra(4.2, h, 0.9, mats); a.position.set(0, 0, z); cena.add(a); }
    const b1 = banca({ w: 3.2, d: 2, h: 2.3, mats, seed }); b1.position.set(-1.7, 0, -28); b1.rotation.y = 0.12; cena.add(b1);
    const b2 = banca({ w: 3.0, d: 2, h: 2.2, mats: { ...mats, toldo: mats.pano[1] }, seed: seed + 3 }); b2.position.set(1.8, 0, -57); b2.rotation.y = -0.1; cena.add(b2);
    for (let i = 0; i < 9; i++) { const a = anfora({ h: 0.55 + r() * 0.5, r: 0.2 + r() * 0.09, mats }); const lado = r() < 0.5 ? -1 : 1; a.position.set(lado * (1.35 + r() * 0.5), 0, 6 - i * 10 - r() * 5); cena.add(a); }
    cena.add(varal([-2.6, 4.2, -8], [2.6, 4.4, -9], 4.2, mats, seed, 4));
    cena.add(varal([-2.6, 4.6, -33], [2.6, 4.2, -34], 4.2, mats, seed + 1, 5));
    cena.add(varal([-2.6, 4.8, -60], [2.6, 4.4, -61], 4.4, mats, seed + 2, 5));
    // oliveiras ao fundo
    for (const [x, z, h, sd] of [[-7, -104, 4.6, 1], [6.5, -112, 4.2, 2], [-13, -126, 5.0, 3], [14, -132, 4.4, 4], [0, -150, 5.2, 5], [-26, -170, 4.8, 6], [25, -178, 4.6, 7]]) {
      const o = oliveira({ h, mats, seed: sd }); o.position.set(x, 0, z); cena.add(o);
    }
    if (alto) {
      // do alto se vê a aldeia inteira: mais casas em fileiras irregulares nas duas encostas, voltadas para a viela
      for (const lado of [-1, 1]) for (let fila = 0; fila < 3; fila++) {
        let z = 18 - r() * 6;
        while (z > -110) {
          const w = 4.6 + r() * 3, d = 4.6 + r() * 2.4, andares = r() < 0.2 ? 2 : 1, x = lado * (15 + fila * 10.5 + r() * 3);
          if (r() < 0.22) { z -= w + 3; continue; }                                          // quintais e falhas entre as casas
          const c = casaJudeia({ w, d, h: 3 + r() * 0.5, andares, escada: andares === 2, porta: false, mats: { ...mats, reboco: [mats.reboco, mReb2, mats.reboco, mReb2, mats.pedra][Math.floor(r() * 5)] }, seed: seed * 300 + fila * 40 + Math.round(-z) + (lado > 0 ? 7 : 0) });
          c.position.set(x, alt(x, z - w / 2) - 0.25, z - w / 2); c.rotation.y = (lado > 0 ? -Math.PI / 2 : Math.PI / 2) + (r() - 0.5) * 0.12;
          casas.add(c); z -= w + 0.6 + r() * 2.2;
        }
      }
      // olivais em socalcos nas encostas e no fundo do vale
      const pts = [];
      for (let i = 0; i < 900; i++) {
        const x = (r() - 0.5) * 520, z = 30 - r() * 520;
        if (Math.abs(x) < 50 && z > -120) continue;                                          // a aldeia
        if (R.fbm(x * 0.012 + 7, z * 0.012, 3) < 0.45) continue;                             // manchas de olival, não um tapete
        pts.push([x, alt(x, z) - 0.1, z, 0.8 + r() * 0.5, r() * 6]);
      }
      cena.add(bosque({ pontos: pts, mats, seed }));
    }

    const sol = criarSol({ cor: 0xffd49a, intensidade: 5.4, dir: paraSol, alvo: [0, 3, -45], dist: 150, caixa: alto ? 120 : 60, mapa: 4096, bias: -0.0003, normalBias: 0.06, near: 20, far: 320 });
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(0x9fb6e0, 0x8a6a48, 1.0));
    const poeira = criarPoeira3D({ semente: seed, n: 650, caixa: [-9, 0.3, -110, 9, 9, 16], vel: [0.12, 0.05, 0.1], cor: 0xffe2b0, tam: 1.8, op: 0.8 });
    cena.add(poeira);

    // vistas: 'viela' (padrão, câmera pela rua), 'telhados' (acima dos terraços, a aldeia e as colinas), 'saida' (da estrada de terra
    // fora da aldeia, entre as oliveiras, olhando de volta para as casas)
    const VISTAS = {
      viela: { pos: [[-1.3, 1.65, 12], [-0.6, 1.85, -6], [0.5, 2.3, -26], [0.9, 2.8, -48]], alvo: [[1.5, 2.7, -22], [0.8, 3.0, -42], [0.2, 3.2, -66], [0, 3.6, -100]], fov: [50, 40] },
      telhados: { pos: [[16, 13, 30], [11, 14, 14], [6, 15, -2]], alvo: [[-4, 4, -40], [-3, 5, -70], [-2, 7, -110]], fov: [46, 40] },
      saida: { pos: [[3, 1.7, -150], [1.5, 1.8, -135], [0.5, 1.9, -122]], alvo: [[0, 3, -60], [0, 3, -50], [0, 3.2, -40]], fov: [40, 34] },
    };
    const VT = VISTAS[P.vista] ?? VISTAS.viela;
    const trilho = criarTrilho({ pos: VT.pos, alvo: VT.alvo, fov: VT.fov, curva: (x) => 0.4 * x + 0.6 * smooth(x) });
    return {
      ceu, trilho, ibl: 1.0, vinheta: 0.5, poeiraTela: 16,
      eventos: [{ t: 0.05, tipo: 'whoosh' }],
      atualizar(t) { poeira.material.uniforms.uT.value = t; },
    };
  },
};

export const cena3d_judeia = { build: (palco, spec) => iniciar3D(palco, spec, def) };
