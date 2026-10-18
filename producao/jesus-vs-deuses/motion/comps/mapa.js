// Mapa histórico animado: o mapa plano "levanta" em perspectiva (câmera 3D com distância focal), a câmera percorre as
// regiões, rotas são traçadas, locais ganham marcadores em pé e a ficha traz o contexto.
// A projeção é feita em Canvas 2D (engine/projecao.js): função pura do tempo, sem camadas CSS 3D e sem histórico de raster.
// params: { camera:[{f,lon,lat,larg}], tiltIni, tiltFim, fTilt:[f0,f1], regioes:[{nome,lon,lat,f,ate,tam}], locais:[{nome,sub,lon,lat,f}],
//           rotas:[{pontos:[[lon,lat]],f0,f1}], ficha:{...}, rodape, nilo, batidas }
import { linha } from '../engine/tl.js';
import { el, canvas, COR, FONTE } from '../engine/ui.js';
import { prog, outCubic, outExpo, inOutCubic, smooth, aBatida, mola } from '../engine/ease.js';
import { construirFicha, construirRodape } from '../engine/ficha.js';
import { carregarMapa, vista, desenharMapa, camera } from '../engine/mapabase.js';
import { criarCamadaFinal } from '../engine/atmos.js';
import { criarProjecao, desenharPlano } from '../engine/projecao.js';

const W = 1920, H = 1080, CW = 2400, CH = 1400, PERSP = 2300, CY = 640;

