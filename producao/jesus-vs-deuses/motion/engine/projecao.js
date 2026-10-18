// Projeção em perspectiva de um plano (rotação em X + câmera com distância focal) feita por nós, em Canvas 2D.
// Cada linha da imagem de origem vira uma faixa horizontal com escala uniforme (exato para rotateX): o resultado é uma
// função pura de (tilt, câmera), sem depender de camadas de composição do navegador (que guardam histórico de raster).

export function criarProjecao({ tilt, persp, cx, cy }) {
  const th = (tilt * Math.PI) / 180, c = Math.cos(th), s = Math.sin(th);
  // (u, v) relativos ao centro do plano -> tela. k = escala de perspectiva naquele ponto.
  return (u, v) => { const k = persp / (persp - v * s); return { x: cx + u * k, y: cy + v * c * k, k }; };
}

export function desenharPlano(dst, src, geo, passo = 2) {
  const f = criarProjecao(geo);
  const W = src.width, H = src.height, DH = dst.canvas.height;
  dst.imageSmoothingEnabled = true; dst.imageSmoothingQuality = 'medium';
  for (let j = 0; j < H; j += passo) {
    const v0 = j - H / 2, v1 = Math.min(H, j + passo) - H / 2;
    const a = f(0, v0), b = f(0, v1);
    const h = b.y - a.y;
    if (h <= 0 || b.y < 0 || a.y > DH) continue;
    dst.drawImage(src, 0, j, W, v1 - v0, geo.cx - (W / 2) * a.k, a.y, W * a.k, h + 0.7);
  }
}
