// API da página: window.loadScene(spec) monta a cena; window.seek(t) desenha o quadro do instante t (segundos).
// seek é uma função pura do tempo: sem estado acumulado entre chamadas, sem timers, sem requestAnimationFrame.
import { COMPS } from '../comps/index.js';

let atual = null;
const palco = document.getElementById('stage');

window.loadScene = async function (spec) {
  palco.replaceChildren();               // nada sobra da cena anterior
  atual = null;
  const comp = COMPS[spec.comp];
  if (!comp) throw new Error('composição desconhecida: ' + spec.comp);
  await document.fonts.load('600 40px "Cinzel"');
  await document.fonts.load('700 40px "Cinzel"');
  await document.fonts.load('400 40px "Inter"');
  await document.fonts.load('500 40px "Inter"');
  await document.fonts.load('600 40px "Inter"');
  await document.fonts.ready;
  atual = await comp.build(palco, spec);
  atual.t0 = spec.t0 ?? 0;                 // o clipe começa t0 s antes do plano (metade da transição de entrada)
  return { dur: spec.dur, eventos: atual.eventos ?? [] };
};

window.seek = function (t) {
  if (!atual) throw new Error('nenhuma cena carregada');
  atual.seek(Math.max(0, t - atual.t0));     // tempo da composição: 0 = início do plano
};

window.__pronto = true;
