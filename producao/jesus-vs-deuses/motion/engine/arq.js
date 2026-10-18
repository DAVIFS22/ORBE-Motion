// Kit de arquitetura procedural (Three.js): geometria real com volume, relevo e escala em metros.
// Tudo é determinístico: só (parâmetros, semente) entram; nenhuma função usa Math.random nem tempo.
// Reconstruções são ARTÍSTICAS (inspiradas em tipos arquitetônicos documentados), nunca evidência arqueológica.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { rngFor } from './rng.js';
import { criarRuido } from './tex.js';

export const TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
const frac = (x) => x - Math.floor(x);

// ------------------------------------------------------------------------------ geometria base ---

// UV "de caixa": projeta a textura pelo eixo dominante da normal, em metros × escala (o relevo não estica em blocos de tamanhos diferentes).
export function uvMundo(geo, esc = 1, off = [0, 0]) {
  const p = geo.attributes.position, n = geo.attributes.normal, uv = geo.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
    let u, v;
    if (ay >= ax && ay >= az) { u = p.getX(i); v = p.getZ(i); }
    else if (ax >= az) { u = p.getZ(i); v = p.getY(i); }
    else { u = p.getX(i); v = p.getY(i); }
    uv.setXY(i, u * esc + off[0], v * esc + off[1]);
  }
  uv.needsUpdate = true;
  return geo;
}

export function caixa(w, h, d, { raio = 0.03, seg = 2, esc = 0.25, off = [0, 0] } = {}) {
  const r = Math.min(raio, Math.min(w, h, d) / 2 - 1e-3);
  return uvMundo(new RoundedBoxGeometry(w, h, d, seg, Math.max(r, 1e-3)), esc, off);
}

// Sólido de revolução com ondulação opcional (caneluras, gomos). perfil: [[raio, y], ...] de baixo para cima.
// ondas(theta, y, j) devolve um fator multiplicativo do raio. repU: voltas da textura; escV: metros → coordenada v.
export function revolucao(perfil, { seg = 64, ondas = null, repU = 1, escV = 0.25, offV = 0 } = {}) {
  const n = perfil.length, pos = new Float32Array((seg + 1) * n * 3), uv = new Float32Array((seg + 1) * n * 2), idx = [];
  const comp = [0];
  for (let j = 1; j < n; j++) comp.push(comp[j - 1] + Math.hypot(perfil[j][0] - perfil[j - 1][0], perfil[j][1] - perfil[j - 1][1]));
  for (let i = 0; i <= seg; i++) {
    const th = (i / seg) * TAU, s = Math.sin(th), c = Math.cos(th);
    for (let j = 0; j < n; j++) {
      const y = perfil[j][1]; let r = perfil[j][0];
      if (ondas) r *= ondas(th, y, j);
      const k = i * n + j;
      pos[3 * k] = r * s; pos[3 * k + 1] = y; pos[3 * k + 2] = r * c;
      uv[2 * k] = (i / seg) * repU; uv[2 * k + 1] = comp[j] * escV + offV;
    }
  }
  for (let i = 0; i < seg; i++) for (let j = 0; j < n - 1; j++) {
    const a = i * n + j, b = (i + 1) * n + j, c = (i + 1) * n + j + 1, d = i * n + j + 1;
    idx.push(a, b, d, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.setIndex(idx);
  g.computeVertexNormals();
  const nm = g.attributes.normal;                                   // costura: média das normais da primeira e da última coluna
  for (let j = 0; j < n; j++) {
    const a = j, b = seg * n + j;
    const x = nm.getX(a) + nm.getX(b), y = nm.getY(a) + nm.getY(b), z = nm.getZ(a) + nm.getZ(b), l = Math.hypot(x, y, z) || 1;
    nm.setXYZ(a, x / l, y / l, z / l); nm.setXYZ(b, x / l, y / l, z / l);
  }
  return g;
}

// Pontos de um arco de circunferência no plano (raio, y): para perfis arredondados (equino, bulbos, bases).
export function arco(cr, cy, r, a0, a1, n = 8) {
  const p = [];
  for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * (i / n); p.push([cr + r * Math.cos(a), cy + r * Math.sin(a)]); }
  return p;
}

// Concatena trechos de perfil removendo pontos repetidos consecutivos.
export function juntar(...trechos) {
  const out = [];
  for (const t of trechos) for (const p of t) { const u = out[out.length - 1]; if (!u || Math.abs(u[0] - p[0]) > 1e-6 || Math.abs(u[1] - p[1]) > 1e-6) out.push(p); }
  return out;
}

export function material(tex, { rep = [1, 1], cor = 0xffffff, normal = 1, rug = 1, metal = 0, env = 1, lado = THREE.FrontSide, vertexColors = false, emis = 0 } = {}) {
  const m = new THREE.MeshStandardMaterial({ color: cor, roughness: rug, metalness: metal, side: lado, vertexColors, envMapIntensity: env });
  if (tex) {
    for (const k of ['map', 'normalMap', 'roughnessMap']) {
      const c = tex[k].clone(); c.repeat.set(rep[0], rep[1]); c.needsUpdate = true; m[k] = c;
    }
    m.normalScale = new THREE.Vector2(normal, normal);
    if (emis > 0) { m.emissive = new THREE.Color(0xffffff); m.emissiveMap = m.map; m.emissiveIntensity = emis; }
  }
  return m;
}

function malha(geo, mat, { sombra = true, pos = null, rot = null } = {}) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = sombra; m.receiveShadow = true;
  if (pos) m.position.set(pos[0], pos[1], pos[2]);
  if (rot) m.rotation.set(rot[0], rot[1], rot[2]);
  return m;
}
export { malha };