function comprimentos(pts) { const c = [0]; for (let i = 1; i < pts.length; i++) c.push(c[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return c; }
function noPercurso(pts, c, k) {
  const alvo = c[c.length - 1] * k; let i = 1; while (i < c.length - 1 && c[i] < alvo) i++;
  const u = c[i] === c[i - 1] ? 0 : (alvo - c[i - 1]) / (c[i] - c[i - 1]);
  return { x: pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * u, y: pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * u, ate: i };
}

export const mapa = {
  async build(palco, spec) {
    const P = spec.params, D = spec.dur, bat = P.batidas || [];
    const dados = await carregarMapa();
    const snap = (x) => aBatida(x, bat, 0.22);
    const raiz = el('div', { left: '0', top: '0', width: W + 'px', height: H + 'px', background: COR.tinta, overflow: 'hidden' }, palco);
    const tela = canvas(W, H, {}, raiz); const gt = tela.getContext('2d');
    const plano = document.createElement('canvas'); plano.width = CW; plano.height = CH; const gp = plano.getContext('2d');

    const fcfg = P.fichaCfg || { x: 90, y: 70, largura: 760, tamNome: 92 };
    const tp = { eyebrow: snap(0.3), nome: snap(0.5), regra: 0.9, periodo: 1.1, descricao: 1.4, fonte: 1.9 };
    const ficha = construirFicha(raiz, P.ficha, fcfg);
    const zona = { x0: fcfg.x - 24, x1: fcfg.x + fcfg.largura + 24, y0: fcfg.y - 24, y1: ficha.fim + 24 };      // área do texto
    const rodape = P.rodape ? construirRodape(raiz, P.rodape, { x: fcfg.x, y: 960, largura: 800 }) : null;
    const final = criarCamadaFinal(raiz, { semente: spec.seed, poeira: { n: 40, brilho: 0.4 }, vinheta: 0.55, grao: 0.04 });
    const saida = D - 0.45;
    const eventos = [{ t: tp.nome, tipo: 'revelar' }];
    (P.locais || []).forEach((L) => eventos.push({ t: snap(L.f * D), tipo: 'ping' }));
    (P.rotas || []).forEach((r) => eventos.push({ t: snap(r.f0 * D), tipo: 'rota' }));

    const est = { tilt: P.tiltIni ?? 0 };
    const [fa, fb] = P.fTilt || [0.0, 0.2];
    const tl = linha((tl) => { tl.fromTo(est, { tilt: P.tiltIni ?? 0 }, { tilt: P.tiltFim ?? 44, duration: Math.max(0.6, (fb - fa) * D), ease: 'power3.inOut' }, fa * D); });

    return {
      eventos,
      seek(t) {
        tl.ir(t);
        const f = t / D, tilt = est.tilt;
        const cam = camera(P.camera, f, inOutCubic);
        const v = vista(cam.lon, cam.lat, cam.larg, CW, CH);
        const sai = 1 - prog(t, saida, saida + 0.4, smooth);

        // 1) o mapa plano (costas, rios, regiões, rotas e marcas no chão)
        desenharMapa(gp, dados, v, { realceNilo: P.nilo ? 1 : 0 });
        gp.save();
        gp.textAlign = 'center'; gp.textBaseline = 'middle';
        for (const R of P.regioes || []) {
          const t0 = snap(R.f * D);
          const k = prog(t, t0, t0 + 0.8, outCubic) * (R.ate ? 1 - prog(t, R.ate * D, R.ate * D + 0.5, smooth) : 1);
          if (k <= 0) continue;
          const [x, y] = v.proj(R.lon, R.lat); const tam = R.tam || 92;
          gp.font = `600 ${tam}px ${FONTE.display}`; gp.letterSpacing = `${Math.round(tam * 0.28)}px`; gp.fillStyle = `rgba(239,230,210,${0.42 * k})`;
          gp.fillText(R.nome.toUpperCase(), x, y);
        }
        gp.letterSpacing = '0px'; gp.textAlign = 'left';
        for (const r of P.rotas || []) {
          const pts = r.pontos.map(([lo, la]) => v.proj(lo, la)); const c = comprimentos(pts);
          const k = prog(t, snap(r.f0 * D), snap(r.f1 * D), inOutCubic); if (k <= 0) continue;
          gp.lineCap = 'round'; gp.lineJoin = 'round';
          gp.setLineDash([2, 12]); gp.strokeStyle = 'rgba(232,190,105,0.25)'; gp.lineWidth = 3; gp.beginPath(); pts.forEach((p, i) => (i ? gp.lineTo(p[0], p[1]) : gp.moveTo(p[0], p[1]))); gp.stroke(); gp.setLineDash([]);
          const pos = noPercurso(pts, c, Math.max(1e-4, k));
          gp.strokeStyle = COR.ouro; gp.lineWidth = 7; gp.beginPath(); gp.moveTo(pts[0][0], pts[0][1]);
          for (let i = 1; i < pos.ate; i++) gp.lineTo(pts[i][0], pts[i][1]);
          gp.lineTo(pos.x, pos.y); gp.stroke();
          if (k < 0.999) { gp.fillStyle = 'rgba(232,190,105,0.3)'; gp.beginPath(); gp.arc(pos.x, pos.y, 26 + 6 * Math.sin(t * 6), 0, 6.283); gp.fill(); gp.fillStyle = COR.marfim; gp.beginPath(); gp.arc(pos.x, pos.y, 14, 0, 6.283); gp.fill(); }
        }
        const marcas = (P.locais || []).map((L) => ({ L, xy: v.proj(L.lon, L.lat), t0: snap(L.f * D) }));
        for (const m of marcas) {
          const k = prog(t, m.t0, m.t0 + 0.55, outExpo); if (k <= 0) continue;
          const ring = (Math.max(0, t - m.t0 - 0.5) * 0.8) % 1;
          if (t > m.t0 + 0.5) { gp.strokeStyle = `rgba(232,190,105,${0.8 * (1 - ring)})`; gp.lineWidth = 4; gp.beginPath(); gp.arc(m.xy[0], m.xy[1], 14 + 70 * ring, 0, 6.283); gp.stroke(); }
          gp.fillStyle = COR.ouro; gp.strokeStyle = COR.tinta; gp.lineWidth = 4; gp.beginPath(); gp.arc(m.xy[0], m.xy[1], 13 * mola(prog(t, m.t0, m.t0 + 0.7, (u) => u), 5, 8), 0, 6.283); gp.fill(); gp.stroke();
        }

        gp.restore();
        // 2) projeta o plano em perspectiva (rotação em X) sobre a tela
        gt.save(); gt.setTransform(1, 0, 0, 1, 0, 0);
        gt.fillStyle = COR.tinta; gt.fillRect(0, 0, W, H);
        const geo = { tilt, persp: PERSP, cx: W / 2, cy: CY };
        desenharPlano(gt, plano, geo, 2);
        const proj = criarProjecao(geo);
        // neblina do horizonte (a borda distante do plano desaparece na escuridão)
        const borda = Math.max(0, proj(0, -CH / 2).y), fim = Math.min(H, borda + 300);      // a névoa começa na borda distante do plano
        const fog = gt.createLinearGradient(0, 0, 0, fim); fog.addColorStop(0, COR.tinta); fog.addColorStop(Math.min(0.98, (borda + 4) / fim), COR.tinta); fog.addColorStop(1, 'rgba(7,8,12,0)');
        gt.globalAlpha = prog(t, 0, 1.2, smooth); gt.fillStyle = fog; gt.fillRect(0, 0, W, fim); gt.globalAlpha = 1;
        // faixa escura sob o texto
        const esc = gt.createLinearGradient(0, 0, 980, 0); esc.addColorStop(0, 'rgba(7,8,12,0.90)'); esc.addColorStop(0.45, 'rgba(7,8,12,0.55)'); esc.addColorStop(1, 'rgba(7,8,12,0)');
        gt.fillStyle = esc; gt.fillRect(0, 0, 980, H);

        // 3) marcadores em pé (haste + cartão), desenhados já na tela para ficarem sempre de frente para a câmera
        for (const m of marcas) {
          const k = prog(t, m.t0, m.t0 + 0.55, outExpo) * sai; if (k <= 0) continue;
          const p = proj(m.xy[0] - CW / 2, m.xy[1] - CH / 2);
          if (p.x < -200 || p.x > W + 300 || p.y < -50 || p.y > H + 200) continue;
          const sc = Math.max(0.7, Math.min(1.35, p.k));
          const alt = 130 * sc * k;
          const rev = prog(t, m.t0 + 0.12, m.t0 + 0.75, outExpo);
          // cartão sobre a ficha (título/texto)? some suavemente conforme a sobreposição (o ponto no chão continua)
          gt.font = `600 ${Math.round(40 * sc)}px ${FONTE.ui}`;
          const lx0 = p.x + 8 * sc, lx1 = lx0 + 36 * sc + gt.measureText(m.L.nome.toUpperCase()).width * 1.08, ly0 = p.y - alt - 70 * sc, ly1 = ly0 + 110 * sc;
          const ov = Math.min(zona.x1 - lx0, lx1 - zona.x0, zona.y1 - ly0, ly1 - zona.y0);
          const borda = Math.min(1, Math.max(0, (ly0 - 10) / 50), Math.max(0, (W - 10 - lx1) / 60));            // nem cortado pela borda da tela
          const vis = (1 - smooth(Math.min(1, Math.max(0, ov / 60)))) * smooth(borda);
          if (vis <= 0) continue;
          gt.globalAlpha = vis;
          gt.strokeStyle = COR.ouro; gt.lineWidth = 3 * sc; gt.beginPath(); gt.moveTo(p.x, p.y); gt.lineTo(p.x, p.y - alt); gt.stroke();
          gt.save(); gt.beginPath(); gt.rect(p.x + 8 * sc, p.y - alt - 70 * sc, 760 * sc * rev, 110 * sc); gt.clip();
          gt.textBaseline = 'alphabetic'; gt.shadowColor = 'rgba(0,0,0,0.9)'; gt.shadowBlur = 12;
          gt.font = `600 ${Math.round(40 * sc)}px ${FONTE.ui}`; gt.letterSpacing = `${Math.round(2.4 * sc)}px`; gt.fillStyle = COR.marfim; gt.fillText(m.L.nome.toUpperCase(), p.x + 18 * sc, p.y - alt - 22 * sc);
          if (m.L.sub) { gt.letterSpacing = '0px'; gt.font = `500 ${Math.round(28 * sc)}px ${FONTE.ui}`; gt.fillStyle = COR.ouro; gt.fillText(m.L.sub, p.x + 18 * sc, p.y - alt + 14 * sc); }
          gt.restore(); gt.letterSpacing = '0px'; gt.shadowBlur = 0; gt.globalAlpha = 1;
        }
        gt.restore();
        ficha.aplicar(t, tp, saida);
        rodape && rodape.aplicar(t, tp.fonte, saida);
        final.desenhar(t, 0.8);
      },
    };
  },
};
