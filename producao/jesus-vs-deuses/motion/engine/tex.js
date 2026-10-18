// Texturas procedurais PBR (cor, relevo → normal map, rugosidade) geradas por código, com ruído de semente fixa.
// Todas são repetíveis (tileable) e determinísticas: o mesmo (receita, semente, tamanho) produz sempre os mesmos pixels.
import * as THREE from 'three';
import { hash32 } from './rng.js';

// ----------------------------------------------------------------------------------- ruído ---
const quintic = (t) => t * t * t * (t * (t * 6 - 15) + 10);

export function criarRuido(semente) {
  const val = (ix, iy) => (hash32(semente, ix | 0, iy | 0) >>> 8) / 16777216;
  const noise = (x, y, per = 0) => {                         // `per` > 0 torna o ruído periódico (tileable) com esse período
    let ix = Math.floor(x), iy = Math.floor(y); const fx = quintic(x - ix), fy = quintic(y - iy);
    let jx = ix + 1, jy = iy + 1;
    if (per) { ix = ((ix % per) + per) % per; jx = ((jx % per) + per) % per; iy = ((iy % per) + per) % per; jy = ((jy % per) + per) % per; }
    const a = val(ix, iy), b = val(jx, iy), c = val(ix, jy), d = val(jx, jy);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  };
  const fbm = (x, y, oit = 4, per = 0, ganho = 0.5) => {
    let s = 0, a = 0.5, f = 1, n = 0;
    for (let i = 0; i < oit; i++) { s += a * noise(x * f, y * f, per ? per * f : 0); n += a; a *= ganho; f *= 2; }
    return s / n;
  };
  const cresta = (x, y, oit = 4, per = 0) => { let s = 0, a = 0.5, f = 1, n = 0; for (let i = 0; i < oit; i++) { s += a * (1 - Math.abs(noise(x * f, y * f, per ? per * f : 0) * 2 - 1)); n += a; a *= 0.5; f *= 2; } return s / n; };
  return { noise, fbm, cresta, val };
}

const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
const mix = (a, b, k) => a + (b - a) * k;
const mixc = (c1, c2, k) => [mix(c1[0], c2[0], k), mix(c1[1], c2[1], k), mix(c1[2], c2[2], k)];

// ---------------------------------------------------------------------------- infraestrutura ---
// `pixel(u, v, i, j)` -> { c:[r,g,b] (0..255), h: altura 0..1, r: rugosidade 0..1 }
function gerar(tam, pixel, { forcaNormal = 3.0, semente = 1 } = {}) {
  const cor = new Uint8ClampedArray(tam * tam * 4), alt = new Float32Array(tam * tam), rug = new Uint8ClampedArray(tam * tam * 4);
  for (let j = 0; j < tam; j++) for (let i = 0; i < tam; i++) {
    const p = pixel(i / tam, j / tam, i, j), k = (j * tam + i) * 4;
    cor[k] = p.c[0]; cor[k + 1] = p.c[1]; cor[k + 2] = p.c[2]; cor[k + 3] = 255;
    alt[j * tam + i] = p.h ?? 0.5; const r = Math.round(255 * (p.r ?? 0.8)); rug[k] = rug[k + 1] = rug[k + 2] = r; rug[k + 3] = 255;
  }
  const nor = new Uint8ClampedArray(tam * tam * 4), H = (i, j) => alt[((j + tam) % tam) * tam + ((i + tam) % tam)];
  for (let j = 0; j < tam; j++) for (let i = 0; i < tam; i++) {
    const dx = (H(i + 1, j - 1) + 2 * H(i + 1, j) + H(i + 1, j + 1)) - (H(i - 1, j - 1) + 2 * H(i - 1, j) + H(i - 1, j + 1));
    const dy = (H(i - 1, j + 1) + 2 * H(i, j + 1) + H(i + 1, j + 1)) - (H(i - 1, j - 1) + 2 * H(i, j - 1) + H(i + 1, j - 1));
    let nx = -dx * forcaNormal, ny = dy * forcaNormal, nz = 1; const l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
    const k = (j * tam + i) * 4; nor[k] = (nx * 0.5 + 0.5) * 255; nor[k + 1] = (ny * 0.5 + 0.5) * 255; nor[k + 2] = (nz * 0.5 + 0.5) * 255; nor[k + 3] = 255;
  }
  const mk = (dados, srgb) => {
    const c = document.createElement('canvas'); c.width = c.height = tam; c.getContext('2d').putImageData(new ImageData(dados, tam, tam), 0, 0);
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; return t;
  };
  return { map: mk(cor, true), normalMap: mk(nor, false), roughnessMap: mk(rug, false), altura: alt, tam };
}