// ----------------------------------------------------------------------------- ordem dórica (Grécia) ---

// Fuste com caneluras de arestas vivas, entasis e afinamento; capitel com anéis, equino e ábaco.
export function colunaDorica({ D = 1.9, H = 10.4, estrias = 20, mats }) {
  const g = new THREE.Group();
  const R0 = D / 2, Rt = R0 * 0.80, hFuste = H * 0.915;
  const perfil = [];
  const N = 26;
  for (let j = 0; j <= N; j++) {
    const y = (j / N) * hFuste, k = y / hFuste;
    perfil.push([(R0 + (Rt - R0) * k) * (1 + 0.016 * Math.sin(Math.PI * k)), y]);   // entasis suave
  }
  const prof = 0.052, seg = estrias * 5;
  const fuste = revolucao(perfil, {
    seg, repU: 1, escV: 1 / hFuste,
    ondas: (th, y) => {
      const u = frac(th / TAU * estrias), q = 2 * u - 1;
      const topo = clamp((hFuste - y) / 0.5);                               // as caneluras morrem sob o colarino
      const base = clamp(y / 0.05);
      return 1 - prof * (1 - q * q) * Math.min(topo, 1) * base;
    },
  });
  g.add(malha(fuste, mats.fuste));
  // capitel: colarino, três anéis, equino (curva convexa), ábaco
  const rc = Rt * 0.985, yc = hFuste;
  const anel = 0.035 * D;
  const eq0 = yc + 3 * anel + 0.04 * D, hEq = 0.28 * D, rTop = Rt * 1.36;
  const equino = [];
  for (let i = 0; i <= 14; i++) {
    const k = i / 14, y = eq0 + k * hEq;
    const r = rc * 1.02 + (rTop - rc * 1.02) * (1 - Math.pow(1 - k, 2.1)) * 0.9 + (rTop - rc * 1.02) * 0.1 * k;
    equino.push([r, y]);
  }
  const capPerfil = juntar([[rc, yc]], [[rc, yc + 0.02 * D], [rc * 1.045, yc + 0.02 * D], [rc * 1.045, yc + anel], [rc, yc + anel], [rc, yc + anel + 0.02 * D], [rc * 1.045, yc + anel + 0.02 * D], [rc * 1.045, yc + 2 * anel], [rc, yc + 2 * anel],
    [rc, yc + 2 * anel + 0.02 * D], [rc * 1.045, yc + 2 * anel + 0.02 * D], [rc * 1.045, yc + 3 * anel]], equino, [[rTop, eq0 + hEq]]);
  g.add(malha(revolucao(capPerfil, { seg: 40, escV: 0.5 }), mats.capitel));
  const hAb = H - (eq0 + hEq), lado = rTop * 2 * 1.08;
  g.add(malha(caixa(lado, hAb, lado, { raio: 0.02, esc: 0.5 }), mats.capitel, { pos: [0, eq0 + hEq + hAb / 2, 0] }));
  g.userData.altura = H; g.userData.raioBase = R0; g.userData.ladoAbaco = lado;
  return g;
}

// Triglifo: bloco com três caneluras verticais (cor de vértice escurece os sulcos). Geometria única, reutilizada.
export function triglifo(w, h, prof) {
  const partes = [];
  const base = caixa(w, h, prof, { raio: 0.012, esc: 0.5 });
  base.setAttribute('color', new THREE.BufferAttribute(new Float32Array(base.attributes.position.count * 3).fill(1), 3));
  partes.push(base);
  const gw = w * 0.1, sulcoH = h * 0.86;
  for (const cx of [-w * 0.28, 0, w * 0.28]) {
    const s = caixa(gw, sulcoH, 0.02, { raio: 0.004, esc: 0.5 });
    s.translate(cx, 0.0, prof / 2 + 0.002);
    s.setAttribute('color', new THREE.BufferAttribute(new Float32Array(s.attributes.position.count * 3).fill(0.28), 3));
    partes.push(s);
  }
  return mergeGeometries(partes);
}

function prisma(pontos, prof, esc = 0.25) {          // extrusão de um polígono do plano XY ao longo de z (frontão, calhas)
  const sh = new THREE.Shape(pontos.map((p) => new THREE.Vector2(p[0], p[1])));
  const g = new THREE.ExtrudeGeometry(sh, { depth: prof, bevelEnabled: false });
  g.translate(0, 0, -prof / 2);
  g.computeVertexNormals();
  return uvMundo(g, esc);
}

