// Base cartográfica: dados do Natural Earth (domínio público) já simplificados em data/mapa.json.
// Projeção Mercator; a câmera do mapa é (lon, lat, largura em graus de longitude visível) e é sempre função do tempo.
import { COR } from './ui.js';

let cache = null;

export async function carregarMapa() {
  if (cache) return cache;
  const bruto = await (await fetch('/data/mapa.json')).json();
  const merc = (lon, lat) => [(lon * Math.PI) / 180, Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))];
  const anel = (plano) => {
    const xs = new Float64Array(plano.length / 2), ys = new Float64Array(plano.length / 2);
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < xs.length; i++) {
      const [x, y] = merc(plano[2 * i], Math.max(-85, Math.min(85, plano[2 * i + 1])));
      xs[i] = x; ys[i] = y; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    return { xs, ys, caixa: [x0, y0, x1, y1] };
  };
  cache = {
    terra: bruto.terra.map(anel),
    rios: bruto.rios.map((r) => ({ nome: r.nome, linhas: r.linhas.map(anel) })),
    lagos: bruto.lagos.map((l) => ({ nome: l.nome, aneis: l.aneis.map(anel) })),
    fonte: bruto.fonte,
  };
  return cache;
}

export const merc = (lon, lat) => [(lon * Math.PI) / 180, Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))];

// Vista: centro (lon,lat) e largura visível em graus -> função de projeção para pixels do canvas W×H.
export function vista(lon, lat, largGraus, W, H) {
  const s = W / ((largGraus * Math.PI) / 180);
  const [cx, cy] = merc(lon, lat);
  return { s, cx, cy, W, H, proj: (lo, la) => { const [x, y] = merc(lo, la); return [W / 2 + (x - cx) * s, H / 2 - (y - cy) * s]; } };
}

function trilha(g, an, v, fechar) {
  const { xs, ys } = an;
  g.moveTo(v.W / 2 + (xs[0] - v.cx) * v.s, v.H / 2 - (ys[0] - v.cy) * v.s);
  for (let i = 1; i < xs.length; i++) g.lineTo(v.W / 2 + (xs[i] - v.cx) * v.s, v.H / 2 - (ys[i] - v.cy) * v.s);
  if (fechar) g.closePath();
}

function visivel(an, v, margem = 40) {
  const [x0, y0, x1, y1] = an.caixa;
  const l = v.W / 2 + (x0 - v.cx) * v.s, r = v.W / 2 + (x1 - v.cx) * v.s, t = v.H / 2 - (y1 - v.cy) * v.s, b = v.H / 2 - (y0 - v.cy) * v.s;
  return r > -margem && l < v.W + margem && b > -margem && t < v.H + margem;
}

// Desenha mar, grade, terra, lagos e rios. Estilo: costa com brilho ouro discreto; Nilo destacado.
export function desenharMapa(g, mapa, v, o = {}) {
  g.save();                              // nenhum estado de desenho (cap/join/dash/fonte) vaza entre quadros
  g.setTransform(1, 0, 0, 1, 0, 0);
  const { W, H } = v;
  const mar = g.createLinearGradient(0, 0, 0, H);
  mar.addColorStop(0, o.marTopo || '#060d14'); mar.addColorStop(1, o.marBase || '#09131c');
  g.fillStyle = mar; g.fillRect(0, 0, W, H);
  // grade de lon/lat (passo conforme o zoom)
  const larg = (W / v.s) * (180 / Math.PI);
  const passo = larg > 60 ? 10 : larg > 25 ? 5 : larg > 10 ? 2 : 1;
  g.lineWidth = 1; g.strokeStyle = 'rgba(190,205,220,0.06)'; g.beginPath();
  const lonC = (v.cx * 180) / Math.PI;
  for (let lo = Math.floor((lonC - larg) / passo) * passo; lo <= lonC + larg; lo += passo) { const [x] = v.proj(lo, 0); g.moveTo(x, 0); g.lineTo(x, H); }
  const latC = (Math.atan(Math.sinh(v.cy)) * 180) / Math.PI;
  for (let la = Math.floor((latC - larg) / passo) * passo; la <= latC + larg; la += passo) { const [, y] = v.proj(0, la); g.moveTo(0, y); g.lineTo(W, y); }
  g.stroke();
  // terra
  g.beginPath();
  for (const an of mapa.terra) if (visivel(an, v)) trilha(g, an, v, true);
  g.fillStyle = o.terra || '#34454f'; g.fill('evenodd');
  g.lineJoin = 'round'; g.lineWidth = o.costaLargura || 2; g.strokeStyle = o.costa || 'rgba(232,190,105,0.62)'; g.stroke();
  // lagos
  g.beginPath();
  for (const l of mapa.lagos) for (const an of l.aneis) if (visivel(an, v)) trilha(g, an, v, true);
  g.fillStyle = o.marBase || '#09131c'; g.fill('evenodd'); g.strokeStyle = 'rgba(232,190,105,0.35)'; g.lineWidth = 1.2; g.stroke();
  // rios
  for (const r of mapa.rios) {
    const nilo = r.nome === 'Nile' || r.nome.endsWith('Branch');
    g.beginPath();
    for (const an of r.linhas) if (visivel(an, v)) trilha(g, an, v, false);
    g.lineCap = 'round'; g.lineJoin = 'round';
    if (nilo && o.realceNilo) { g.strokeStyle = `rgba(232,190,105,${o.realceNilo * 0.28})`; g.lineWidth = Math.max(8, v.s * 0.0009); g.stroke(); }
    g.strokeStyle = nilo ? 'rgba(232,190,105,0.85)' : 'rgba(150,170,190,0.45)'; g.lineWidth = nilo ? Math.max(2, v.s * 0.00022) : 1.4; g.stroke();
  }
  g.restore();
}

// Interpolação de câmera por quadros-chave {f: fração do clipe, lon, lat, larg}; zoom exponencial, curva suave entre chaves.
export function camera(chaves, f, curva) {
  if (f <= chaves[0].f) return { lon: chaves[0].lon, lat: chaves[0].lat, larg: chaves[0].larg };
  for (let i = 1; i < chaves.length; i++) {
    if (f <= chaves[i].f) {
      const a = chaves[i - 1], b = chaves[i];
      const k = curva((f - a.f) / Math.max(1e-6, b.f - a.f));
      return { lon: a.lon + (b.lon - a.lon) * k, lat: a.lat + (b.lat - a.lat) * k, larg: Math.exp(Math.log(a.larg) + (Math.log(b.larg) - Math.log(a.larg)) * k) };
    }
  }
  const u = chaves[chaves.length - 1];
  return { lon: u.lon, lat: u.lat, larg: u.larg };
}

export { COR };