// ------------------------------------------------------------------------------------ receitas ---

// Blocos de pedra em fiadas (aparelho de cantaria): juntas, desgaste, manchas e lascas.
export function blocos({ tam = 1024, semente = 1, fiadas = 6, comprimento = [0.34, 0.5], base = [196, 178, 140], variacao = 0.16, junta = 0.012, desgaste = 0.5, estratos = 0 } = {}) {
  const R = criarRuido(semente), R2 = criarRuido(semente + 7);
  const compFiada = Array.from({ length: fiadas }, (_, f) => comprimento[0] + (hash32(semente, f, 3) % 1000) / 1000 * (comprimento[1] - comprimento[0]));
  const desloc = Array.from({ length: fiadas }, (_, f) => (hash32(semente, f, 5) % 1000) / 1000);
  return gerar(tam, (u, v) => {
    const f = Math.floor(v * fiadas), lv = v * fiadas - f, L = compFiada[f] ?? 0.4;
    const uu = u / L + desloc[f] * 3, bi = Math.floor(uu), lu = uu - bi;
    const dBorda = Math.min(lu * L, (1 - lu) * L, lv / fiadas * 1, (1 - lv) / fiadas);
    const alvo = junta * (0.7 + 0.6 * R.noise(u * 40, v * 40));
    const naJunta = dBorda < alvo ? 1 : 0;
    const bloco = hash32(semente, f, bi) % 1000 / 1000;
    const g = 0.5 + 0.5 * R.fbm(u * 12 + bloco * 9, v * 12, 5);
    const mancha = R2.fbm(u * 3, v * 3, 4);
    let k = 1 - variacao + 2 * variacao * bloco;
    k *= 0.82 + 0.3 * g;
    k *= 1 - desgaste * 0.25 * Math.pow(mancha, 2);
    if (estratos) k *= 1 - estratos * 0.08 * Math.sin(v * fiadas * 18 + R.noise(u * 4, v * 20) * 6);
    const bordaSuave = clamp((dBorda - alvo) / 0.02);
    k *= mix(0.45, 1, bordaSuave);
    const c = base.map((x) => clamp(x * k, 0, 255));
    const poro = R.noise(u * 140, v * 140) > 0.82 ? 0.88 : 1;
    return { c: c.map((x) => x * poro), h: naJunta ? 0.05 : 0.5 + 0.35 * g * bordaSuave + 0.1 * R.noise(u * 60, v * 60), r: mix(0.95, 0.75, 1 - g * 0.5) };
  }, { forcaNormal: 4.5 });
}

// Mármore claro com veios finos, escorrimentos verticais e juntas de tambores (para colunas: u = perímetro, v = altura).
export function marmore({ tam = 1024, semente = 2, tambores = 7, base = [226, 217, 197], veios = 0.5, junta = 0.004 } = {}) {
  const R = criarRuido(semente), R2 = criarRuido(semente + 3);
  return gerar(tam, (u, v) => {
    const w = R.fbm(u * 6 + R2.fbm(u * 8, v * 3, 3) * 2.5, v * 3, 5, 6);
    const veio = Math.pow(1 - Math.abs(Math.sin((u * 5 + w * 3 + v * 0.7) * Math.PI * 2 * 0.5)), 14) * veios;
    const escorre = R2.fbm(u * 24, v * 1.2, 4, 24) * 0.6;
    const fd = (v * tambores) % 1, naJunta = fd < junta * tambores || fd > 1 - junta * tambores ? 1 : 0;
    let k = 0.9 + 0.12 * w - 0.2 * escorre * escorre - 0.25 * veio;
    if (naJunta) k *= 0.62;
    const tom = mixc(base, [196, 176, 140], clamp(escorre * 0.8 + (1 - w) * 0.25));
    return { c: tom.map((x) => clamp(x * k, 0, 255)), h: naJunta ? 0.15 : 0.55 + 0.08 * w, r: 0.62 + 0.25 * escorre };
  }, { forcaNormal: 2.0 });
}

export function areia({ tam = 1024, semente = 3, base = [214, 176, 112], ondas = 14 } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const o = R.fbm(u * 3 + R.noise(u * 5, v * 5, 5) * 0.6, v * ondas, 5, 3);
    const rip = 0.5 + 0.5 * Math.sin((v + R.noise(u * 6, v * 2, 6) * 0.25) * ondas * Math.PI * 2);
    const g = R.noise(u * 220, v * 220);
    const k = 0.78 + 0.28 * o + 0.1 * rip + 0.06 * g;
    return { c: mixc(base, [236, 204, 150], clamp(rip * 0.5)).map((x) => clamp(x * k, 0, 255)), h: 0.4 + 0.5 * rip * o, r: 0.97 };
  }, { forcaNormal: 3.2 });
}