// Templo períptero dórico completo. Origem: centro da plataforma (topo do estilóbato em y = 0); frontão voltado para +z.
// nF x nL colunas (frente x lado). Medidas em metros, proporções inspiradas no Partenon (447–432 a.C.).
export function temploDorico({ nF = 8, nL = 17, D = 1.9, H = 10.4, entre = 4.3, mats, estrias = 20 }) {
  const g = new THREE.Group();
  const xw = ((nF - 1) * entre) / 2, zl = ((nL - 1) * entre) / 2;
  // crepidoma (3 degraus): k = 0 é o mais baixo e largo; o topo (k = 2) termina em y = 0
  const f = D / 1.9, degrau = 0.55 * f, avanco = 0.95 * f;
  const bw = xw * 2 + D * 1.7, bl = zl * 2 + D * 1.7;
  for (let k = 0; k < 3; k++) {
    const w = bw + 2 * avanco * (2 - k), l = bl + 2 * avanco * (2 - k);
    g.add(malha(caixa(w, degrau, l, { raio: 0.04, esc: 0.35, off: [k * 0.37, k * 0.21] }), mats.degrau, { pos: [0, -degrau * (2.5 - k), 0] }));
  }
  // colunas
  const col = colunaDorica({ D, H, estrias, mats });
  const pos = [];
  for (let i = 0; i < nF; i++) { const x = -xw + i * entre; pos.push([x, zl], [x, -zl]); }
  for (let k = 1; k < nL - 1; k++) { const z = -zl + k * entre; pos.push([-xw, z], [xw, z]); }
  pos.forEach(([x, z], i) => {
    const c = col.clone(true);
    c.position.set(x, 0, z); c.rotation.y = ((i * 37) % 4) * (Math.PI / 2);   // gira o fuste (a textura não repete na mesma posição)
    g.add(c);
  });
  // entablamento
  const hArq = 1.35 * f, hFri = 1.3 * f, hCor = 0.55 * f, prof = D * 0.95;
  const yArq = H + hArq / 2;
  const compF = xw * 2 + D * 1.02, compL = zl * 2 + D * 1.02;
  g.add(malha(caixa(compF, hArq, prof, { raio: 0.02, esc: 0.4 }), mats.arquitrave, { pos: [0, yArq, zl] }));
  g.add(malha(caixa(compF, hArq, prof, { raio: 0.02, esc: 0.4 }), mats.arquitrave, { pos: [0, yArq, -zl] }));
  g.add(malha(caixa(prof, hArq, compL, { raio: 0.02, esc: 0.4 }), mats.arquitrave, { pos: [xw, yArq, 0] }));
  g.add(malha(caixa(prof, hArq, compL, { raio: 0.02, esc: 0.4 }), mats.arquitrave, { pos: [-xw, yArq, 0] }));
  const yFri = H + hArq + hFri / 2;
  const tri = triglifo(D * 0.72, hFri, 0.12 * f), mTri = mats.triglifo;
  const met = mats.metopa;
  const friso = (comp, eixo, fixo, sentido) => {
    const nT = Math.round(comp / (entre / 2));                             // dois triglifos por intercolúnio
    const passo = comp / nT;
    g.add(malha(caixa(eixo === 'x' ? comp : prof * 0.8, hFri, eixo === 'x' ? prof * 0.8 : comp, { raio: 0.01, esc: 0.4 }), met, { pos: eixo === 'x' ? [0, yFri, fixo] : [fixo, yFri, 0] }));
    for (let i = 0; i <= nT; i++) {
      const p = -comp / 2 + i * passo;
      const m = new THREE.Mesh(tri, mTri); m.castShadow = true; m.receiveShadow = true;
      if (eixo === 'x') { m.position.set(p, yFri, fixo + sentido * (prof * 0.4 + 0.02)); if (sentido < 0) m.rotation.y = Math.PI; }
      else { m.position.set(fixo + sentido * (prof * 0.4 + 0.02), yFri, p); m.rotation.y = sentido > 0 ? Math.PI / 2 : -Math.PI / 2; }
      g.add(m);
    }
  };
  friso(compF, 'x', zl, +1); friso(compF, 'x', -zl, -1); friso(compL, 'z', xw, +1); friso(compL, 'z', -xw, -1);
  // cornija
  const yCor = H + hArq + hFri + hCor / 2, pj = 0.75 * f;
  g.add(malha(caixa(compF + 2 * pj, hCor, prof + 2 * pj, { raio: 0.02, esc: 0.4 }), mats.cornija, { pos: [0, yCor, zl] }));
  g.add(malha(caixa(compF + 2 * pj, hCor, prof + 2 * pj, { raio: 0.02, esc: 0.4 }), mats.cornija, { pos: [0, yCor, -zl] }));
  g.add(malha(caixa(prof + 2 * pj, hCor, compL + 2 * pj, { raio: 0.02, esc: 0.4 }), mats.cornija, { pos: [xw, yCor, 0] }));
  g.add(malha(caixa(prof + 2 * pj, hCor, compL + 2 * pj, { raio: 0.02, esc: 0.4 }), mats.cornija, { pos: [-xw, yCor, 0] }));
  // frontões: tímpano triangular (escuro) emoldurado pelas cornijas inclinadas
  const yFr = H + hArq + hFri + hCor;
  const wFr = compF + 2 * pj - 0.4, altFr = wFr * 0.115;
  const alfa = Math.atan2(altFr, wFr / 2), compInc = Math.hypot(wFr / 2, altFr);
  for (const s of [1, -1]) {
    const z = s * zl;
    g.add(malha(prisma([[-wFr / 2, 0], [wFr / 2, 0], [0, altFr]], 0.6, 0.3), mats.timpano, { pos: [0, yFr, z] }));
    for (const sx of [1, -1]) {
      const m = malha(caixa(compInc, 0.62, 0.95, { raio: 0.03, esc: 0.4 }), mats.cornija);
      m.position.set(sx * wFr / 4, yFr + altFr / 2 + 0.28, z); m.rotation.z = -sx * alfa;
      g.add(m);
    }
  }
  // telhado: duas águas de lajes de mármore
  const compT = compL + 2 * pj, semi = (compF + 2 * pj) / 2, rise = altFr, inc = Math.atan2(rise, semi), lado = Math.hypot(semi, rise);
  for (const s of [1, -1]) {
    const lage = caixa(lado, 0.22, compT, { raio: 0.02, esc: 0.5 });
    const m = malha(lage, mats.telha);
    m.position.set(s * semi / 2, yFr + rise / 2 + 0.1, 0); m.rotation.z = s * -inc;
    g.add(m);
  }
  // cela (naos): paredes de cantaria atrás da colunata
  const cw = xw - entre * 0.9, cl = zl - entre * 0.7, hc = H * 0.98;
  const parede = (w, l, x, z) => g.add(malha(caixa(w, hc, l, { raio: 0.02, esc: 0.28 }), mats.cela, { pos: [x, hc / 2, z] }));
  parede(0.9, cl * 2, cw, 0); parede(0.9, cl * 2, -cw, 0); parede(cw * 2 + 0.9, 0.9, 0, -cl);
  // fachada da cela com portal escuro
  const pw = (cw * 2 - 5.6) / 2;
  parede(pw, 0.9, -cw + pw / 2, cl); parede(pw, 0.9, cw - pw / 2, cl);
  const vazio = 5.6, lintel = hc - 7.2;
  g.add(malha(caixa(vazio + 0.6, lintel, 0.9, { raio: 0.02, esc: 0.28 }), mats.cela, { pos: [0, 7.2 + lintel / 2, cl] }));
  g.add(malha(new THREE.PlaneGeometry(vazio, 7.2), new THREE.MeshBasicMaterial({ color: 0x050403 }), { sombra: false, pos: [0, 3.6, cl - 0.3] }));
  // laje de piso do interior (escurece)
  g.add(malha(new THREE.PlaneGeometry(cw * 2, cl * 2), mats.degrau, { pos: [0, 0.01, 0], rot: [-Math.PI / 2, 0, 0], sombra: false }));
  g.userData.dim = { xw, zl, H, comp: compL, larg: compF, yFr, altFr };
  return g;
}

