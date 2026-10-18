// Atmosfera 2D determinística: poeira em suspensão, granulação de filme e vinheta. Tudo depende só de (semente, t).
import { rngFor, hash32 } from './rng.js';
import { el } from './ui.js';

function sprite(r = 16) {
  const c = document.createElement('canvas'); c.width = c.height = r * 2;
  const g = c.getContext('2d'); const gr = g.createRadialGradient(r, r, 0, r, r, r);
  gr.addColorStop(0, 'rgba(255,236,190,1)'); gr.addColorStop(0.35, 'rgba(255,220,150,0.45)'); gr.addColorStop(1, 'rgba(255,210,140,0)');
  g.fillStyle = gr; g.fillRect(0, 0, r * 2, r * 2);
  return c;
}

// Partículas de poeira: posição = função linear do tempo (módulo da tela). Nada é acumulado.
export function criarPoeira(canvas, { semente, n = 70, tam = [3, 12], vel = [4, 18], brilho = 0.5 }) {
  const g = canvas.getContext('2d'); const W = canvas.width, H = canvas.height; const sp = sprite(16);
  const ps = Array.from({ length: n }, (_, i) => {
    const r = rngFor(semente, i);
    const prof = r();
    return { x0: r() * W, y0: r() * H, vx: (vel[0] + r() * vel[1]) * (0.4 + prof), vy: -(2 + r() * vel[1] * 0.5) * (0.4 + prof), s: tam[0] + (tam[1] - tam[0]) * prof * prof, fase: r() * 6.283, b: 0.25 + r() * 0.75 };
  });
  return {
    desenhar(t, a = 1) {
      g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, W, H);
      for (const p of ps) {
        const x = (((p.x0 + p.vx * t) % W) + W) % W, y = (((p.y0 + p.vy * t) % H) + H) % H;
        g.globalAlpha = Math.max(0, Math.min(1, brilho * p.b * (0.55 + 0.45 * Math.sin(t * 1.1 + p.fase)) * a));
        g.drawImage(sp, x - p.s, y - p.s, p.s * 2, p.s * 2);
      }
      g.globalAlpha = 1;
    },
  };
}

// Granulação: mosaico de ruído (mulberry32) cujo deslocamento muda 24 vezes por segundo, de forma determinística.
export function criarGrao(pai, semente, intensidade = 0.16) {
  const N = 256; const c = document.createElement('canvas'); c.width = c.height = N;
  const g = c.getContext('2d'); const im = g.createImageData(N, N); const r = rngFor(semente, 99991);
  for (let i = 0; i < N * N; i++) { const v = Math.floor(r() * 255); im.data[4 * i] = im.data[4 * i + 1] = im.data[4 * i + 2] = v; im.data[4 * i + 3] = 255; }
  g.putImageData(im, 0, 0);
  const e = el('div', { left: '0', top: '0', width: '1920px', height: '1080px', backgroundImage: `url(${c.toDataURL()})`, backgroundSize: '256px 256px', mixBlendMode: 'overlay', opacity: String(intensidade), pointerEvents: 'none' }, pai);
  return { aplicar(t) { const q = Math.floor(t * 24); e.style.backgroundPosition = `${hash32(semente, q) % 256}px ${hash32(semente, q, 7) % 256}px`; } };
}

export function criarVinheta(pai, forca = 0.62) {
  return el('div', { left: '0', top: '0', width: '1920px', height: '1080px', pointerEvents: 'none',
    background: `radial-gradient(ellipse 75% 70% at 50% 50%, rgba(0,0,0,0) 45%, rgba(0,0,0,${forca}) 100%)` }, pai);
}

// Camada final única (um só elemento de composição): poeira dourada, vinheta e granulação de filme.
// Tudo é desenhado a cada quadro em um canvas 1920×1080 transparente, só a partir de (semente, t).
export function criarCamadaFinal(pai, { semente, poeira = { n: 60, brilho: 0.5 }, vinheta = 0.6, grao = 0.10 }) {
  const W = 1920, H = 1080;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  Object.assign(cv.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px', pointerEvents: 'none' });
  pai.appendChild(cv);
  const g = cv.getContext('2d');
  // ruído de média zero: pontos claros e escuros com opacidade proporcional ao desvio (não clareia nem escurece o conjunto)
  const N = 256; const tile = document.createElement('canvas'); tile.width = tile.height = N;
  { const gt = tile.getContext('2d'); const im = gt.createImageData(N, N); const r = rngFor(semente, 99991);
    for (let i = 0; i < N * N; i++) { const v = r() * 2 - 1; const c = v > 0 ? 255 : 0; im.data[4 * i] = im.data[4 * i + 1] = im.data[4 * i + 2] = c; im.data[4 * i + 3] = Math.round(Math.abs(v) * grao * 255); }
    gt.putImageData(im, 0, 0); }
  const padrao = g.createPattern(tile, 'repeat');
  const sp = sprite(16);
  const ps = Array.from({ length: poeira.n }, (_, i) => {
    const r = rngFor(semente, i); const prof = r();
    return { x0: r() * W, y0: r() * H, vx: (4 + r() * 18) * (0.4 + prof), vy: -(2 + r() * 9) * (0.4 + prof), s: 3 + 9 * prof * prof, fase: r() * 6.283, b: 0.25 + r() * 0.75 };
  });
  const vig = g.createRadialGradient(W / 2, H / 2, 0.30 * H, W / 2, H / 2, 0.98 * H);
  vig.addColorStop(0, 'rgba(0,0,0,0)'); vig.addColorStop(1, `rgba(0,0,0,${vinheta})`);
  return {
    desenhar(t, a = 1) {
      g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, W, H);
      for (const p of ps) {
        const x = (((p.x0 + p.vx * t) % W) + W) % W, y = (((p.y0 + p.vy * t) % H) + H) % H;
        g.globalAlpha = Math.max(0, Math.min(1, poeira.brilho * p.b * (0.55 + 0.45 * Math.sin(t * 1.1 + p.fase)) * a));
        g.drawImage(sp, x - p.s, y - p.s, p.s * 2, p.s * 2);
      }
      g.globalAlpha = 1;
      g.fillStyle = vig; g.fillRect(0, 0, W, H);
      const q = Math.floor(t * 24);
      g.save(); g.translate(hash32(semente, q) % N, hash32(semente, q, 7) % N); g.fillStyle = padrao; g.fillRect(-N, -N, W + 2 * N, H + 2 * N); g.restore();
      g.restore();
    },
  };
}
