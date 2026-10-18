// Cena de teste 3D: mede desempenho e determinismo do WebGL por software (SwiftShader).
import * as THREE from 'three';
import { gsap } from 'gsap';
import { rngFor } from '../engine/rng.js';
import { el } from '../engine/ui.js';

export const teste3d = {
  async build(palco, spec) {
    const W = spec.largura, H = spec.altura;
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H; cv.style.cssText = 'position:absolute;left:0;top:0';
    palco.appendChild(cv);
    const r = new THREE.WebGLRenderer({ canvas: cv, antialias: true, preserveDrawingBuffer: true });
    r.setPixelRatio(1); r.setSize(W, H, false);
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.toneMapping = THREE.ACESFilmicToneMapping; r.outputColorSpace = THREE.SRGBColorSpace;
    const cena = new THREE.Scene(); cena.background = new THREE.Color(0x151a22); cena.fog = new THREE.FogExp2(0x151a22, 0.035);
    const sol = new THREE.DirectionalLight(0xffd9a0, 3.2); sol.position.set(-8, 10, 6); sol.castShadow = true;
    sol.shadow.mapSize.set(2048, 2048); Object.assign(sol.shadow.camera, { left: -14, right: 14, top: 14, bottom: -14, near: 1, far: 40 }); sol.shadow.bias = -0.0004; cena.add(sol);
    cena.add(new THREE.HemisphereLight(0x8fa4c8, 0x3a2c1c, 0.55));
    const chao = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: 0x8a7556, roughness: 0.95 })); chao.rotation.x = -Math.PI / 2; chao.receiveShadow = true; cena.add(chao);
    for (let i = 0; i < 10; i++) for (const lado of [-1, 1]) {
      const c = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.65, 7, 24, 1), new THREE.MeshStandardMaterial({ color: 0xcdb98f, roughness: 0.8 }));
      c.position.set(lado * 3, 3.5, -i * 4); c.castShadow = true; c.receiveShadow = true; cena.add(c);
    }
    const cam = new THREE.PerspectiveCamera(38, W / H, 0.1, 120);
    const tl = gsap.timeline({ paused: true });
    const estado = { z: 6, x: 0, y: 1.8 };
    tl.fromTo(estado, { z: 6, x: -1.5 }, { z: -24, x: 1.5, duration: spec.dur, ease: 'power1.inOut' }, 0);
    gsap.ticker.sleep();
    return {
      seek(t) {
        tl.totalTime(t, false);
        cam.position.set(estado.x, estado.y, estado.z); cam.lookAt(0, 2.4, estado.z - 10);
        r.render(cena, cam);
      },
    };
  },
};