// -------------------------------------------------------------------------- ordem egípcia (Egito) ---

// Coluna papiriforme: fuste de feixe de caules (gomos), anéis de amarração, base com folhas e capitel
// aberto (campaniforme, nave central) ou fechado (botão de papiro, naves laterais). Cores pintadas vêm do material.
export function colunaPapiro({ R = 1.7, H = 18, aberto = true, gomos = 8, mats }) {
  const g = new THREE.Group();
  const hBase = R * 0.55, hFuste = H * 0.80;
  const pf = [];
  const N = 22;
  for (let j = 0; j <= N; j++) {
    const k = j / N, y = hBase + k * (hFuste - hBase);
    pf.push([R * (0.94 + 0.07 * Math.sin(Math.PI * Math.min(1, k * 1.2) * 0.9) - 0.14 * Math.pow(k, 2.5)), y]);
  }
  const fb = [[R * 0.6, 0], [R * 0.9, 0.0], [R * 0.98, hBase * 0.35], [R * 0.93, hBase * 0.7], [R * 0.9, hBase]];
  const baseG = revolucao(fb, { seg: gomos * 4, escV: 0.2, repU: 2, ondas: (th, y) => 1 + 0.07 * Math.pow(Math.abs(Math.cos(th * gomos * 0.5)), 0.6) * clamp(1 - y / hBase) });
  g.add(malha(baseG, mats.fuste));
  const fusteG = revolucao(pf, {
    seg: gomos * 6, repU: 2, escV: 1 / H * 0.9,
    ondas: (th, y) => {
      const k = (y - hBase) / (hFuste - hBase);
      const cost = Math.abs(Math.cos(th * gomos * 0.5));                  // costelas do feixe de caules
      const nervura = 1 + 0.10 * (Math.pow(cost, 0.5) - 0.7);
      const amar = 1 + 0.1 * Math.exp(-Math.pow((k - 0.955) / 0.014, 2)) + 0.08 * Math.exp(-Math.pow((k - 0.9) / 0.01, 2));   // faixas de amarração
      return nervura * amar;
    },
  });
  g.add(malha(fusteG, mats.fuste));
  const y0 = hFuste, rN = pf[N][0] * 0.88;
  let cap;
  if (aberto) {
    const hc = H - y0;
    const cp = [];
    for (let i = 0; i <= 14; i++) { const k = i / 14, y = y0 + k * hc; cp.push([rN + (R * 1.75 - rN) * (0.42 * k + 0.58 * Math.pow(k, 2.2)) * 1.0, y]); }
    cap = revolucao(cp, { seg: 72, repU: 2, escV: 0.2, ondas: (th, y) => 1 + 0.06 * Math.cos(th * 24) + 0.045 * Math.cos(th * 48 + 1) });
  } else {
    const hc = H - y0 * 0.96;
    const cp = [[rN, y0 * 0.96]];
    for (let i = 1; i <= 14; i++) { const k = i / 14, y = y0 * 0.96 + k * hc; const r = rN * (1 + 0.42 * Math.sin(Math.PI * Math.pow(k, 0.7)) * (1 - 0.3 * k)) * (1 - 0.55 * Math.pow(k, 3)); cp.push([r, y]); }
    cap = revolucao(cp, { seg: 48, repU: 2, escV: 0.2, ondas: (th) => 1 + 0.07 * Math.pow(Math.abs(Math.cos(th * 4)), 0.7) + 0.02 * Math.cos(th * 16) });
  }
  g.add(malha(cap, mats.capitel));
  const lado = aberto ? R * 3.2 : R * 2.5, hAb = R * 0.8;
  g.add(malha(caixa(lado, hAb, lado, { raio: 0.04, esc: 0.35 }), mats.pedra, { pos: [0, H + hAb / 2, 0] }));
  g.userData.altura = H + hAb; g.userData.lado = lado;
  return g;
}

