// Utilitários de DOM/Canvas. Tudo escreve o estado completo a partir dos argumentos (nada é lido de volta).
export const COR = {
  tinta: '#07080c', tintaQuente: '#0e0b08', marfim: '#efe6d2', marfimSuave: 'rgba(239,230,210,0.82)', mudo: '#9d927c',
  ouro: '#e8be69', ouroEscuro: '#9a7a35', mar: '#0c1218', terra: '#1b242c', costa: '#46586a',
};
export const FONTE = { display: '"Cinzel", "Times New Roman", serif', ui: '"Inter", "Helvetica Neue", Arial, sans-serif' };

export function el(tag, estilo = {}, pai = null, texto = null) {
  const e = document.createElement(tag);
  // Sem will-change e sem transform 3D nos textos: nada é promovido a camada própria, então o raster não depende do histórico
  // de quadros (determinismo) e a composição por software fica rápida. Só a geometria 3D usa pose() (camada própria fixa).
  Object.assign(e.style, { position: 'absolute', margin: '0', padding: '0', boxSizing: 'border-box' }, estilo);
  if (texto !== null) e.textContent = texto;
  if (pai) pai.appendChild(e);
  return e;
}

export function canvas(w, h, estilo = {}, pai = null) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  Object.assign(c.style, { position: 'absolute', left: '0', top: '0', width: w + 'px', height: h + 'px' }, estilo);
  if (pai) pai.appendChild(c);
  return c;
}

// Aplica transformação 3D completa (ordem fixa) e opacidade. Valores omitidos usam o neutro.
export function pose(e, { x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, s = 1, o = 1 } = {}) {
  e.style.willChange = 'transform, opacity';   // sempre em camada própria: o raster não depende do histórico de quadros
  e.style.transform = `translate3d(${x}px, ${y}px, ${z}px) rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${rz}deg) scale(${s})`;
  e.style.opacity = String(o);
}

export function carregarImagem(url) {
  return new Promise((ok, erro) => {
    const im = new Image();
    im.onload = async () => { try { await im.decode(); } catch (_) { /* já carregada */ } ok(im); };
    im.onerror = () => erro(new Error('imagem não carregou: ' + url));
    im.src = url;
  });
}

// Divide um texto em letras (spans) para revelar caractere a caractere; devolve {raiz, letras}.
export function letras(texto, estilo, pai) {
  const raiz = el('div', Object.assign({ whiteSpace: 'nowrap', display: 'flex' }, estilo), pai);
  const spans = [];
  for (const ch of texto) {
    const s = document.createElement('span');
    s.textContent = ch === ' ' ? ' ' : ch;
    Object.assign(s.style, { display: 'inline-block', position: 'relative' });
    raiz.appendChild(s);
    spans.push(s);
  }
  return { raiz, letras: spans };
}

// Máscara de revelação de linha: o conteúdo sobe de baixo para dentro da janela (clip).
export function janelaMascara(estilo, pai) {
  return el('div', Object.assign({ overflow: 'hidden' }, estilo), pai);
}

export const rotulo = (texto) => String(texto).toUpperCase();
