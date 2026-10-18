// GSAP sob o contrato determinístico: a linha do tempo nasce pausada e só avança por seek explícito (tempo absoluto).
// O ticker do GSAP é posto para dormir e o rAF do navegador é neutralizado pelo render.mjs: nada anda sozinho.
import { gsap } from 'gsap';

gsap.ticker.lagSmoothing(false);

// montar(tl, gsap) registra tweens (preferir fromTo: o estado final de cada instante não depende do anterior).
export function linha(montar) {
  const tl = gsap.timeline({ paused: true, defaults: { overwrite: false } });
  montar(tl, gsap);
  gsap.ticker.sleep();
  return {
    tl,
    ir(t) { tl.totalTime(Math.max(0, t), false); },   // suppressEvents = false: aplica todos os valores do instante t
    duracao: tl.duration(),
  };
}

export { gsap };