// Salão hipostilo: nave central alta (colunas abertas), naves laterais baixas (botões de papiro), arquitraves, lajes do teto,
// claristório com frestas (entrada da luz), pórtico/portal ao fundo com brilho. Origem no centro do piso; eixo da nave = -z.
export function salaoHipostilo({ filas = 7, espaco = 9.6, naveLarg = 13, R1 = 1.75, H1 = 19, R2 = 1.25, H2 = 12.5, laterais = 4, esp2 = 6.4, mats, seed = 5 }) {
  const g = new THREE.Group();
  const comp = (filas - 1) * espaco;
  const colAberta = colunaPapiro({ R: R1, H: H1, aberto: true, gomos: 8, mats });
  const colFechada = colunaPapiro({ R: R2, H: H2, aberto: false, gomos: 8, mats });
  const pos1 = [], pos2 = [];
  for (let i = 0; i < filas; i++) { const z = -i * espaco; pos1.push([-naveLarg / 2, z], [naveLarg / 2, z]); }
  const ladoX = (k) => naveLarg / 2 + R1 * 2.2 + esp2 * (k + 0.5) + 0.5;
  const nZ = Math.floor(comp / esp2) + 1;
  for (let k = 0; k < laterais; k++) for (let i = 0; i < nZ; i++) { const z = -i * esp2 + 1.2; for (const s of [-1, 1]) pos2.push([s * ladoX(k), z]); }
  const r = rngFor(seed, 1);
  pos1.forEach(([x, z]) => { const c = colAberta.clone(true); c.position.set(x, 0, z); c.rotation.y = r() * TAU; g.add(c); });
  pos2.forEach(([x, z]) => { const c = colFechada.clone(true); c.position.set(x, 0, z); c.rotation.y = r() * TAU; g.add(c); });
  const topo1 = colAberta.userData.altura, topo2 = colFechada.userData.altura;
  // arquitraves da nave (ao longo de z) e lajes transversais
  const hArq = 2.2;
  const zc = -comp / 2, larguraTotal = ladoX(laterais - 1) + R2 * 1.4;
  for (const s of [-1, 1]) {
    g.add(malha(caixa(R1 * 2.2, hArq, comp + espaco, { raio: 0.05, esc: 0.2 }), mats.pedra, { pos: [s * naveLarg / 2, topo1 + hArq / 2, zc] }));
  }
  // lajes do teto da nave (transversais) e do teto das laterais
  const nLajes = Math.floor((comp + espaco) / 3.2);
  for (let i = 0; i < nLajes; i++) {
    const z = espaco / 2 - (i + 0.5) * ((comp + espaco) / nLajes);
    g.add(malha(caixa(naveLarg + R1 * 2.2, 1.2, (comp + espaco) / nLajes - 0.05, { raio: 0.04, esc: 0.12, off: [i * 0.13, 0] }), mats.teto ?? mats.pedra, { pos: [0, topo1 + hArq + 0.6, z] }));
  }
  // paredes do claristório com frestas (entra a luz); a parede fica sobre as arquitraves das laterais
  const yClar = topo2 + 1.8;
  for (const s of [-1, 1]) {
    // teto das laterais
    g.add(malha(caixa(larguraTotal - naveLarg / 2 - R1 * 1.1, 1.6, comp + espaco + 2, { raio: 0.04, esc: 0.12 }), mats.teto ?? mats.pedra, { pos: [s * (naveLarg / 2 + R1 * 1.1 + (larguraTotal - naveLarg / 2 - R1 * 1.1) / 2), topo2 + 0.8, zc] }));
    // parede do claristório: pilares entre frestas
    const nFr = Math.floor((comp + espaco) / 2.6);
    const y0 = topo2 + 1.6, y1 = topo1 + hArq;
    for (let i = 0; i <= nFr; i++) {
      const z = espaco / 2 - i * ((comp + espaco) / nFr);
      g.add(malha(caixa(1.2, y1 - y0, 1.35, { raio: 0.03, esc: 0.3, off: [i * 0.07, 0.3] }), mats.parede, { pos: [s * (naveLarg / 2 + R1 * 1.1 + 0.6), (y0 + y1) / 2, z] }));
    }
  }
  // piso de lajes
  const pisoL = larguraTotal * 2 + 6, pisoC = comp + espaco + 40;
  g.add(malha(new THREE.PlaneGeometry(pisoL, pisoC), mats.piso, { pos: [0, 0, -comp / 2 - 10], rot: [-Math.PI / 2, 0, 0], sombra: false }));
  g.userData.dim = { comp, naveLarg, topo1, topo2, larguraTotal, espaco, zc };
  return g;
}

