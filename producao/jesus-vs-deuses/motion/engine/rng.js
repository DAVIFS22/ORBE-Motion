// Ruído pseudoaleatório SEMPRE com semente (mulberry32). Math.random é proibido neste projeto.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Combina números inteiros em um único inteiro de 32 bits (FNV-1a com mistura final).
export function hash32(...valores) {
  let h = 2166136261 >>> 0;
  for (const v of valores) {
    h ^= (v | 0) >>> 0;
    h = Math.imul(h, 16777619) >>> 0;
    h ^= h >>> 13;
  }
  return h >>> 0;
}

// Gerador independente para (semente, chaves...): o mesmo par produz a mesma sequência em qualquer ordem de chamada.
export function rngFor(seed, ...chaves) {
  return mulberry32(hash32(seed, ...chaves));
}
