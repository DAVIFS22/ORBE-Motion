// Testes do contrato de renderização determinística.
//  1) Lint: nenhum Math.random/setTimeout/rAF/Date/performance.now/transição CSS no código das composições.
//  2) Determinismo: cada composição produz exatamente os mesmos pixels para o mesmo instante, em ordem direta, reversa e a frio.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, '..');
const FIX = path.join(AQUI, 'fixtures', 'placa.png');

const PROIBIDOS = [
  [/Math\.random\s*\(/, 'Math.random'], [/\bsetTimeout\s*\(/, 'setTimeout'], [/\bsetInterval\s*\(/, 'setInterval'],
  [/requestAnimationFrame/, 'requestAnimationFrame'], [/\bDate\.now\s*\(/, 'Date.now'], [/new Date\s*\(/, 'new Date'],
  [/performance\.now\s*\(/, 'performance.now'], [/\btransition\s*:/, 'transição CSS'], [/\banimation\s*:/, 'animação CSS'],
  [/@keyframes/, '@keyframes'], [/\.animate\s*\(/, 'Web Animations API'], [/setAnimationLoop/, 'setAnimationLoop'],
];

function semComentarios(src) { return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1'); }

test('código das composições respeita o contrato (sem aleatório, timers, rAF ou transições CSS)', () => {
  const arqs = [];
  for (const d of ['engine', 'comps', 'audio']) {
    const p = path.join(RAIZ, d); if (!fs.existsSync(p)) continue;
    for (const f of fs.readdirSync(p)) if (f.endsWith('.js') || f.endsWith('.mjs')) arqs.push(path.join(p, f));
  }
  arqs.push(path.join(RAIZ, 'film.html'));
  assert.ok(arqs.length > 5);
  for (const f of arqs) {
    const src = semComentarios(fs.readFileSync(f, 'utf-8'));
    for (const [re, nome] of PROIBIDOS) assert.ok(!re.test(src), `${path.relative(RAIZ, f)} usa ${nome}`);
  }
});

function renderQuadros(comp, params, dur, tempos, { embaralhar = false } = {}) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'motion-'));
  const spec = { largura: 960, altura: 540, fps: 30, assets: { placa: FIX }, clipes: [{ id: comp, comp, dur, seed: 5, params, saida: path.join(tmp, 'x.mp4') }] };
  fs.writeFileSync(path.join(tmp, 'spec.json'), JSON.stringify(spec));
  const args = [path.join(RAIZ, 'render.mjs'), '--spec', path.join(tmp, 'spec.json'), '--quadros', tempos.join(','), '--png-dir', path.join(tmp, 'png'), ...(embaralhar ? ['--embaralhar'] : [])];
  const r = spawnSync('node', args, { encoding: 'utf-8' });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const h = {};
  for (const f of fs.readdirSync(path.join(tmp, 'png'))) h[Number(f.match(/_t(\d+)\.png$/)[1]) / 1000] = crypto.createHash('sha256').update(fs.readFileSync(path.join(tmp, 'png', f))).digest('hex');
  fs.rmSync(tmp, { recursive: true, force: true });
  return h;
}

const CASOS = {
  teste: { dur: 4, params: {} },
  deus: { dur: 5.5, params: { imagem: '/ativo/placa', fundoPlaca: 'papiro', variante: 'A', fantasma: 'Egito', batidas: [0.5, 1, 1.5],
    ficha: { eyebrow: 'Egito antigo · teste', nome: 'Teste', periodo: 'c. 2400 a.C.', categoria: 'mitologico', descricao: 'Descrição de teste para o contrato.' },
    rodape: 'Imagem de teste.', local: { nome: 'Abidos', lon: 31.9, lat: 26.2, lon0: 24, lat0: 34, larg0: 50, larg1: 9, regiao: { nome: 'Egito', lon: 30, lat: 27 } } } },
  mapa: { dur: 6, params: { camera: [{ f: 0, lon: 20, lat: 40, larg: 80 }, { f: 1, lon: 30, lat: 30, larg: 20 }], tiltIni: 0, tiltFim: 42, fTilt: [0, 0.3],
    regioes: [{ nome: 'Egito', lon: 29, lat: 25, f: 0.2 }], locais: [{ nome: 'Mênfis', sub: 'Egito antigo', lon: 31.25, lat: 29.85, f: 0.3 }],
    rotas: [{ pontos: [[31.25, 29.85], [23.7, 38], [17.6, 59.9]], f0: 0.4, f1: 0.9 }], ficha: { eyebrow: 'Mapa', nome: 'Teste', periodo: 'Teste', categoria: 'historico' } } },
  periodo: { dur: 6, params: { janela: [{ f: 0, a: -3500, b: 1500 }, { f: 1, a: -100, b: 100 }], periodos: [{ nome: 'Egito antigo', ini: -3100, fim: -30, lane: 0, f: 0.1 }],
    eventos: [{ nome: 'Evento', sub: 'x', ano: 30, aprox: true, f: 0.5, nivel: 0, foco: true }], ficha: { eyebrow: 'Linha do tempo', nome: 'Teste', periodo: 'Teste', categoria: 'historico' } } },
  frase: { dur: 5.5, params: { imagem: '/ativo/placa', lado: 'esq', eyebrow: 'João 1:1', aspas: true, nota: 'Citação de teste',
    linhas: [[{ txt: 'No', t: 0.5 }, { txt: 'princípio', t: 0.8 }], [{ txt: 'era', t: 1.6 }, { txt: 'o', t: 1.8 }, { txt: 'Verbo', t: 2.0, enfase: true }]],
    camera: { corte: { t: 1.6, s: 1.28, x: -110, y: 24 } } } },
  pontos: { dur: 5.5, params: { imagem: '/ativo/placa', ativo: 3, t_ativo: 1.6, itens: [{ rotulo: 'Um', ref: 'A 1' }, { rotulo: 'Dois', ref: 'B 2' }, { rotulo: 'Três', ref: 'C 3' }, { rotulo: 'Quatro', ref: 'D 4' }, { rotulo: 'Cinco', ref: 'E 5' }] } },
};

// cenas Three.js/WebGL (SwiftShader): menos instantes por caso, pois cada carga leva alguns segundos
const FICHA3D = { eyebrow: 'Teste · cena 3D', nome: 'Teste', periodo: 'Teste', categoria: 'historico', descricao: '' };
for (const [comp, dur] of [['cena3d_abertura', 4.4], ['cena3d_egito', 4.2], ['cena3d_grecia', 5.8], ['cena3d_fiorde', 9.9], ['cena3d_judeia', 3.2]]) CASOS[comp] = { dur, params: { ficha: FICHA3D, rodape: 'Reconstrução artística de teste.', ...(comp === 'cena3d_abertura' ? { hud: { desligado: true } } : {}) }, tres: true };
// cenas novas, uma vista cada (a do Gólgota com anotação híbrida e só o rodapé)
CASOS.cena3d_golgota = { dur: 6, tres: true, params: { vista: 'distante', ficha: FICHA3D, rodape: 'Reconstrução artística de teste.', hud: { desligado: true, rodape: true },
  anotacoes: [{ pos: [30, 14.5, -336], texto: 'Muralha', sub: 'teste', t0: 1.0, t1: 5.5 }] } };
CASOS.cena3d_tumulo = { dur: 5, tres: true, params: { vista: 'interior', ficha: FICHA3D, rodape: 'Reconstrução artística de teste.' } };
CASOS.cena3d_galileia = { dur: 6, tres: true, params: { vista: 'lago', ficha: FICHA3D, rodape: 'Paisagem artística de teste.' } };
CASOS.cena3d_escritos = { dur: 5, tres: true, params: { vista: 'mesa', ficha: FICHA3D, rodape: 'Composição artística de teste.', hud: { desligado: true } } };

for (const [comp, { dur, params, tres }] of Object.entries(CASOS)) {
  test(`determinismo de "${comp}": mesma imagem em ordem direta, reversa e a frio`, () => {
    const ts = tres ? [0.25, dur * 0.5, dur * 0.95] : [0.2, dur * 0.12, dur * 0.3, dur * 0.55, dur * 0.8, dur * 0.97];
    const direta = renderQuadros(comp, params, dur, ts);
    const reversa = renderQuadros(comp, params, dur, [...ts].reverse());
    const embaralhada = renderQuadros(comp, params, dur, tres ? [ts[1], ts[0], ts[2], ts[1]] : [ts[2], ts[0], ts[4], ts[1], ts[5], ts[3], ts[2]], { embaralhar: true });
    for (const t of ts) {
      assert.equal(reversa[t], direta[t], `${comp}: t=${t} difere em ordem reversa`);
      assert.equal(embaralhada[t], direta[t], `${comp}: t=${t} difere em ordem embaralhada`);
    }
    for (const t of ts) {                                         // cada quadro sozinho, em página nova (nenhum quadro anterior)
      const frio = renderQuadros(comp, params, dur, [t]);
      assert.equal(frio[t], direta[t], `${comp}: quadro a frio em t=${t} difere do quadro em sequência`);
    }
  });
}