// Poliedro convexo a partir de vértices e faces (quadriláteros/triângulos); normais orientadas para fora pelo centroide.
export function poliedro(pts, faces, esc = 0.25) {
  const c = pts.reduce((a, p) => [a[0] + p[0] / pts.length, a[1] + p[1] / pts.length, a[2] + p[2] / pts.length], [0, 0, 0]);
  const v = [];
  for (const f of faces) {
    const tris = f.length === 3 ? [[f[0], f[1], f[2]]] : [[f[0], f[1], f[2]], [f[0], f[2], f[3]]];
    for (const [a, b, d] of tris) {
      const A = new THREE.Vector3(...pts[a]), B = new THREE.Vector3(...pts[b]), C = new THREE.Vector3(...pts[d]);
      const n = new THREE.Vector3().crossVectors(B.clone().sub(A), C.clone().sub(A));
      const fora = n.dot(A.clone().sub(new THREE.Vector3(...c))) > 0;
      const ord = fora ? [A, B, C] : [A, C, B];
      for (const q of ord) v.push(q.x, q.y, q.z);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(v.length / 3 * 2), 2));
  g.computeVertexNormals();
  return uvMundo(g, esc);
}

// Pilone (portal monumental de templo egípcio): duas torres troncopiramidais com um vão; frente para +z.
export function pilone({ larg = 38, alt = 24, prof = 9, vao = 7, mats }) {
  const g = new THREE.Group();
  const w = (larg - vao) / 2, b = w, t = w * 0.86;
  const p = [[-b / 2, 0, -prof / 2], [b / 2, 0, -prof / 2], [b / 2, 0, prof / 2], [-b / 2, 0, prof / 2], [-t / 2, alt, -prof * 0.42], [t / 2, alt, -prof * 0.42], [t / 2, alt, prof * 0.42], [-t / 2, alt, prof * 0.42]];
  const geo = poliedro(p, [[0, 1, 5, 4], [2, 3, 7, 6], [3, 0, 4, 7], [1, 2, 6, 5], [4, 5, 6, 7], [0, 3, 2, 1]], 0.22);
  for (const s of [-1, 1]) g.add(malha(geo, mats.parede, { pos: [s * (vao / 2 + w / 2), 0, 0] }));
  g.add(malha(caixa(vao + 1, 3, prof * 0.9, { raio: 0.05, esc: 0.2 }), mats.pedra, { pos: [0, alt * 0.84, 0] }));
  return g;
}

export function obelisco({ base = 2.4, alt = 24, mats }) {
  const g = new THREE.Group();
  const b = base / 2, t = base * 0.28 / 2, hp = base * 0.7;
  const pts = [[-b, 0, -b], [b, 0, -b], [b, 0, b], [-b, 0, b], [-t, alt, -t], [t, alt, -t], [t, alt, t], [-t, alt, t], [0, alt + hp, 0]];
  g.add(malha(poliedro(pts, [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 8], [5, 6, 8], [6, 7, 8], [7, 4, 8], [0, 3, 2, 1]], 0.3), mats.pedra));
  return g;
}

// -------------------------------------------------------------------------- Judeia, séc. I (aldeia) ---