// Reboco antigo (Judeia): paredes caiadas com manchas, fissuras e remendos de pedra à mostra.
export function reboco({ tam = 1024, semente = 4, base = [214, 200, 172], remendos = 0.5 } = {}) {
  const R = criarRuido(semente), R2 = criarRuido(semente + 11);
  return gerar(tam, (u, v) => {
    const m = R.fbm(u * 6, v * 6, 5, 6), manc = R2.fbm(u * 2.5, v * 2.5, 4, 3), fis = Math.pow(1 - Math.abs(R.noise(u * 9, v * 9, 9) * 2 - 1), 12);
    const pedra = R2.noise(u * 7, v * 7, 7) > 1 - remendos * 0.22 ? 1 : 0;
    let k = 0.88 + 0.2 * m - 0.28 * Math.pow(manc, 3) - 0.35 * fis;
    let c = base.map((x) => x * k);
    if (pedra) { const b = 0.62 + 0.3 * R.noise(u * 60, v * 60); c = [168 * b, 148 * b, 118 * b]; }
    return { c: c.map((x) => clamp(x, 0, 255)), h: pedra ? 0.35 : 0.55 + 0.2 * m - 0.3 * fis, r: 0.93 };
  }, { forcaNormal: 3.0 });
}

export function lajes({ tam = 1024, semente = 5, n = 5, base = [150, 138, 118] } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const cu = u * n + 0.35 * R.noise(u * 3, v * 3, 3), cv = v * n + 0.35 * R.noise(u * 3 + 9, v * 3, 3);
    const iu = Math.floor(cu), iv = Math.floor(cv), fu = cu - iu, fv = cv - iv, borda = Math.min(fu, 1 - fu, fv, 1 - fv);
    const id = hash32(semente, ((iu % n) + n) % n, ((iv % n) + n) % n) % 1000 / 1000, g = R.fbm(u * 18, v * 18, 5, 18);
    const k = (0.75 + 0.3 * id) * (0.8 + 0.3 * g) * (borda < 0.035 ? 0.5 : 1);
    return { c: base.map((x) => clamp(x * k, 0, 255)), h: borda < 0.035 ? 0.1 : 0.5 + 0.3 * g, r: 0.9 };
  }, { forcaNormal: 4.0 });
}

export function terra({ tam = 1024, semente = 6, base = [128, 104, 74] } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const g = R.fbm(u * 10, v * 10, 6, 10), s = R.noise(u * 200, v * 200), pedr = R.noise(u * 30, v * 30, 30) > 0.86 ? 1 : 0;
    const k = 0.7 + 0.4 * g + 0.1 * s;
    const c = pedr ? [150 * (0.7 + 0.3 * s), 138 * (0.7 + 0.3 * s), 120 * (0.7 + 0.3 * s)] : base.map((x) => x * k);
    return { c: c.map((x) => clamp(x, 0, 255)), h: 0.4 + 0.4 * g + (pedr ? 0.2 : 0), r: 0.98 };
  }, { forcaNormal: 3.5 });
}

export function rocha({ tam = 1024, semente = 7, base = [118, 112, 104] } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const c = R.cresta(u * 5, v * 5, 6, 5), g = R.fbm(u * 18, v * 18, 5, 18), l = R.noise(u * 7, v * 9, 7);
    const k = 0.55 + 0.6 * c * c + 0.2 * g;
    return { c: mixc(base, [150, 140, 126], l * 0.5).map((x) => clamp(x * k, 0, 255)), h: c, r: 0.92 };
  }, { forcaNormal: 5.0 });
}

export function madeira({ tam = 512, semente = 8, base = [112, 78, 48] } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const veio = R.fbm(u * 2 + R.noise(u * 6, v * 1.5, 6) * 0.8, v * 28, 5), anel = 0.5 + 0.5 * Math.sin((u * 14 + veio * 5) * Math.PI);
    const k = 0.7 + 0.4 * veio + 0.15 * anel;
    return { c: base.map((x) => clamp(x * k, 0, 255)), h: 0.4 + 0.3 * veio, r: 0.8 };
  }, { forcaNormal: 2.5 });
}

