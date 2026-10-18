// Funções puras de tempo. Nenhuma guarda estado.
export const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
export const lerp = (a, b, k) => a + (b - a) * k;
export const smooth = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
export const outCubic = (x) => 1 - Math.pow(1 - clamp01(x), 3);
export const inCubic = (x) => Math.pow(clamp01(x), 3);
export const inOutCubic = (x) => { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
export const outExpo = (x) => { x = clamp01(x); return x === 1 ? 1 : 1 - Math.pow(2, -10 * x); };
export const inOutSine = (x) => -(Math.cos(Math.PI * clamp01(x)) - 1) / 2;
// Passa de 0 a 1 entre t0 e t1 (ou 1 a 0 se t1 < t0), com a curva escolhida.
export const prog = (t, t0, t1, curva = outCubic) => curva(clamp01((t - t0) / (t1 - t0)));
// Entrada e saída: sobe em [a,b], fica, desce em [c,d].
export const janela = (t, a, b, c, d, curva = smooth) => curva(clamp01((t - a) / (b - a))) * (1 - curva(clamp01((t - c) / (d - c))));
// Salto com leve ultrapassagem (mola amortecida), função fechada do tempo.
export const mola = (x, amort = 6, freq = 9) => { x = clamp01(x); return x >= 1 ? 1 : 1 - Math.exp(-amort * x) * Math.cos(freq * x); };
// Alinha um instante desejado à batida mais próxima (dentro da tolerância); sem batidas devolve o desejado.
export function aBatida(t, batidas, tol = 0.3) {
  if (!batidas || !batidas.length) return t;
  let melhor = t, d = tol + 1e-9;
  for (const b of batidas) { const e = Math.abs(b - t); if (e < d) { d = e; melhor = b; } }
  return melhor;
}