// Casa de pedra e reboco com telhado plano e parapeito; porta de madeira, janela pequena, vigas aparentes e escada externa opcional.
export function casaJudeia({ w = 6, d = 5, h = 3.2, andares = 1, escada = false, porta = true, mats, seed = 1, lado = 'frente' }) {
  const g = new THREE.Group();
  const r = rngFor(seed, 3);
  const H = h * andares;
  g.add(malha(caixa(w, H, d, { raio: 0.06, seg: 2, esc: 0.3, off: [r(), r()] }), mats.reboco, { pos: [0, H / 2, 0] }));
  // base de pedra aparente
  g.add(malha(caixa(w + 0.12, 0.7, d + 0.12, { raio: 0.05, esc: 0.35, off: [r(), r()] }), mats.pedra, { pos: [0, 0.35, 0] }));
  // parapeito do terraço
  const pp = 0.5, esp = 0.28;
  g.add(malha(caixa(w + 0.3, pp, esp, { raio: 0.04, esc: 0.35 }), mats.reboco, { pos: [0, H + pp / 2, d / 2 + 0.08] }));
  g.add(malha(caixa(w + 0.3, pp, esp, { raio: 0.04, esc: 0.35 }), mats.reboco, { pos: [0, H + pp / 2, -d / 2 - 0.08] }));
  g.add(malha(caixa(esp, pp, d, { raio: 0.04, esc: 0.35 }), mats.reboco, { pos: [w / 2 + 0.08, H + pp / 2, 0] }));
  g.add(malha(caixa(esp, pp, d, { raio: 0.04, esc: 0.35 }), mats.reboco, { pos: [-w / 2 - 0.08, H + pp / 2, 0] }));
  // terraço de terra batida
  g.add(malha(caixa(w - 0.1, 0.16, d - 0.1, { raio: 0.03, esc: 0.5 }), mats.terraco, { pos: [0, H + 0.08, 0] }));
  // vigas (cabeças de troncos aparecendo na fachada)
  const nv = Math.max(3, Math.floor(w / 0.9));
  for (let i = 0; i < nv; i++) {
    const x = -w / 2 + (i + 0.5) * (w / nv);
    g.add(malha(new THREE.CylinderGeometry(0.1, 0.1, 0.45, 8), mats.madeira, { pos: [x, H - 0.12, d / 2 + 0.2], rot: [Math.PI / 2, 0, 0] }));
  }
  if (porta) {
    const pw = 1.05, ph = 2.05, xp = (r() - 0.5) * (w - 2.2);
    g.add(malha(caixa(pw + 0.35, ph + 0.2, 0.14, { raio: 0.03, esc: 0.5 }), mats.pedra, { pos: [xp, (ph + 0.2) / 2, d / 2 + 0.02] }));
    g.add(malha(caixa(pw, ph, 0.1, { raio: 0.02, esc: 0.6 }), mats.porta, { pos: [xp, ph / 2, d / 2 + 0.1] }));
  }
  const jw = 0.55, jh = 0.7;
  for (let a = 0; a < andares; a++) {
    const xj = (r() - 0.5) * (w - 1.6);
    if (a === 0 && !porta) continue;
    g.add(malha(caixa(jw + 0.25, jh + 0.25, 0.1, { raio: 0.02, esc: 0.5 }), mats.pedra, { pos: [xj, a * h + h * 0.62, d / 2 + 0.02] }));
    g.add(malha(new THREE.PlaneGeometry(jw, jh), new THREE.MeshBasicMaterial({ color: 0x120c08 }), { sombra: false, pos: [xj, a * h + h * 0.62, d / 2 + 0.085] }));
  }
  if (escada) {
    const nd = 11, hd = H / nd, ld = 0.32;
    for (let i = 0; i < nd; i++) g.add(malha(caixa(0.95, hd * (i + 1), ld, { raio: 0.02, esc: 0.4 }), mats.pedra, { pos: [w / 2 + 0.55, hd * (i + 1) / 2, d / 2 - 0.3 - (nd - i) * ld * 0.0 - (nd - 1 - i) * ld] }));
  }
  g.userData.alt = H;
  return g;
}

// Ânfora / jarro (revolução)
export function anfora({ h = 0.9, r = 0.28, mats, alca = true }) {
  const g = new THREE.Group();
  const p = juntar([[0.0, 0], [r * 0.38, 0.0], [r * 0.4, 0.04 * h]], arco(r * 0.2, h * 0.38, r * 0.8, -Math.PI / 2 + 0.25, Math.PI / 2 - 0.15, 12).map(([a, b]) => [Math.max(a, 0.02), b]),
    [[r * 0.34, h * 0.8], [r * 0.3, h * 0.88], [r * 0.4, h * 0.95], [r * 0.44, h]]);
  g.add(malha(revolucao(p, { seg: 28, escV: 0.8 }), mats.barro));
  return g;
}

// Banca de mercado com toldo de pano (cantos erguidos por varas), mesa e cestos.
export function banca({ w = 3.2, d = 2, h = 2.2, mats, seed = 2 }) {
  const g = new THREE.Group();
  const r = rngFor(seed, 4);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) g.add(malha(new THREE.CylinderGeometry(0.05, 0.06, h + (sz > 0 ? 0 : 0.35), 8), mats.madeira, { pos: [sx * w / 2, (h + (sz > 0 ? 0 : 0.35)) / 2, sz * d / 2] }));
  const toldo = new THREE.PlaneGeometry(w + 0.5, d + 0.9, 14, 6);
  const p = toldo.attributes.position;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i); p.setZ(i, 0.1 * Math.sin(x * 1.7 + seed) * Math.cos(y * 2.1) - 0.08 * Math.abs(x) / w); }
  toldo.computeVertexNormals();
  const t = malha(toldo, mats.toldo, { pos: [0, h + 0.05, 0], rot: [-Math.PI / 2 + 0.16, 0, 0] });
  t.material.side = THREE.DoubleSide;
  g.add(t);
  g.add(malha(caixa(w * 0.9, 0.08, d * 0.5, { raio: 0.01, esc: 0.8 }), mats.madeira, { pos: [0, 0.9, 0.1] }));
  for (const sx of [-0.7, 0.2, 0.9]) g.add(malha(caixa(w * 0.18, 0.04, d * 0.22, { raio: 0.01, esc: 0.8 }), mats.madeira, { pos: [sx, 0.97, 0.15] }));
  for (let i = 0; i < 4; i++) { const a = anfora({ h: 0.5 + r() * 0.35, r: 0.17 + r() * 0.08, mats }); a.position.set(-w / 2 + 0.3 + i * (w - 0.6) / 3, 0, d / 2 + 0.3 + r() * 0.2); g.add(a); }
  return g;
}

