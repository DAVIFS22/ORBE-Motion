// Ferramenta de inspeção (não usada no filme): mostra mapas de cor e normal de uma textura procedural lado a lado.
// params: { receita: 'terra', opcoes: {...} }
import * as tex from '../engine/tex.js';
import { el, canvas } from '../engine/ui.js';

export const amostra_tex = {
  async build(palco, spec) {
    const P = spec.params;
    const t = tex[P.receita]({ tam: 512, ...(P.opcoes || {}) });
    const raiz = el('div', { left: '0', top: '0', width: '1920px', height: '1080px', background: '#111' }, palco);
    const a = canvas(940, 940, { left: '10px', top: '70px' }, raiz), b = canvas(940, 940, { left: '970px', top: '70px' }, raiz);
    const ga = a.getContext('2d'), gb = b.getContext('2d');
    for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) { ga.drawImage(t.map.image, i * 470, j * 470, 470, 470); gb.drawImage(t.normalMap.image, i * 470, j * 470, 470, 470); }
    el('div', { left: '20px', top: '16px', color: '#ddd', font: '600 30px Inter' }, raiz, `${P.receita} — cor (2×2 repetições) | normal`);
    return { eventos: [], seek() {} };
  },
};
