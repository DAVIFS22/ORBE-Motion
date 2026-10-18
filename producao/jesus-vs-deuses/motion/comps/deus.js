// Apresentação de uma figura da tradição religiosa/mitológica: placa ilustrada com profundidade 3D (perspectiva CSS real),
// ficha informativa em hierarquia tipográfica, mapa de localização e procedência da imagem.
// params: { imagem, fundoPlaca: 'papiro'|'branco'|'escuro', variante: 'A'|'B', fantasma, ficha:{eyebrow,nome,periodo,categoria,descricao,descricaoCurta},
//           rodape, local:{nome,lon,lat,larg0,larg1,lon0,lat0}, batidas:[s] }
import { linha } from '../engine/tl.js';
import { el, canvas, pose, carregarImagem, COR, FONTE } from '../engine/ui.js';
import { prog, outCubic, outExpo, inOutCubic, smooth, mola, aBatida } from '../engine/ease.js';
import { construirFicha, construirRodape, medirTexto } from '../engine/ficha.js';
import { carregarMapa, vista, desenharMapa, merc } from '../engine/mapabase.js';
import { criarCamadaFinal } from '../engine/atmos.js';

const W = 1920, H = 1080;
const PAPEL = { papiro: '#c7a566', branco: '#d9c9a3', escuro: '#0d0e12' };