// Tecido (toldos, panos): trama fina com listras largas de tintura natural.
export function pano({ tam = 512, semente = 9, cores = [[176, 62, 44], [226, 208, 170]], listras = 6 } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const st = Math.floor(u * listras * 2) % 2, trama = 0.5 + 0.5 * Math.sin(u * tam * 0.55) * Math.sin(v * tam * 0.55), g = R.fbm(u * 10, v * 10, 4, 10);
    const c = cores[st].map((x) => clamp(x * (0.82 + 0.16 * trama + 0.12 * g), 0, 255));
    return { c, h: 0.5 + 0.2 * trama, r: 0.95 };
  }, { forcaNormal: 1.5 });
}

// Arenito pintado das colunas egípcias. ATENÇÃO: as "inscrições" são marcas abstratas estilizadas (retângulos, círculos, ondas), NÃO são
// hieróglifos legíveis nem texto real. modo 'fuste': registros verticais + folhas na base + faixas coloridas; modo 'capitel': pétalas pintadas.
export function egipcia({ tam = 1024, semente = 21, base = [208, 170, 118], modo = 'fuste', pintura = 0.75, paleta = null } = {}) {
  const R = criarRuido(semente), R2 = criarRuido(semente + 5);
  const pal = paleta ?? { azul: [58, 108, 128], verde: [74, 122, 92], verm: [150, 62, 46], ocre: [206, 152, 62], escuro: [58, 40, 28] };
  const cel = (cu, cv, tipo) => {            // máscara 0..1 de uma marca dentro de uma célula (cu, cv em 0..1)
    const x = cu - 0.5, y = cv - 0.5;
    switch (tipo % 7) {
      case 0: return Math.abs(x) < 0.26 && Math.abs(y) < 0.2 ? 1 : 0;                          // bloco
      case 1: return Math.hypot(x, y) < 0.26 ? 1 : 0;                                           // disco
      case 2: { const d = Math.hypot(x, y); return d < 0.28 && d > 0.15 ? 1 : 0; }              // anel
      case 3: return Math.abs(x) < 0.07 && Math.abs(y) < 0.36 ? 1 : 0;                          // barra vertical
      case 4: return Math.abs(y - 0.12 * Math.sin(cu * 12)) < 0.07 && Math.abs(x) < 0.4 ? 1 : 0;   // onda
      case 5: return y > -0.05 && Math.hypot(x, y + 0.05) < 0.3 && Math.hypot(x, y + 0.05) > 0.17 ? 1 : 0;   // arco
      default: return Math.abs(x) < 0.35 && Math.abs(y) < 0.05 || Math.abs(x) < 0.05 && Math.abs(y) < 0.3 ? 1 : 0;   // cruz de traços
    }
  };
  return gerar(tam, (u, v) => {
    const g = R.fbm(u * 8, v * 8, 5, 8), gran = R.noise(u * 300, v * 300), mancha = R2.fbm(u * 3, v * 3, 4, 3);
    let k = 0.84 + 0.26 * g + 0.05 * gran - 0.22 * Math.pow(mancha, 2.2);
    let c = base.map((x) => x * k), alt = 0.55 + 0.12 * g, rug = 0.9;
    let tinta = null, ta = 0;
    if (modo === 'fuste') {
      const nreg = 8, lu = (u * nreg) % 1, ri = Math.floor(u * nreg);
      if (v < 0.075) {                                                        // base: folhas triangulares verdes
        const ph = Math.abs(((u * 16) % 1) - 0.5) * 2, h = 0.075 * (1 - ph * 0.9);
        if (v < h) { tinta = ph < 0.12 ? pal.escuro : (Math.floor(u * 16) % 2 ? pal.verde : pal.azul); ta = 0.85; alt = 0.7; }
      } else if (v > 0.66 && v < 0.69) { tinta = pal.verm; ta = 0.85; }
      else if (v > 0.69 && v < 0.705) { tinta = pal.escuro; ta = 0.8; }
      else if (v > 0.705 && v < 0.74) { const b = Math.floor((v - 0.705) / 0.0117); tinta = [pal.azul, pal.ocre, pal.verde][b % 3]; ta = 0.85; alt = 0.62; }
      else if (v >= 0.075 && v <= 0.66) {
        if (lu < 0.045 || lu > 0.955) { tinta = pal.verm; ta = 0.65; alt = 0.3; }
        else {
          const ncv = 46, cvv = v * ncv, rj = Math.floor(cvv), lc = cvv - rj, lw = (lu - 0.045) / 0.91;
          const tipo = hash32(semente, ri, rj) % 11;
          if (tipo < 7 && lw > 0.12 && lw < 0.88) {
            const m = cel((lw - 0.12) / 0.76, lc, tipo);
            if (m) { c = c.map((x) => x * 0.55); alt = 0.2; const t2 = hash32(semente, ri, rj, 7) % 9; if (t2 < 5) { tinta = [pal.azul, pal.ocre, pal.verm, pal.verde, pal.azul][t2]; ta = 0.55; } }
          }
        }
      } else if (v > 0.78) { const b = Math.floor((v - 0.78) / 0.02); if (b % 3 === 0) { tinta = pal.ocre; ta = 0.5; } }
    } else {                                                                   // capitel: pétalas
      const ph = (u * 12) % 1, pe = Math.floor(u * 12), borda = Math.min(ph, 1 - ph);
      const mid = 0.5 - Math.abs(ph - 0.5);
      if (borda < 0.05) { tinta = pal.escuro; ta = 0.8; alt = 0.25; }
      else { tinta = [pal.azul, pal.verde, pal.verm][pe % 3]; ta = 0.7 * (0.55 + 0.45 * Math.min(1, v * 1.6)); alt = 0.6 + 0.3 * mid; }
      if (v > 0.9) { tinta = [pal.ocre, pal.verm][(Math.floor(u * 24)) % 2]; ta = 0.8; }
    }
    if (tinta && ta > 0) {
      const a = ta * pintura * (0.75 + 0.25 * R.noise(u * 90, v * 90)) * (g > 0.78 ? 0.7 : 1);       // tinta gasta em manchas
      c = [mix(c[0], tinta[0] * (0.8 + 0.3 * g), a), mix(c[1], tinta[1] * (0.8 + 0.3 * g), a), mix(c[2], tinta[2] * (0.8 + 0.3 * g), a)];
    }
    return { c: c.map((x) => clamp(x, 0, 255)), h: alt, r: rug };
  }, { forcaNormal: 3.5 });
}