// Oliveira: tronco retorcido e copa de folhas prateadas (esferas achatadas); semente fixa.
export function oliveira({ h = 4.2, mats, seed = 1 }) {
  const g = new THREE.Group();
  const r = rngFor(seed, 9);
  const tronco = revolucao(juntar([[0.34, 0], [0.26, h * 0.22], [0.2, h * 0.5], [0.12, h * 0.68]]), {
    seg: 14, escV: 0.8, ondas: (th, y) => 1 + 0.2 * Math.sin(th * 3 + y * 1.5 + seed) + 0.08 * Math.sin(th * 7 + y * 4),
  });
  g.add(malha(tronco, mats.madeira));
  const n = 9;
  for (let i = 0; i < n; i++) {
    const a = r() * TAU, d = 0.9 + r() * 1.4, y = h * (0.6 + r() * 0.3), s = 0.85 + r() * 0.7;
    const copa = new THREE.IcosahedronGeometry(1, 2);
    const q = copa.attributes.position;
    for (let k = 0; k < q.count; k++) { const f = 1 + 0.18 * Math.sin(q.getX(k) * 5 + i) * Math.cos(q.getZ(k) * 4 + i * 2); q.setXYZ(k, q.getX(k) * f, q.getY(k) * f, q.getZ(k) * f); }
    copa.computeVertexNormals();
    const m = malha(copa, mats.folha);
    m.scale.set(s * 1.2, s * 0.62, s * 1.2); m.position.set(Math.cos(a) * d, y, Math.sin(a) * d);
    g.add(m);
  }
  return g;
}

// Pinheiros instanciados (floresta nórdica): InstancedMesh com posições vindas de uma função (x,z)->{y,ok}, semente fixa.
export function floresta({ n = 800, area, altura, aceita, mats, seed = 3, escala = [0.8, 1.5], h0 = 9 }) {
  const cone = (r, h, y) => { const c = new THREE.ConeGeometry(r, h, 7, 1); c.translate(0, y + h / 2, 0); return c; };
  const partes = [cone(1.9, 3.4, 1.4), cone(1.5, 3.2, 3.4), cone(1.1, 3.0, 5.4), cone(0.7, 2.6, 7.2)];
  const tronco = new THREE.CylinderGeometry(0.16, 0.24, 2.0, 5); tronco.translate(0, 1.0, 0);
  const geo = mergeGeometries([partes[0], partes[1], partes[2], partes[3]].map((g) => g.index ? g.toNonIndexed() : g));
  const im = new THREE.InstancedMesh(geo, mats.pinheiro, n);
  const tr = new THREE.InstancedMesh(tronco, mats.tronco, n);
  const r = rngFor(seed, 17), M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), s = new THREE.Vector3();
  let k = 0, tent = 0;
  while (k < n && tent < n * 40) {
    tent++;
    const x = area[0] + r() * (area[1] - area[0]), z = area[2] + r() * (area[3] - area[2]);
    const hh = altura(x, z);
    if (!aceita(x, z, hh)) continue;
    const sc = escala[0] + r() * (escala[1] - escala[0]);
    e.set((r() - 0.5) * 0.08, r() * TAU, (r() - 0.5) * 0.08); q.setFromEuler(e);
    p.set(x, hh - 0.3, z); s.set(sc * (0.85 + r() * 0.3), sc, sc * (0.85 + r() * 0.3));
    M.compose(p, q, s); im.setMatrixAt(k, M); tr.setMatrixAt(k, M);
    k++;
  }
  im.count = k; tr.count = k;
  im.castShadow = true; im.receiveShadow = true; tr.castShadow = true;
  im.instanceMatrix.needsUpdate = true; tr.instanceMatrix.needsUpdate = true;
  const g = new THREE.Group(); g.add(im, tr); g.userData.n = k;
  return g;
}

// ------------------------------------------------------------------------------------ terreno ---

// Malha de terreno a partir de uma função de altura; cor opcional por vértice (rampa/declive/altitude).
export function terreno({ larg, prof, nx = 160, nz = 160, altura, cor = null, esc = 0.1, centro = [0, 0], uvf = null }) {
  const g = new THREE.PlaneGeometry(larg, prof, nx, nz);
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position;
  const colors = cor ? new Float32Array(p.count * 3) : null;
  const uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i) + centro[0], z = p.getZ(i) + centro[1];
    const y = altura(x, z);
    p.setXYZ(i, p.getX(i), y, p.getZ(i));
    if (uvf) { const q = uvf(x, y, z); uv.setXY(i, q[0], q[1]); } else uv.setXY(i, x * esc, z * esc);
  }
  g.computeVertexNormals();
  if (cor) {
    const nrm = g.attributes.normal;
    for (let i = 0; i < p.count; i++) {
      const c = cor(p.getX(i) + centro[0], p.getY(i), p.getZ(i) + centro[1], nrm.getY(i));
      colors[3 * i] = c[0]; colors[3 * i + 1] = c[1]; colors[3 * i + 2] = c[2];
    }
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  }
  g.translate(centro[0], 0, centro[1]);
  return g;
}

export { criarRuido };
