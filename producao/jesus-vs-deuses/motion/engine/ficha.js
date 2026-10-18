// Ficha informativa: hierarquia tipográfica única para divindades, lugares, datas e fontes.
//   eyebrow (civilização · papel)  >  nome (fonte de exibição)  >  regra  >  período + categoria  >  descrição  >  fonte
// Tudo é função do tempo: aplicar(t) escreve o estado completo; nada é lido de volta.
import { el, COR, FONTE, pose } from './ui.js';
import { prog, outCubic, outExpo, inCubic, smooth, clamp01 } from './ease.js';

const TAM = { eyebrow: 32, periodo: 38, descricao: 41, fonte: 28, chip: 26 };

const CATEGORIAS = {
  historico: { rotulo: 'FATO HISTÓRICO', estilo: 'cheio' },
  mitologico: { rotulo: 'TRADIÇÃO MITOLÓGICA', estilo: 'vazado' },
  academico: { rotulo: 'DATAÇÃO ACADÊMICA', estilo: 'sublinhado' },
  religioso: { rotulo: 'CRENÇA RELIGIOSA', estilo: 'vazado' },
  fonte: { rotulo: 'FONTE ANTIGA', estilo: 'sublinhado' },
};

function medirTexto(texto, fonte) {
  const c = document.createElement('canvas').getContext('2d');
  c.font = fonte;
  return c.measureText(texto).width;
}

// Quebra em linhas pela largura máxima (medida com a mesma fonte renderizada).
function quebrar(texto, fonte, largura) {
  const linhas = [];
  let atual = '';
  for (const p of texto.split(/\s+/)) {
    const teste = atual ? atual + ' ' + p : p;
    if (medirTexto(teste, fonte) <= largura || !atual) atual = teste; else { linhas.push(atual); atual = p; }
  }
  if (atual) linhas.push(atual);
  return linhas;
}

// Linha cujo conteúdo sobe de baixo para dentro de uma janela de corte (revelação por máscara).
function linhaMascara(pai, x, y, largura, altura, texto, estilo) {
  const jan = el('div', { left: x + 'px', top: y + 'px', width: largura + 'px', height: altura + 'px', overflow: 'hidden' }, pai);
  const t = el('div', Object.assign({ left: '0', top: '0', width: largura + 'px', whiteSpace: 'nowrap', lineHeight: altura + 'px' }, estilo), jan, texto);
  return { jan, t, altura };
}