// Teto pintado: azul-escuro com estrelas douradas de cinco pontas (motivo atestado em tetos de templos egípcios; aqui, estilizado).
export function teto({ tam = 1024, semente = 41, base = [26, 50, 104], n = 8 } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const g = R.fbm(u * 6, v * 6, 5, 6), gran = R.noise(u * 260, v * 260), mancha = R.fbm(u * 2.2 + 5, v * 2.2, 4, 2);
    const k = 0.78 + 0.34 * g + 0.06 * gran - 0.25 * Math.pow(mancha, 2.5);
    let c = base.map((x) => x * k), h = 0.5 + 0.1 * g;
    const cu = u * n, cv = v * n, iu = Math.floor(cu), iv = Math.floor(cv);
    const dx = cu - iu - 0.5, dy = cv - iv - 0.5, d = Math.hypot(dx, dy), ang = Math.atan2(dy, dx);
    const lobo = 0.5 + 0.5 * Math.cos(5 * ang + Math.PI);
    if (d < 0.07 + 0.14 * Math.pow(lobo, 2.2) && (hash32(semente, iu, iv) % 7) > 0) {
      const a = 0.85 * (g > 0.78 ? 0.6 : 1);
      c = [mix(c[0], 224 * (0.85 + 0.2 * g), a), mix(c[1], 176 * (0.85 + 0.2 * g), a), mix(c[2], 62, a)]; h = 0.35;
    }
    return { c: c.map((x) => clamp(x, 0, 255)), h, r: 0.92 };
  }, { forcaNormal: 3.0 });
}

// Água: relevo de ondas (apenas o normalMap importa). Repetível; o movimento vem de deslocar a textura em função do tempo.
export function agua({ tam = 512, semente = 31 } = {}) {
  const R = criarRuido(semente);
  return gerar(tam, (u, v) => {
    const o = R.fbm(u * 6 + R.noise(u * 3, v * 9, 3) * 0.7, v * 14, 5, 6) * 0.7 + R.cresta(u * 10, v * 10, 4, 10) * 0.3;
    return { c: [24, 56, 62], h: o, r: 0.04 };
  }, { forcaNormal: 2.2 });
}

export function aplicar(mat, t, repeticao = [1, 1], { normal = 1.0 } = {}) {
  for (const k of ['map', 'normalMap', 'roughnessMap']) { if (t[k]) { t[k].repeat.set(repeticao[0], repeticao[1]); } }
  mat.map = t.map; mat.normalMap = t.normalMap; mat.roughnessMap = t.roughnessMap; mat.normalScale = new THREE.Vector2(normal, normal);
  mat.needsUpdate = true;
  return mat;
}
