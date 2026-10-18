// Fiorde nórdico — PAISAGEM ARTÍSTICA por código (não é um local real nem representa um evento mitológico).
// Relevo procedural (ruído fractal de semente fixa), água com reflexo do céu, floresta instanciada, névoa em camadas e céu
// de crepúsculo que esquenta ao longo da cena. Câmera desliza sobre a água em spline.
import * as THREE from 'three';
import { iniciar3D } from '../engine/base3d.js';
import { criarCeu, criarSol, criarPoeira3D, criarTrilho } from '../engine/cena3d.js';
import { material, malha, terreno, floresta } from '../engine/arq.js';
import * as tex from '../engine/tex.js';
import { smooth } from '../engine/ease.js';

const norm = (v) => { const l = Math.hypot(...v); return v.map((x) => x / l); };
const mixc = (a, b, k) => a.clone().lerp(b, k);

const NEVOA_VS = `varying vec3 vP; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vP = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const NEVOA_FS = `
varying vec3 vP; uniform float uT, op, alt; uniform vec3 cor;
float h21(vec2 p){ p = fract(p*vec2(123.34,456.21)); p += dot(p,p+45.32); return fract(p.x*p.y); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
float fbm(vec2 p){ float a=.5, s=0.; for(int i=0;i<4;i++){ s+=a*vn(p); p=p*2.02+vec2(5.3,1.7); a*=.5; } return s; }
void main(){
  vec2 q = vP.xz * 0.004 + vec2(uT*0.004, uT*0.0015);
  float n = fbm(q + fbm(q*1.7)*0.8);
  float a = smoothstep(0.38, 0.78, n) * op;
  float dist = length(vP - cameraPosition);
  a *= smoothstep(30., 260., dist) * (1. - smoothstep(900., 1500., dist));
  gl_FragColor = vec4(cor * a, a);
}`;

function nevoa(y, cor, op, semente) {
  const m = new THREE.ShaderMaterial({ uniforms: { uT: { value: 0 }, op: { value: op }, alt: { value: y }, cor: { value: new THREE.Color(cor) } }, vertexShader: NEVOA_VS, fragmentShader: NEVOA_FS,
    transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false });
  const p = new THREE.Mesh(new THREE.PlaneGeometry(2400, 2400, 1, 1), m); p.rotation.x = -Math.PI / 2; p.position.y = y; p.renderOrder = 4; p.frustumCulled = false;
  return p;
}

const def = {
  render: { exposicao: 1.0 },
  async montar({ cena, P, D, spec }) {
    const seed = spec.seed ?? 1;
    const paraSol = norm([-0.78, 0.17, -0.6]);                 // sol baixo à esquerda e à frente: ilumina a margem direita, a esquerda fica em silhueta
    const ceu = criarCeu({ hor: 0xff9a5a, meio: 0x6f7fb0, zen: 0x1c2a5c, baixo: 0x1a2430, sol: 0xffb070, sunDir: paraSol, expo: 0.5, brilho: 1.3, nuvens: 0.9, cobertura: 0.45, nuvem: 0xffc89a, nuvemSombra: 0x34385a });
    const corNevoa = new THREE.Color(0x8a96b0);
    cena.fog = new THREE.FogExp2(corNevoa, 0.0021);

    const tRocha = tex.rocha({ tam: 1024, semente: 71, base: [112, 108, 104] });
    const tMusgo = tex.terra({ tam: 1024, semente: 72, base: [78, 92, 56] });
    const tAgua = tex.agua({ tam: 512, semente: 73 });

    // relevo: calha do fiorde ao longo de z, paredes íngremes com cristas
    const R = tex.criarRuido(seed + 90), R2 = tex.criarRuido(seed + 91);
    const eixo = (z) => 70 * Math.sin(z * 0.0042 + 0.6) + 35 * Math.sin(z * 0.011);          // o fiorde serpenteia
    const larg = (z) => 135 + 40 * Math.sin(z * 0.006) + 25 * Math.sin(z * 0.017 + 1);           // meia-largura da água
    const altura = (x, z) => {
      const ax = Math.abs(x - eixo(z)), L = larg(z);
      const d = Math.max(0, ax - L);
      const vale = 760 * (1 - Math.exp(-Math.pow(d / 470, 1.25)));                                  // perfil em U: costas suaves perto d'água, paredões ao fundo
      const cris = 0.62 + 0.75 * R.cresta(x * 0.0045 + 3, z * 0.0045, 5);                           // cristas e vales em grande escala
      let h = vale * cris;
      h += Math.min(1, d / 60) * (46 * R2.cresta(x * 0.018, z * 0.018, 4) + 11 * R.cresta(x * 0.06, z * 0.06, 3));   // rugosidade de rocha
      return ax < L ? -6 - 8 * smooth(Math.min(1, (L - ax) / 60)) : h - 6;                         // leito / margem e encostas
    };
    const solo = terreno({ larg: 3400, prof: 3400, nx: 380, nz: 380, centro: [0, -500], esc: 0.02, altura, uvf: (x, y, z) => [(z + 0.35 * x) * 0.018, (y * 0.9 + Math.abs(x) * 0.15) * 0.018],
      cor: (x, y, z, ny) => {
        const neve = Math.min(1, Math.max(0, (y - 330) / 90)) * Math.min(1, Math.max(0, (ny - 0.55) / 0.25));
        const mata = Math.min(1, Math.max(0, 1 - (y - 20) / 190)) * Math.min(1, Math.max(0, (ny - 0.62) / 0.2));
        const rocha = [0.6, 0.6, 0.62], verde = [0.34, 0.42, 0.26], branco = [0.93, 0.95, 1.0];
        const c = rocha.map((r, i) => r + (verde[i] - r) * mata);
        return c.map((v, i) => v + (branco[i] - v) * neve);
      } });
    const mSolo = material(tRocha, { rep: [1, 1], normal: 1.4, rug: 1, env: 0.7, vertexColors: true });
    cena.add(malha(solo, mSolo, { sombra: false }));

    // água
    const mAgua = new THREE.MeshStandardMaterial({ color: 0x1f3a46, roughness: 0.05, metalness: 0.0, envMapIntensity: 1.6 });
    mAgua.normalMap = tAgua.normalMap.clone(); mAgua.normalMap.repeat.set(700, 700); mAgua.normalMap.needsUpdate = true; mAgua.normalScale = new THREE.Vector2(0.4, 0.4);
    const agua = new THREE.Mesh(new THREE.PlaneGeometry(9000, 9000), mAgua); agua.rotation.x = -Math.PI / 2; agua.position.y = 0; agua.receiveShadow = false;
    cena.add(agua);

    // floresta de pinheiros nas encostas baixas
    const mPin = new THREE.MeshStandardMaterial({ color: 0x1d3322, roughness: 1 }), mTr = new THREE.MeshStandardMaterial({ color: 0x3a2a1c, roughness: 1 });
    const f = floresta({ n: 1100, area: [-900, 900, -1200, 300], altura, aceita: (x, z, h) => h > 3 && h < 170 && Math.abs(x - eixo(z)) > larg(z) + 4, mats: { pinheiro: mPin, tronco: mTr }, seed, escala: [1.0, 2.4] });
    cena.add(f);

    // névoa em camadas (a de cima fica abaixo dos picos) e sol
    const nv1 = nevoa(38, 0xb4bfd6, 0.55, seed), nv2 = nevoa(110, 0xc5c8da, 0.45, seed + 1);
    const sol = criarSol({ cor: 0xffb070, intensidade: 4.2, dir: paraSol, alvo: [0, 40, -250], dist: 600, caixa: 420, mapa: 2048, bias: -0.0006, normalBias: 0.4, near: 50, far: 1400 });
    sol.castShadow = false;                                       // relevo vasto: sem sombra projetada (o contraluz já modela)
    cena.add(sol, sol.target);
    cena.add(new THREE.HemisphereLight(0x7f96d0, 0x3a4a3a, 0.85));
    const poeira = criarPoeira3D({ semente: seed, n: 220, caixa: [-40, 1, -300, 40, 30, 60], vel: [0.5, 0.1, 0.2], cor: 0xffd7b0, tam: 2.2, op: 0.5 });
    cena.add(poeira);

    const trilho = criarTrilho({
      pos: [[-30, 6, 240], [-14, 8, 90], [-4, 12, -80], [6, 18, -250], [10, 30, -420]].map(([x, y, z]) => [x + eixo(z), y, z]),
      alvo: [[20, 52, -140], [8, 48, -300], [0, 46, -520], [-6, 52, -760], [-8, 70, -900]].map(([x, y, z]) => [x + eixo(z), y, z]),
      fov: [50, 38], curva: (x) => 0.25 * x + 0.75 * smooth(x),
    });
    const cSol0 = new THREE.Color(0xffb070), cSol1 = new THREE.Color(0xff5a2a);
    const cHor0 = new THREE.Color(0xff9a5a), cHor1 = new THREE.Color(0xc4301c);
    const cZen0 = new THREE.Color(0x1c2a5c), cZen1 = new THREE.Color(0x120f2a);
    const cNv0 = new THREE.Color(0xffc89a), cNv1 = new THREE.Color(0xff6a4a);
    return {
      ceu, trilho, ibl: 0.9, vinheta: 0.55, poeiraTela: 10,
      eventos: [{ t: 0.05, tipo: 'whoosh' }],
      atualizar(t, fr) {
        const k = smooth(Math.min(1, Math.max(0, (fr - 0.25) / 0.75)));         // o céu esquenta e escurece (puro função de t)
        ceu.u.cHor.value.copy(mixc(cHor0, cHor1, k)); ceu.u.cZen.value.copy(mixc(cZen0, cZen1, k));
        ceu.u.cSol.value.copy(mixc(cSol0, cSol1, k)); ceu.u.cNuvem.value.copy(mixc(cNv0, cNv1, k));
        poeira.material.uniforms.uT.value = t;
        mAgua.normalMap.offset.set((t * 0.0016) % 1, (t * 0.0007) % 1);
      },
    };
  },
};

export const cena3d_fiorde = { build: (palco, spec) => iniciar3D(palco, spec, def) };
