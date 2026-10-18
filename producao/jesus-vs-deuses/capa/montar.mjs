// Capa (thumbnail) do documentário: compõe capa.html sobre a placa 3D e grava PNG 1920x1080.
// 1) placa:  cd ../motion && node render.mjs --spec ../capa/placa-spec.json --quadros 1.0 --png-dir ../capa/png  (copie png/capa_t001000.png para capa/placa.png)
// 2) capa:   node montar.mjs capa.png    (gera também capa-1280x720.jpg com: python3 -c "from PIL import Image; ...")
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '../motion/node_modules/playwright-core/index.mjs';
const aqui = path.dirname(fileURLToPath(import.meta.url));
const saida = path.resolve(process.argv[2] || 'capa.png');
const b = await chromium.launch({ args: ['--force-color-profile=srgb', '--font-render-hinting=none', '--allow-file-access-from-files'] });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.goto('file://' + path.join(aqui, 'capa.html'));
await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.decode())); });
await p.locator('#c').screenshot({ path: saida });
await b.close();
console.log('ok', saida);
