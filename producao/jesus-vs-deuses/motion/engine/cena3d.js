// Infraestrutura das cenas Three.js: renderizador, céu procedural, iluminação por imagem (IBL), feixes de luz, poeira em
// suspensão, trilhos de câmera por spline e tremor de câmera. TUDO é função do tempo: nada acumula entre quadros.
import * as THREE from 'three';
import { rngFor, hash32 } from './rng.js';
import { clamp01 } from './ease.js';

// ------------------------------------------------------------------------------------ renderizador ---
// O layout é sempre 1920×1080 px CSS; a resolução real do buffer vem do devicePixelRatio (prévias renderizam menos pixels).
// window.RENDER3D (opcional, definido pelo render.mjs): { escala, msaa } — resolução interna do 3D relativa à saída e MSAA ligado/desligado.
export function criarRenderizador(palco, { exposicao = 1.0, sombras = true, tipoSombra = THREE.PCFSoftShadowMap } = {}) {
  const cfg = window.RENDER3D || {};
  const pr = (window.devicePixelRatio || 1) * (cfg.escala ?? 1);
  const antialias = cfg.msaa ?? (window.devicePixelRatio || 1) >= 1;                                  // prévias (escala < 1) dispensam o MSAA
  const cv = document.createElement('canvas');
  cv.style.cssText = 'position:absolute;left:0;top:0;width:1920px;height:1080px;display:none';        // o canvas WebGL não é exibido: ver `copiar`
  palco.appendChild(cv);
  const r = new THREE.WebGLRenderer({ canvas: cv, antialias, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  r.setPixelRatio(pr);
  r.setSize(1920, 1080, false);
  r.outputColorSpace = THREE.SRGBColorSpace;
  r.toneMapping = THREE.ACESFilmicToneMapping;
  r.toneMappingExposure = exposicao;
  r.shadowMap.enabled = sombras; r.shadowMap.type = tipoSombra;
  // Espelho 2D: depois de renderizar, gl.finish() + readPixels bloqueiam até a GPU (SwiftShader) concluir o quadro e só então o buffer é
  // copiado para um canvas 2D. Assim a captura nunca pega um quadro anterior ainda não apresentado, mesmo com a máquina sob carga.
  const espelho = document.createElement('canvas');
  const dpr = window.devicePixelRatio || 1;
  espelho.width = Math.round(1920 * dpr); espelho.height = Math.round(1080 * dpr);                    // sempre na resolução de saída
  espelho.style.cssText = 'position:absolute;left:0;top:0;width:1920px;height:1080px';
  palco.appendChild(espelho);
  const g = espelho.getContext('2d', { alpha: false });
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  const gl = r.getContext(), px = new Uint8Array(4);
  const copiar = () => {
    gl.finish(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);     // leitura síncrona: bloqueia até a GPU (SwiftShader) terminar o quadro
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'copy';
    g.drawImage(cv, 0, 0, espelho.width, espelho.height); g.restore();
  };
  return { r, cv, copiar };
}

// ------------------------------------------------------------------------------------------- céu ---
const CEU_VS = `varying vec3 vDir; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vDir = w.xyz - cameraPosition; gl_Position = projectionMatrix * viewMatrix * w; }`;
const CEU_FS = `
varying vec3 vDir;
uniform vec3 cHor, cMeio, cZen, cBaixo, cSol, cNuvem, cNuvemSombra;
uniform vec3 sunDir; uniform float expo, brilho, nuvens, uT, estrelas, cobertura, via, disco;
float h21(vec2 p){ p = fract(p*vec2(123.34,456.21)); p += dot(p,p+45.32); return fract(p.x*p.y); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
float fbm(vec2 p){ float a=.5, s=0.; for(int i=0;i<5;i++){ s+=a*vn(p); p=p*2.03+vec2(7.1,3.7); a*=.5; } return s; }
void main(){
  vec3 d = normalize(vDir);
  float h = clamp(d.y, 0., 1.);
  vec3 col = mix(mix(cHor, cMeio, smoothstep(0.0, 0.28, pow(h, expo))), cZen, smoothstep(0.30, 1.0, pow(h, expo)));
  if (d.y < 0.) col = mix(cHor, cBaixo, clamp(-d.y*5., 0., 1.));
  vec3 sd = normalize(sunDir);
  float s = max(dot(d, sd), 0.);
  vec3 glow = cSol * (pow(s, 6.)*0.30 + pow(s, 48.)*0.55) * brilho + cSol * pow(s, 900.) * 6.0 * brilho;
  if (nuvens > 0. && d.y > 0.015) {
    vec2 uv = d.xz / (d.y + 0.16) * 0.55 + vec2(uT*0.006, uT*0.002);
    float n = fbm(uv*1.6), n2 = fbm(uv*3.7 + 11.0);
    float dens = smoothstep(1.0 - cobertura, 1.0 - cobertura + 0.28, n*0.75 + n2*0.35);
    dens *= smoothstep(0.015, 0.22, d.y);
    float luzN = clamp(0.55 + 0.9*pow(s, 3.) + 0.3*(n2-0.5), 0., 1.6);
    vec3 cn = mix(cNuvemSombra, cNuvem, clamp(luzN, 0., 1.)) + cSol*pow(s, 10.)*0.35*brilho;
    col = mix(col, cn, dens*nuvens);
    glow *= (1. - dens*nuvens*0.7);
  }
  col += glow;
  if (estrelas > 0. && d.y > -0.02) {
    vec3 p = d * 520.; vec3 g = floor(p); vec3 f = fract(p) - 0.5;
    float hh = fract(sin(dot(g, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
    float e = step(0.9935, hh) * (1. - smoothstep(0.0, 0.55, length(f))) * (0.5 + 1.0 * fract(hh * 91.7));
    float cint = 0.75 + 0.25 * sin(uT * (1.5 + 3. * fract(hh * 17.)) + hh * 50.);
    col += vec3(0.85, 0.9, 1.0) * e * cint * estrelas * smoothstep(-0.02, 0.12, d.y);
    if (via > 0.) {                                           // faixa da Via Láctea (plano galáctico inclinado) com poeira em fbm
      vec3 nv = normalize(vec3(0.35, 0.8, -0.45));
      float b = exp(-pow(dot(d, nv) / 0.2, 2.));
      float n = fbm(d.xz * 5. / (abs(d.y) + 0.6) + 3.1) * 0.9 + 0.35 * fbm(d.xz * 14. + 8.);
      col += vec3(0.55, 0.62, 0.85) * b * n * via * smoothstep(0.0, 0.2, d.y) + vec3(0.9, 0.8, 0.7) * pow(b, 6.) * 0.35 * via * n * smoothstep(0.0, 0.2, d.y);
    }
  }
  if (disco > 0.) col += cSol * smoothstep(0.99915, 0.99925, s) * disco * 5.5;     // disco do astro (lua/sol)
  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

// Cores em sRGB (hex); o material recebe-as em espaço linear.
export function criarCeu({ hor = 0xe8c590, meio = 0x9ec2e8, zen = 0x4a6a9a, baixo = 0x3a3024, sol = 0xffd9a0, sunDir = [-0.5, 0.35, -0.8], expo = 0.55, brilho = 1, nuvens = 0, cobertura = 0.5, nuvem = 0xf6ead8, nuvemSombra = 0x6a6676, estrelas = 0, via = 0, disco = 0 } = {}) {
  const u = {
    cHor: { value: new THREE.Color(hor) }, cMeio: { value: new THREE.Color(meio) }, cZen: { value: new THREE.Color(zen) }, cBaixo: { value: new THREE.Color(baixo) }, cSol: { value: new THREE.Color(sol) },
    cNuvem: { value: new THREE.Color(nuvem) }, cNuvemSombra: { value: new THREE.Color(nuvemSombra) },
    sunDir: { value: new THREE.Vector3(...sunDir).normalize() }, expo: { value: expo }, brilho: { value: brilho }, nuvens: { value: nuvens }, uT: { value: 0 }, estrelas: { value: estrelas }, cobertura: { value: cobertura }, via: { value: via }, disco: { value: disco },
  };
  const m = new THREE.ShaderMaterial({ uniforms: u, vertexShader: CEU_VS, fragmentShader: CEU_FS, side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false });
  const malha = new THREE.Mesh(new THREE.SphereGeometry(900, 48, 24), m);
  malha.renderOrder = -10; malha.frustumCulled = false;
  return { malha, u };
}

// Iluminação por imagem a partir do próprio céu (PMREM): sombras coloridas e reflexos coerentes sem luzes extras.
export function ambienteDoCeu(renderer, ceu, intensidade = 1) {
  const cena = new THREE.Scene();
  const clone = ceu.malha.clone(); clone.material = ceu.malha.material.clone();
  clone.material.depthTest = false;
  cena.add(clone);
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(cena, 0.0, 0.1, 2000);
  pm.dispose();
  return { textura: rt.texture, intensidade };
}

// ------------------------------------------------------------------------- feixes de luz (volumétricos falsos) ---
const RAIO_VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`;
const RAIO_FS = `
varying vec2 vUv; uniform vec3 cor; uniform float op, uT, fase, esp;
void main(){
  float lateral = smoothstep(0., .5, vUv.x) * smoothstep(1., .5, vUv.x);
  float ao_longo = pow(1. - vUv.y, esp) * smoothstep(0., .06, vUv.y);
  float cintila = .88 + .12 * sin(uT*1.3 + fase + vUv.y*5.);
  float a = lateral*lateral * ao_longo * op * cintila;
  gl_FragColor = vec4(cor * a, a);
}`;

// Feixe: dois planos cruzados ao longo de `dir`, de `origem` até `comp` metros. Mistura aditiva, sem escrever profundidade.
export function criarFeixe({ origem, dir, comp = 20, larg = 2.2, cor = 0xffe2a8, op = 0.16, esp = 1.4, fase = 0 }) {
  const g = new THREE.Group();
  const d = new THREE.Vector3(...dir).normalize();
  const mats = [];
  for (let k = 0; k < 2; k++) {
    const geo = new THREE.PlaneGeometry(larg, comp, 1, 1); geo.translate(0, -comp / 2, 0);       // topo na origem, desce ao longo de -y local
    const m = new THREE.ShaderMaterial({ uniforms: { cor: { value: new THREE.Color(cor) }, op: { value: op }, uT: { value: 0 }, fase: { value: fase }, esp: { value: esp } },
      vertexShader: RAIO_VS, fragmentShader: RAIO_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
    const mesh = new THREE.Mesh(geo, m); mesh.rotation.y = k * Math.PI / 2; mesh.renderOrder = 5; mesh.frustumCulled = false;
    g.add(mesh); mats.push(m);
  }
  g.position.set(...origem);
  g.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d);   // eixo local -y alinhado a `dir`
  g.userData.mats = mats;
  return g;
}

// ----------------------------------------------------------------------------- poeira em suspensão (GPU) ---
const POE_VS = `
attribute float aSem; uniform float uT, uTam, uPR; uniform vec3 uMin, uTam3, uVel; varying float vB;
void main(){
  vec3 p = position + uVel * (0.4 + aSem) * uT + vec3(sin(uT*0.7 + aSem*40.), cos(uT*0.5 + aSem*23.), sin(uT*0.6 + aSem*31.)) * 0.35;
  p = uMin + mod(p - uMin, uTam3);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uTam * uPR * (0.5 + aSem) * (300.0 / max(-mv.z, 0.5));
  vB = 0.35 + 0.65 * sin(uT*1.1 + aSem*60.) * sin(uT*1.1 + aSem*60.);
}`;
const POE_FS = `
varying float vB; uniform vec3 uCor; uniform float uOp;
void main(){ vec2 c = gl_PointCoord - .5; float r = length(c); if (r > .5) discard; float a = smoothstep(.5, 0., r); gl_FragColor = vec4(uCor * a * vB * uOp, a * vB * uOp); }`;

export function criarPoeira3D({ semente, n = 600, caixa, vel = [0.05, 0.02, 0.02], cor = 0xffe3b0, tam = 5, op = 0.8 }) {
  const r = rngFor(semente, 31);
  const pos = new Float32Array(n * 3), sem = new Float32Array(n);
  const [x0, y0, z0, x1, y1, z1] = caixa;
  for (let i = 0; i < n; i++) { pos[3 * i] = x0 + r() * (x1 - x0); pos[3 * i + 1] = y0 + r() * (y1 - y0); pos[3 * i + 2] = z0 + r() * (z1 - z0); sem[i] = r(); }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aSem', new THREE.BufferAttribute(sem, 1));
  const m = new THREE.ShaderMaterial({ uniforms: { uT: { value: 0 }, uTam: { value: tam }, uPR: { value: (window.devicePixelRatio || 1) * ((window.RENDER3D || {}).escala ?? 1) }, uMin: { value: new THREE.Vector3(x0, y0, z0) }, uTam3: { value: new THREE.Vector3(x1 - x0, y1 - y0, z1 - z0) },
    uVel: { value: new THREE.Vector3(...vel) }, uCor: { value: new THREE.Color(cor) }, uOp: { value: op } }, vertexShader: POE_VS, fragmentShader: POE_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
  const p = new THREE.Points(g, m); p.frustumCulled = false; p.renderOrder = 6;
  return p;
}

// -------------------------------------------------------------------------------------- câmera ---
// Trilho: pontos de posição e de alvo (Catmull-Rom centrípeta) percorridos por f ∈ [0,1] com uma curva de aceleração.
// `fov` pode ser número ou [a, b]. Retorna uma função pura trilho(f) -> {pos, alvo, fov, roll}.
export function criarTrilho({ pos, alvo, fov = 40, roll = 0, curva = (x) => x }) {
  const cp = new THREE.CatmullRomCurve3(pos.map((p) => new THREE.Vector3(...p)), false, 'centripetal');
  const ca = new THREE.CatmullRomCurve3(alvo.map((p) => new THREE.Vector3(...p)), false, 'centripetal');
  const fv = Array.isArray(fov) ? fov : [fov, fov], rl = Array.isArray(roll) ? roll : [roll, roll];
  return (f) => {
    const u = clamp01(curva(clamp01(f)));
    return { pos: cp.getPointAt(u), alvo: ca.getPointAt(u), fov: fv[0] + (fv[1] - fv[0]) * u, roll: rl[0] + (rl[1] - rl[0]) * u };
  };
}

// Tremor de câmera de mão (determinístico): soma de senos com fases de semente fixa; amplitudes em metros/graus.
export function criarTremor(semente, { pos = 0.012, ang = 0.05 } = {}) {
  const r = rngFor(semente, 77);
  const f = Array.from({ length: 6 }, () => ({ fq: 0.45 + r() * 1.9, ph: r() * 6.283 }));
  return (t) => {
    const s = (i, k = 1) => Math.sin(t * f[i].fq * k + f[i].ph);
    return { dx: pos * (s(0) + 0.5 * s(1, 2.1)), dy: pos * (s(2) + 0.5 * s(3, 1.7)), dz: pos * 0.4 * s(4), drot: ang * (s(5) + 0.4 * s(0, 2.7)) };
  };
}

export function aplicarCamera(cam, k, tremor) {
  cam.position.copy(k.pos);
  cam.position.x += tremor.dx; cam.position.y += tremor.dy; cam.position.z += tremor.dz;
  cam.up.set(Math.sin(((k.roll + tremor.drot) * Math.PI) / 180), Math.cos(((k.roll + tremor.drot) * Math.PI) / 180), 0);
  cam.lookAt(k.alvo);
  cam.fov = k.fov; cam.updateProjectionMatrix();
}

// ----------------------------------------------------------------------------- sol (luz direcional) ---
export function criarSol({ cor = 0xfff0d0, intensidade = 3, dir = [-0.5, 0.6, -0.5], alvo = [0, 0, 0], dist = 120, caixa = 60, mapa = 2048, bias = -0.0004, normalBias = 0.05, near = 1, far = 400 }) {
  const l = new THREE.DirectionalLight(cor, intensidade);
  const d = new THREE.Vector3(...dir).normalize();
  l.position.set(alvo[0] + d.x * dist, alvo[1] + d.y * dist, alvo[2] + d.z * dist);
  l.target.position.set(...alvo);
  l.castShadow = true;
  l.shadow.mapSize.set(mapa, mapa);
  Object.assign(l.shadow.camera, { left: -caixa, right: caixa, top: caixa, bottom: -caixa, near, far });
  l.shadow.bias = bias; l.shadow.normalBias = normalBias; l.shadow.radius = 3;
  return l;
}

export { hash32 };

// ------------------------------------------------------------------------------------- névoa ---
// Camada horizontal de névoa (ruído fractal que desliza devagar), visível só a média distância; função pura de uT.
const NEVOA_VS = `varying vec3 vP; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vP = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const NEVOA_FS = `
varying vec3 vP; uniform float uT, op, perto, longe, esc; uniform vec3 cor;
float h21(vec2 p){ p = fract(p*vec2(123.34,456.21)); p += dot(p,p+45.32); return fract(p.x*p.y); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
float fbm(vec2 p){ float a=.5, s=0.; for(int i=0;i<4;i++){ s+=a*vn(p); p=p*2.02+vec2(5.3,1.7); a*=.5; } return s; }
void main(){
  vec2 q = vP.xz * esc + vec2(uT*0.004, uT*0.0015);
  float n = fbm(q + fbm(q*1.7)*0.8);
  float a = smoothstep(0.36, 0.76, n) * op;
  float dist = length(vP - cameraPosition);
  a *= smoothstep(perto * 0.3, perto, dist) * (1. - smoothstep(longe * 0.6, longe, dist));
  gl_FragColor = vec4(cor * a, a);
}`;
export function criarNevoa({ y, cor, op = 0.5, esc = 0.004, perto = 60, longe = 1500, tam = 2400 }) {
  const m = new THREE.ShaderMaterial({ uniforms: { uT: { value: 0 }, op: { value: op }, perto: { value: perto }, longe: { value: longe }, esc: { value: esc }, cor: { value: new THREE.Color(cor) } },
    vertexShader: NEVOA_VS, fragmentShader: NEVOA_FS, transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false });
  const p = new THREE.Mesh(new THREE.PlaneGeometry(tam, tam, 1, 1), m); p.rotation.x = -Math.PI / 2; p.position.y = y; p.renderOrder = 4; p.frustumCulled = false;
  return p;
}
