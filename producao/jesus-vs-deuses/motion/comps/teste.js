// Cena de teste do motor: usada pelos testes de contrato/determinismo e para medir desempenho.
import { rngFor } from '../engine/rng.js';
import { el, canvas, pose, COR, FONTE } from '../engine/ui.js';
import { prog, outCubic, inOutSine } from '../engine/ease.js';

export const teste = {
  async build(palco, spec) {
    const W = 1920, H = 1080;
    const raiz = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', perspective: '1400px' }, palco);
    const c = canvas(W, H, {}, raiz);
    const g = c.getContext('2d');
    const placa = el('div', { left: '1080px', top: '160px', width: '520px', height: '720px', background: 'linear-gradient(160deg,#caa45a,#5a3f17)', transformStyle: 'preserve-3d' }, raiz);
    const titulo = el('div', { left: '120px', top: '380px', font: `700 140px ${FONTE.display}`, color: COR.marfim, whiteSpace: 'nowrap' }, raiz, 'TESTE');
    const sementes = spec.seed ?? 1;
    return {
      seek(t) {
        g.clearRect(0, 0, W, H);
        g.fillStyle = COR.tinta; g.fillRect(0, 0, W, H);
        for (let i = 0; i < 60; i++) {
          const r = rngFor(sementes, i);
          const x = (r() * W + t * (10 + r() * 40)) % W, y = (r() * H - t * (6 + r() * 20) + H) % H;
          g.fillStyle = `rgba(232,190,105,${0.15 + 0.35 * r()})`;
          g.beginPath(); g.arc(x, y, 1 + 2 * r(), 0, 6.283); g.fill();
        }
        pose(placa, { ry: -20 + 14 * prog(t, 0, 2, outCubic) + 3 * Math.sin(t), z: -300 + 300 * prog(t, 0, 2), o: prog(t, 0, 0.6) });
        pose(titulo, { x: -200 * (1 - prog(t, 0.2, 1.4)), o: prog(t, 0.2, 1.0) });
      },
    };
  },
};