export const deus = {
  async build(palco, spec) {
    const P = spec.params, D = spec.dur, bat = P.batidas || [];
    const img = await carregarImagem(P.imagem);
    const mapa = await carregarMapa();
    const A = (P.variante || 'A') === 'A';
    const esc = Math.min(1, Math.max(0.55, (D - 0.9) / 3.4));
    const snap = (x) => aBatida(x, bat, 0.22);
    const tp = { eyebrow: snap(0.32 * esc), nome: snap(0.5 * esc), regra: 0.95 * esc, periodo: 1.12 * esc, descricao: 1.45 * esc, rodape: 1.9 * esc, local: 1.25 * esc };
    const saida = D - 0.5;
    const eventos = [{ t: 0, tipo: 'entrada' }, { t: tp.nome, tipo: 'revelar' }, { t: tp.local + 0.55, tipo: 'ping' }];

    const raiz = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', background: COR.tinta, overflow: 'hidden' }, palco);

    // fundo: a própria imagem, muito desfocada e escurecida, ocupa a cena inteira (uma só vez, fora do loop de quadros)
    const blur = document.createElement('canvas'); blur.width = 480; blur.height = 270;
    { const g = blur.getContext('2d'); g.filter = 'blur(14px) saturate(1.1)'; const k = Math.max(480 / img.naturalWidth, 270 / img.naturalHeight) * 1.1;
      g.drawImage(img, (480 - img.naturalWidth * k) / 2, (270 - img.naturalHeight * k) / 2, img.naturalWidth * k, img.naturalHeight * k); }
    const fundo = canvas(W, H, {}, raiz);
    const gf = fundo.getContext('2d');

    // geometria da placa
    const maxW = 620, maxH = 900; const k0 = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight, 2.6);
    const pw = Math.round(img.naturalWidth * k0), ph = Math.round(img.naturalHeight * k0);
    const cxP = A ? 1400 : 520, cyP = 520;
    const xTxt = A ? 110 : 1010, lTxt = 800;

    // fantasma tipográfico (profundidade): palavra enorme atrás da placa
    const fant = el('div', { left: (A ? 760 : 60) + 'px', top: '260px', font: `700 330px/1 ${FONTE.display}`, color: 'transparent', whiteSpace: 'nowrap', webkitTextStroke: '2px rgba(232,190,105,0.13)' }, raiz, (P.fantasma || '').toUpperCase());
    fant.style.webkitTextStroke = '2px rgba(232,190,105,0.13)';

    // placa em perspectiva
    const cena3d = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', perspective: '1500px', perspectiveOrigin: `${(cxP / W) * 100}% 50%` }, raiz);
    const placa = el('div', { left: (cxP - pw / 2) + 'px', top: (cyP - ph / 2) + 'px', width: pw + 'px', height: ph + 'px', transformStyle: 'preserve-3d' }, cena3d);
    el('div', { left: '0', top: '0', width: pw + 'px', height: ph + 'px', boxShadow: '0 60px 140px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,235,190,0.10)', borderRadius: '5px' }, placa);
    const quadro = el('div', { left: '0', top: '0', width: pw + 'px', height: ph + 'px', overflow: 'hidden', borderRadius: '5px', background: PAPEL[P.fundoPlaca || 'papiro'], isolation: 'isolate' }, placa);
    // a ilustração vai para um canvas de resolução fixa (uma vez): numa <img> dentro da camada 3D o Chromium escolhe a escala de
    // rasterização pelo primeiro quadro pintado, e quadros iguais saíam com ±1 de diferença conforme a ordem de captura
    const dprP = window.devicePixelRatio || 1;
    const im = canvas(Math.round(pw * dprP), Math.round(ph * dprP), { width: pw + 'px', height: ph + 'px', mixBlendMode: P.fundoPlaca === 'branco' ? 'multiply' : 'normal' }, quadro);
    { const gi = im.getContext('2d'); gi.imageSmoothingEnabled = true; gi.imageSmoothingQuality = 'high';
      const kc = Math.max(im.width / img.naturalWidth, im.height / img.naturalHeight);                 // object-fit: cover
      gi.drawImage(img, (im.width - img.naturalWidth * kc) / 2, (im.height - img.naturalHeight * kc) / 2, img.naturalWidth * kc, img.naturalHeight * kc); }
    const brilho = el('div', { left: '-60%', top: '0', width: '80%', height: '100%', background: 'linear-gradient(105deg, rgba(255,240,205,0) 20%, rgba(255,240,205,0.30) 50%, rgba(255,240,205,0) 80%)', mixBlendMode: 'soft-light' }, quadro);

    // ficha (texto) e rodapé de procedência
    const descr = D < 4.6 && P.ficha.descricaoCurta ? P.ficha.descricaoCurta : P.ficha.descricao;
    const ficha = construirFicha(raiz, { ...P.ficha, descricao: descr }, { x: xTxt, y: 100, largura: lTxt });
    const rodape = P.rodape ? construirRodape(raiz, P.rodape, { x: xTxt, y: 960, largura: lTxt }) : null;

    // atributos (fichas sincronizadas com palavras da narração; os tempos vêm resolvidos do alinhamento)
    const attrs = (P.atributos || []).map((a, i) => ({ ...a, t: a.t ?? (tp.descricao + i * 0.9) }));
    const chips = []; let xc = 0;
    attrs.forEach((a) => {
      const tw = Math.ceil(medirTexto(a.texto.toUpperCase(), `600 34px ${FONTE.ui}`) + a.texto.length * 34 * 0.1 + 56);
      const c = el('div', { left: (xTxt + xc) + 'px', top: (ficha.fim + 6) + 'px', width: tw + 'px', height: '64px', borderRadius: '32px', border: `2px solid ${COR.ouro}`, overflow: 'hidden' }, raiz);
      const f = el('div', { left: '0', top: '0', width: '100%', height: '100%', background: COR.ouro }, c);
      const tx = el('div', { left: '0', top: '0', width: '100%', height: '100%', textAlign: 'center', lineHeight: '60px', font: `600 34px ${FONTE.ui}`, letterSpacing: '0.1em' }, c, a.texto.toUpperCase());
      chips.push({ a, c, f, tx }); xc += tw + 16;
    });
    const yChips = attrs.length ? ficha.fim + 6 + 64 + 18 : ficha.fim;
    for (const a of attrs) eventos.push({ t: a.t, tipo: 'ping' });

    // mapa de localização (inset)
    const L = P.local;
    const iw = 700, ih = 232, ix = xTxt, iy = Math.min(yChips + 22, 948 - 18 - ih);
    const insetCv = canvas(iw, ih, { left: ix + 'px', top: iy + 'px', borderRadius: '8px' }, raiz);
    const gi = insetCv.getContext('2d');
    const pinEl = null;

    const final = criarCamadaFinal(raiz, { semente: spec.seed, poeira: { n: 70, brilho: 0.55 }, vinheta: 0.6, grao: 0.04 });

    // dolly/rotação da placa por GSAP (tempo absoluto). Estado em objeto simples; aplicado a cada seek.
    const est = { z: 0, ry: 0, rx: 0, y: 0, o: 0, br: -60, zoom: 1 };
    const sgn = A ? -1 : 1;
    const tl = linha((tl) => {
      tl.fromTo(est, { z: -520, ry: sgn * 30, rx: 5, o: 0 }, { z: 0, ry: sgn * 7, rx: 1.5, o: 1, duration: 1.35 * Math.min(1, esc + 0.2), ease: 'expo.out' }, 0);
      tl.fromTo(est, { zoom: 1 }, { zoom: 1.06, duration: D, ease: 'none' }, 0);
      tl.fromTo(est, { br: -60 }, { br: 170, duration: 1.5, ease: 'power2.inOut' }, tp.nome + 0.2);
    });

    return {
      eventos,
      seek(t) {
        tl.ir(t);
        const f = t / D;
        // saída: a placa recua e escurece nos últimos 0,5 s
        const sai = prog(t, saida, D, smooth);
        // fundo
        gf.save();
        gf.fillStyle = COR.tinta; gf.fillRect(0, 0, W, H);
        const kk = Math.max(W / 480, H / 270) * (1.12 + 0.07 * f);
        gf.globalAlpha = 0.62; gf.drawImage(blur, W / 2 - (480 * kk) / 2 + (A ? -25 : 25) * f, H / 2 - (270 * kk) / 2, 480 * kk, 270 * kk); gf.globalAlpha = 1;
        gf.fillStyle = 'rgba(7,8,12,0.58)'; gf.fillRect(0, 0, W, H);
        const rg = gf.createRadialGradient(cxP, cyP, 40, cxP, cyP, 760);
        rg.addColorStop(0, `rgba(232,190,105,${0.20 + 0.03 * Math.sin(t * 1.4)})`); rg.addColorStop(1, 'rgba(232,190,105,0)');
        gf.fillStyle = rg; gf.fillRect(0, 0, W, H);
        gf.restore();
        // pose da placa
        const oscil = 1.6 * Math.sin(t * 0.7);
        pose(placa, { z: est.z + 60 * f - 80 * sai, ry: est.ry + oscil * (A ? -1 : 1), rx: est.rx, y: -8 * Math.sin(t * 0.55) , o: est.o * (1 - 0.65 * sai), s: 1 });
        brilho.style.transform = `translate(${est.br}%, 0)`;
        // fantasma desliza em paralaxe contrária
        fant.style.transform = `translate(${(A ? 1 : -1) * (-40 * f)}px, 0)`; fant.style.opacity = String(prog(t, 0.2, 1.4, smooth) * (1 - sai));
        // ficha
        ficha.aplicar(t, tp, saida);
        rodape && rodape.aplicar(t, tp.rodape, saida);
        chips.forEach((ch) => {
          const k = prog(t, ch.a.t - 0.2, ch.a.t + 0.35, outExpo) * (1 - prog(t, saida, saida + 0.4, smooth));
          const ativo = 1 - prog(t, ch.a.t + 0.15, ch.a.t + 1.1, smooth);
          ch.c.style.opacity = String(k); ch.c.style.transform = `translate(${-40 * (1 - k)}px, 0) scale(${0.92 + 0.08 * k})`;
          ch.f.style.opacity = String(ativo); ch.tx.style.color = ativo > 0.5 ? COR.tinta : COR.marfim;
        });
        // inset do mapa: revela por máscara e aproxima a câmera até o local
        const kr = prog(t, tp.local, tp.local + 0.7, outExpo) * (1 - prog(t, saida, saida + 0.4, smooth));
        insetCv.style.clipPath = `inset(0 ${(1 - kr) * 100}% 0 0 round 8px)`;
        insetCv.style.opacity = String(Math.min(1, kr * 3));
        const kz = prog(t, tp.local - 0.2, tp.local + 1.7, inOutCubic);
        const lar = Math.exp(Math.log(L.larg0) + (Math.log(L.larg1) - Math.log(L.larg0)) * kz);
        const lon = L.lon0 + (L.lon - L.lon0) * kz, lat = L.lat0 + (L.lat - L.lat0) * kz;
        const v = vista(lon, lat, lar, iw, ih);
        desenharMapa(gi, mapa, v, { realceNilo: L.nilo ? 1 : 0 });
        gi.save();
        const [px, py] = v.proj(L.lon, L.lat);
        const queda = 1 - mola(prog(t, tp.local + 0.45, tp.local + 1.15, (x) => x), 5, 8);
        const ring = (Math.max(0, t - (tp.local + 0.95)) * 0.9) % 1;
        if (t > tp.local + 0.95) { gi.strokeStyle = `rgba(232,190,105,${0.7 * (1 - ring)})`; gi.lineWidth = 2.5; gi.beginPath(); gi.arc(px, py, 10 + 38 * ring, 0, 6.283); gi.stroke(); }
        gi.fillStyle = COR.ouro; gi.beginPath(); gi.arc(px, py - 70 * Math.max(0, queda), 9, 0, 6.283); gi.fill();
        gi.strokeStyle = COR.tinta; gi.lineWidth = 3; gi.stroke();
        if (L.regiao) {                                                  // nome da região (orientação), em exibição, discreto
          const [rx, ry] = v.proj(L.regiao.lon, L.regiao.lat);
          gi.font = `600 46px ${FONTE.display}`; gi.textBaseline = 'middle'; gi.textAlign = 'center'; gi.fillStyle = `rgba(239,230,210,${0.38 * (1 - kz)})`;
          gi.fillText(L.regiao.nome.toUpperCase().split('').join('\u200a'), rx, ry); gi.textAlign = 'left';
        }
        gi.font = `600 32px ${FONTE.ui}`; gi.textBaseline = 'middle';
        const lx = px + 24 > iw - 220 ? px - 24 - gi.measureText(L.nome).width : px + 24;
        gi.fillStyle = 'rgba(7,8,12,0.78)'; gi.fillText(L.nome, lx + 1.5, py - 70 * Math.max(0, queda) + 1.5);
        gi.fillStyle = COR.marfim; gi.fillText(L.nome, lx, py - 70 * Math.max(0, queda));
        gi.restore();
        final.desenhar(t, 1 - 0.7 * sai);
      },
    };
  },
};