export function construirFicha(pai, cfg, { x, y, largura, alinhar = 'esq' }) {
  const refs = [];
  let cy = y;
    const fp = `500 ${TAM.periodo}px ${FONTE.ui}`;
  const fd = `400 ${TAM.descricao}px ${FONTE.ui}`;
  const cat = cfg.categoria ? CATEGORIAS[cfg.categoria] : null;

  // eyebrow
  const txtEb = (cfg.eyebrow || '').toUpperCase();
  let tamEb = TAM.eyebrow;
  while (tamEb > 20 && medirTexto(txtEb, `600 ${tamEb}px ${FONTE.ui}`) + txtEb.length * tamEb * 0.2 > largura) tamEb -= 1;   // cabe sempre em uma linha
  const eb = linhaMascara(pai, x, cy, largura, 46, txtEb, { font: `600 ${tamEb}px ${FONTE.ui}`, letterSpacing: '0.2em', color: COR.ouro });
  cy += 56;

  // nome: tamanho ajustado para caber em uma linha
  let tamNome = cfg.tamNome || 152;
  while (tamNome > 70 && (medirTexto(cfg.nome.toUpperCase(), `700 ${tamNome}px ${FONTE.display}`) + cfg.nome.length * tamNome * 0.02) * 1.05 > largura) tamNome -= 4;
  const altNome = Math.round(tamNome * 1.12);
  const jan = el('div', { left: x + 'px', top: cy + 'px', width: largura + 'px', height: altNome + 'px', overflow: 'hidden' }, pai);
  const linhaNome = el('div', { left: '0', top: '0', whiteSpace: 'nowrap', display: 'flex', font: `700 ${tamNome}px/${altNome}px ${FONTE.display}`, letterSpacing: '0.02em', color: COR.marfim }, jan);
  const letrasNome = [];
  for (const ch of cfg.nome.toUpperCase()) {
    const s = document.createElement('span');
    s.textContent = ch === ' ' ? ' ' : ch;
    Object.assign(s.style, { display: 'inline-block', position: 'relative' });
    linhaNome.appendChild(s);
    letrasNome.push(s);
  }
  cy += altNome + 14;

  // regra
  const regra = el('div', { left: x + 'px', top: cy + 'px', width: '260px', height: '3px', background: COR.ouro, transformOrigin: '0 50%' }, pai);
  cy += 3 + 26;

  // período + categoria
  let chipEl = null, chipTxt = null;
  if (cat) {
    const tw = medirTexto(cat.rotulo, `600 ${TAM.chip}px ${FONTE.ui}`) + cat.rotulo.length * TAM.chip * 0.14 + 40;
    const cheio = cat.estilo === 'cheio';
    chipEl = el('div', {
      left: x + 'px', top: cy + 'px', width: Math.ceil(tw) + 'px', height: '46px', borderRadius: '23px',
      background: cheio ? COR.ouro : 'transparent', border: cheio ? 'none' : `2px solid ${COR.ouro}`,
      borderBottom: cat.estilo === 'sublinhado' ? `2px solid ${COR.ouro}` : undefined,
    }, pai);
    if (cat.estilo === 'sublinhado') { chipEl.style.border = 'none'; chipEl.style.borderRadius = '0'; chipEl.style.borderBottom = `3px solid ${COR.ouro}`; }
    chipTxt = el('div', { left: '0', top: '0', width: '100%', height: '100%', textAlign: 'center', lineHeight: '46px', font: `600 ${TAM.chip}px ${FONTE.ui}`, letterSpacing: '0.14em', color: cheio ? COR.tinta : COR.ouro }, chipEl, cat.rotulo);
    cy += 46 + 20;
  }
  let per = null;
  if (cfg.periodo) { per = linhaMascara(pai, x, cy, largura, 52, cfg.periodo, { font: fp, color: COR.marfim }); cy += 62; }

  // descrição (linhas medidas)
  let blocoDesc = null;
  if (cfg.descricao) {
    const linhas = quebrar(cfg.descricao, fd, largura);
    const alt = Math.round(TAM.descricao * 1.36);
    blocoDesc = [];
    linhas.forEach((ln, i) => blocoDesc.push(linhaMascara(pai, x, cy + i * alt, largura, alt, ln, { font: fd, color: COR.marfimSuave })));
    cy += linhas.length * alt + 18;
  }
  const alturaTotal = cy - y;

  // tempos de entrada (s). saida: instante em que tudo desliza para fora (ou null)
  function aplicar(t, tp, saida = null) {
    const sai = saida === null ? 0 : prog(t, saida, saida + 0.45, inCubic);
    const dx = -90 * sai;
    const rev = (j, ini, d = 0.7) => 1 - prog(t, ini, ini + d, outExpo);          // 1 = escondida abaixo da janela
    eb.t.style.transform = `translate(${dx}px, ${rev(0, tp.eyebrow) * 52}px)`;
    letrasNome.forEach((s, i) => { s.style.transform = `translate(${dx}px, ${(1 - prog(t, tp.nome + i * 0.05, tp.nome + i * 0.05 + 0.7, outExpo)) * tamNome * 1.15}px)`; });
    const rg = prog(t, tp.regra, tp.regra + 0.7, outExpo);
    regra.style.transform = `translate(${dx}px, 0) scaleX(${rg})`;
    if (chipEl) {
      const k = prog(t, tp.periodo - 0.1, tp.periodo + 0.5, outCubic);
      chipEl.style.opacity = String(k * (1 - sai));
      chipEl.style.transform = `translate(${dx - 30 * (1 - k)}px, 0)`;
    }
    if (per) per.t.style.transform = `translate(${dx}px, ${rev(0, tp.periodo) * 62}px)`;
    if (blocoDesc) blocoDesc.forEach((l, i) => { l.t.style.transform = `translate(${dx}px, ${rev(0, tp.descricao + i * 0.12, 0.75) * (l.altura + 6)}px)`; });
    // saída: as máscaras sobem junto com o deslocamento lateral
    const fade = String(1 - sai);
    eb.jan.style.opacity = fade; jan.style.opacity = fade; per && (per.jan.style.opacity = fade);
    blocoDesc && blocoDesc.forEach((l) => { l.jan.style.opacity = fade; });
    regra.style.opacity = fade;
  }
  refs.push(eb, jan);
  return { aplicar, altura: alturaTotal, fim: y + alturaTotal };
}

// Linha de procedência (fonte da imagem/dados): discreta, legível, sempre presente depois de entrar.
export function construirRodape(pai, texto, { x, y, largura }) {
  const f = `500 ${TAM.fonte}px ${FONTE.ui}`;
  const linhas = quebrar(texto, f, largura);
  const e = el('div', { left: x + 'px', top: y + 'px', width: largura + 'px', font: `500 ${TAM.fonte}px/${Math.round(TAM.fonte * 1.4)}px ${FONTE.ui}`, color: COR.mudo, whiteSpace: 'pre' }, pai, linhas.join('\n'));
  return { aplicar(t, ini, saida = null) { const k = prog(t, ini, ini + 0.8, smooth) * (saida === null ? 1 : 1 - prog(t, saida, saida + 0.4, smooth)); e.style.opacity = String(k); }, altura: linhas.length * Math.round(TAM.fonte * 1.4) };
}

export { CATEGORIAS, medirTexto, quebrar, TAM };
