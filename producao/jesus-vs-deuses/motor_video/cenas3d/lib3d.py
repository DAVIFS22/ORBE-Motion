"""Ferramentas para montar cenas 3D no Blender (bpy 4.x/5.x): materiais, terreno, câmera, atmosfera.

Executa dentro do Blender. Não importa nada do restante do motor (o Blender tem seu próprio Python).
"""

from __future__ import annotations

import math
import os
import random

import bpy  # deve vir antes de bmesh/mathutils quando o Blender roda como módulo Python
import bmesh
import numpy as np
from mathutils import Quaternion, Vector


# ----------------------------------------------------------------- inicialização ---

def reiniciar():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.preferences.addon_enable(module="cycles")
    except Exception:
        pass


def configurar_render(a) -> dict:
    """Aplica motor, resolução, amostras e gerência de cor. Devolve informações sobre o dispositivo usado."""
    sc = bpy.context.scene
    sc.render.engine = a.motor
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = a.largura, a.altura, 100
    sc.render.fps = a.fps
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 12
    sc.render.use_motion_blur = False
    info = {"motor": a.motor, "dispositivo": "CPU"}
    if a.motor == "CYCLES":
        c = sc.cycles
        c.samples = a.amostras
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.04
        c.max_bounces = a.rebotes
        c.diffuse_bounces = min(a.rebotes, 3)
        c.glossy_bounces = min(a.rebotes, 3)
        c.transmission_bounces = 2
        c.volume_bounces = 1
        try:
            c.volume_step_rate = 2.0
            c.volume_max_steps = 256
        except Exception:
            pass
        c.use_denoising = True
        try:
            c.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            pass
        c.device = "CPU"
        if a.dispositivo == "GPU":
            info["dispositivo"] = _ativar_gpu(sc)
        sc.render.threads_mode = "AUTO"
    else:
        try:
            sc.eevee.taa_render_samples = a.amostras
        except Exception:
            pass
    try:
        sc.view_settings.view_transform = "AgX"
    except Exception:
        pass
    for look in ("AgX - High Contrast", "AgX - Medium High Contrast", "High Contrast", "Medium High Contrast"):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            continue
    return info


def _ativar_gpu(sc) -> str:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for tipo in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = tipo
                prefs.refresh_devices() if hasattr(prefs, "refresh_devices") else prefs.get_devices()
            except Exception:
                continue
            gpus = [d for d in prefs.devices if d.type == tipo]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == tipo
                sc.cycles.device = "GPU"
                return f"GPU ({tipo})"
    except Exception as e:  # noqa: BLE001
        print(f"AVISO: falha ao ativar GPU: {e}", flush=True)
    print("AVISO: nenhuma GPU utilizável; renderizando na CPU.", flush=True)
    return "CPU"


# -------------------------------------------------------------------- ruído ---

def ruido2d(nx: int, ny: int, escala: float, oitavas: int = 5, semente: int = 1, persistencia: float = 0.5) -> np.ndarray:
    """Ruído fractal (ny, nx) em [0, 1]; `escala` ≈ número de células do primeiro octave na maior dimensão."""
    from PIL import Image
    rng = np.random.default_rng(semente)
    total = np.zeros((ny, nx), np.float32)
    amp, soma = 1.0, 0.0
    for o in range(oitavas):
        c = max(2, int(escala * 2 ** o))
        gx, gy = c + 2, max(2, int(c * ny / nx) + 2)
        grade = rng.random((gy, gx)).astype(np.float32)
        total += amp * np.asarray(Image.fromarray((grade * 255).astype(np.uint8)).resize((nx, ny), Image.BICUBIC), np.float32) / 255
        soma += amp
        amp *= persistencia
    total /= soma
    lo, hi = total.min(), total.max()
    return (total - lo) / max(hi - lo, 1e-6)


# ---------------------------------------------------------------- materiais ---

def _rgba(c):
    return (c[0], c[1], c[2], 1.0) if len(c) == 3 else tuple(c)


def material(nome: str, cor, rug: float = 0.6, metal: float = 0.0, emissao=None, forca: float = 0.0,
             transm: float = 0.0, ior: float = 1.45):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = _rgba(cor)
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    if transm:
        b.inputs["Transmission Weight"].default_value = transm
        b.inputs["IOR"].default_value = ior
    if emissao is not None:
        b.inputs["Emission Color"].default_value = _rgba(emissao)
        b.inputs["Emission Strength"].default_value = forca
    return m


def material_emissivo(nome: str, cor, forca: float):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = _rgba(cor)
    em.inputs["Strength"].default_value = forca
    sai = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], sai.inputs["Surface"])
    return m


def material_pedra(nome: str, cor_a, cor_b, escala: float = 12.0, rug: float = 0.85, relevo: float = 0.35, metal: float = 0.0):
    """Pedra/areia/mármore procedural: ruído mistura duas cores e gera relevo (bump)."""
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = escala
    ruido.inputs["Detail"].default_value = 8.0
    ruido.inputs["Roughness"].default_value = 0.6
    nt.links.new(coord.outputs["Object"], ruido.inputs["Vector"])
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].color = _rgba(cor_a)
    rampa.color_ramp.elements[1].color = _rgba(cor_b)
    nt.links.new(ruido.outputs["Fac"], rampa.inputs["Fac"])
    nt.links.new(rampa.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = relevo
    bump.inputs["Distance"].default_value = 0.05
    nt.links.new(ruido.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    return m


def material_agua(nome: str, cor, rug: float = 0.06, ondas: float = 0.04, escala: float = 14.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = _rgba(cor)
    b.inputs["Roughness"].default_value = rug
    b.inputs["IOR"].default_value = 1.33
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = escala
    ruido.inputs["Detail"].default_value = 3.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = ondas
    nt.links.new(ruido.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def material_imagem(nome: str, caminho: str, forca: float = 1.0):
    """Imagem como emissão (sem depender da iluminação da cena): preserva as cores da fotografia."""
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(caminho)
    tex.image.colorspace_settings.name = "sRGB"
    tex.extension = "EXTEND"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = forca
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    sai = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], sai.inputs["Surface"])
    return m


# -------------------------------------------------------------------- malhas ---

def _objeto(nome: str, malha, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), suave: bool = True):
    obj = bpy.data.objects.new(nome, malha)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rot
    if mat is not None:
        malha.materials.append(mat)
    for p in malha.polygons:
        p.use_smooth = suave
    return obj


def cilindro(nome, raio, altura, loc, mat, seg=20, raio_topo=None, suave=True, rot=(0, 0, 0)):
    """Cilindro/tronco de cone com base em z=loc.z (a malha cresce para cima)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=raio,
                          radius2=raio if raio_topo is None else raio_topo, depth=altura)
    for v in bm.verts:
        v.co.z += altura / 2
    malha = bpy.data.meshes.new(nome)
    bm.to_mesh(malha)
    bm.free()
    return _objeto(nome, malha, mat, loc, rot, suave)


def caixa(nome, dim, loc, mat, rot=(0, 0, 0), base_no_chao=False, bisel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= dim[0]
        v.co.y *= dim[1]
        v.co.z *= dim[2]
        if base_no_chao:
            v.co.z += dim[2] / 2
    if bisel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bisel, segments=2, affect="EDGES")
    malha = bpy.data.meshes.new(nome)
    bm.to_mesh(malha)
    bm.free()
    return _objeto(nome, malha, mat, loc, rot, suave=False)


def esfera(nome, raio, loc, mat, escala=(1, 1, 1), seg=16, rings=10, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=raio)
    for v in bm.verts:
        v.co.x *= escala[0]
        v.co.y *= escala[1]
        v.co.z *= escala[2]
    malha = bpy.data.meshes.new(nome)
    bm.to_mesh(malha)
    bm.free()
    return _objeto(nome, malha, mat, loc, rot, True)


def cone(nome, raio, altura, loc, mat, seg=16, rot=(0, 0, 0), suave=True):
    return cilindro(nome, raio, altura, loc, mat, seg, raio_topo=0.0, suave=suave, rot=rot)


def prisma_triangular(nome, largura, altura, profundidade, loc, mat):
    """Frontão: triângulo no plano XZ extrudado em Y."""
    h = profundidade / 2
    v = [(-largura / 2, -h, 0), (largura / 2, -h, 0), (0, -h, altura), (-largura / 2, h, 0), (largura / 2, h, 0), (0, h, altura)]
    f = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    malha = bpy.data.meshes.new(nome)
    malha.from_pydata(v, [], f)
    malha.update()
    return _objeto(nome, malha, mat, loc, suave=False)


def malha_de_grade(nome, xs, ys, zs, mat, cores=None):
    """Superfície a partir de uma grade de alturas zs[ny, nx] com coordenadas xs[nx], ys[ny]."""
    ny, nx = zs.shape
    X, Y = np.meshgrid(xs, ys)
    verts = np.stack([X.ravel(), Y.ravel(), zs.ravel()], axis=1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    quads = np.stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()], axis=1)
    malha = bpy.data.meshes.new(nome)
    malha.from_pydata(verts.tolist(), [], quads.tolist())
    malha.update()
    if cores is not None:
        attr = malha.color_attributes.new("cor", "FLOAT_COLOR", "POINT")
        flat = np.concatenate([cores.reshape(-1, 4)], axis=0).astype(np.float32).ravel()
        attr.data.foreach_set("color", flat)
    return _objeto(nome, malha, mat, suave=True)


def plano(nome, largura, altura, loc, mat, rot=(0, 0, 0)):
    return caixa(nome, (largura, altura, 0.001), loc, mat, rot)


def duplicar(obj, nome, loc, rot=None, escala=None):
    c = obj.copy()  # compartilha os dados da malha: barato para florestas e colunatas
    c.name = nome
    c.location = loc
    if rot is not None:
        c.rotation_euler = rot
    if escala is not None:
        c.scale = escala
    bpy.context.scene.collection.objects.link(c)
    return c


# ---------------------------------------------------------------- atmosfera ---

def ceu(elevacao_graus: float, azimute_graus: float = 0.0, poeira: float = 1.0, ar: float = 1.0, forca: float = 1.0,
        tamanho_sol: float = 0.6, disco: bool = False):
    """Céu físico (Nishita/Sky Texture): luz ambiente e cor do horizonte. O sol "de verdade" (sombras e raios de luz)
    vem de `sol()`; o disco do céu fica desligado para não duplicar a luz direta."""
    w = bpy.data.worlds.new("Mundo")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new("ShaderNodeTexSky")
    for tipo in ("SINGLE_SCATTERING", "MULTIPLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        try:
            sky.sky_type = tipo
            break
        except TypeError:
            continue
    sky.sun_elevation = math.radians(elevacao_graus)
    sky.sun_rotation = math.radians(azimute_graus)
    try:
        sky.air_density = ar
        sky.dust_density = poeira
        sky.sun_size = math.radians(tamanho_sol)
        sky.sun_disc = disco
    except Exception:
        pass
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = forca
    sai = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], sai.inputs["Surface"])
    return w


def ceu_gradiente(topo, horizonte, forca=1.0, solo=None):
    """Fundo em gradiente vertical (céus dramáticos e estilizados: tempestade, brasas, crepúsculo)."""
    w = bpy.data.worlds.new("Mundo")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].position = 0.42
    rampa.color_ramp.elements[0].color = _rgba(solo or horizonte)
    rampa.color_ramp.elements[1].position = 0.5
    rampa.color_ramp.elements[1].color = _rgba(horizonte)
    e = rampa.color_ramp.elements.new(0.78)
    e.color = _rgba(topo)
    nt.links.new(sep.outputs["Z"], rampa.inputs["Fac"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = forca
    sai = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(rampa.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], sai.inputs["Surface"])
    return w


def neblina(densidade: float, cor=(0.85, 0.8, 0.75), anisotropia: float = 0.35, centro=(0, 0, 0), dim=(80, 80, 30)):
    """Névoa/bruma e raios de luz (god rays): caixa de volume FINITA em torno da cena.

    Um volume de mundo infinito atenuaria até zero a luz do sol e do céu (que vêm do infinito) e a
    imagem sairia preta; com uma caixa finita, só o trecho dentro dela espalha a luz.
    """
    m = bpy.data.materials.new("Neblina")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    esp = nt.nodes.new("ShaderNodeVolumeScatter")
    esp.inputs["Density"].default_value = densidade
    esp.inputs["Color"].default_value = _rgba(cor)
    esp.inputs["Anisotropy"].default_value = anisotropia
    sai = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(esp.outputs["Volume"], sai.inputs["Volume"])
    obj = caixa("Neblina", dim, centro, m)
    obj.display_type = "WIRE"
    obj.visible_shadow = False
    return obj


def direcao_sol(elevacao_graus: float, azimute_graus: float) -> Vector:
    """Vetor unitário que aponta DO centro da cena PARA o sol (azimute 0 = +Y, 90 = +X)."""
    e, az = math.radians(elevacao_graus), math.radians(azimute_graus)
    return Vector((math.sin(az) * math.cos(e), math.cos(az) * math.cos(e), math.sin(e)))


def sol(elevacao_graus: float, azimute_graus: float, energia: float = 3.0, cor=(1.0, 0.9, 0.75), angulo_graus: float = 0.6):
    luz = bpy.data.lights.new("Sol", "SUN")
    luz.energy = energia
    luz.color = cor[:3]
    luz.angle = math.radians(angulo_graus)
    obj = bpy.data.objects.new("Sol", luz)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = (-direcao_sol(elevacao_graus, azimute_graus)).to_track_quat("-Z", "Y").to_euler()
    return obj


def luz_pontual(loc, energia=500.0, cor=(1.0, 0.7, 0.4), raio=0.2, nome="Luz"):
    luz = bpy.data.lights.new(nome, "POINT")
    luz.energy = energia
    luz.color = cor[:3]
    luz.shadow_soft_size = raio
    obj = bpy.data.objects.new(nome, luz)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    return obj


def luz_area(loc, alvo, largura, altura, energia=800.0, cor=(1, 1, 1), nome="Area"):
    luz = bpy.data.lights.new(nome, "AREA")
    luz.energy = energia
    luz.color = cor[:3]
    luz.shape = "RECTANGLE"
    luz.size, luz.size_y = largura, altura
    obj = bpy.data.objects.new(nome, luz)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


def luz_spot(loc, alvo, energia=2000.0, cor=(1, 0.9, 0.8), angulo_graus=40.0, suavidade=0.4, nome="Spot"):
    luz = bpy.data.lights.new(nome, "SPOT")
    luz.energy = energia
    luz.color = cor[:3]
    luz.spot_size = math.radians(angulo_graus)
    luz.spot_blend = suavidade
    obj = bpy.data.objects.new(nome, luz)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


# ------------------------------------------------------------------ poeira ---

class Poeira:
    """Partículas de poeira/cinzas flutuando (esferas emissivas minúsculas, animadas por código)."""

    def __init__(self, n, caixa_min, caixa_max, raio=0.012, forca=6.0, cor=(1.0, 0.92, 0.8), deriva=(0.05, 0.0, 0.03), semente=3):
        rng = np.random.default_rng(semente)
        self.base = rng.uniform(caixa_min, caixa_max, (n, 3))
        self.fase = rng.uniform(0, 2 * math.pi, (n, 3))
        self.deriva = np.array(deriva) * rng.uniform(0.5, 1.5, (n, 1))
        self.caixa_min, self.caixa_max = np.array(caixa_min), np.array(caixa_max)
        mat = material_emissivo("Poeira", cor, forca)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=raio)
        malha = bpy.data.meshes.new("poeira")
        bm.to_mesh(malha)
        bm.free()
        malha.materials.append(mat)
        self.objs = []
        for i in range(n):
            o = bpy.data.objects.new(f"p{i}", malha)
            bpy.context.scene.collection.objects.link(o)
            self.objs.append(o)

    def atualizar(self, t_seg: float):
        amp = self.caixa_max - self.caixa_min
        for i, o in enumerate(self.objs):
            p = self.base[i] + self.deriva[i] * t_seg + 0.08 * np.sin(self.fase[i] + t_seg * np.array([0.7, 0.5, 0.9]))
            p = self.caixa_min + np.mod(p - self.caixa_min, amp)
            o.location = (p[0], p[1], p[2])


# ------------------------------------------------------------------- câmera ---

def criar_camera(lente_mm=35.0, fstop: float | None = None):
    cam = bpy.data.cameras.new("Camera")
    cam.lens = lente_mm
    cam.sensor_width = 36.0
    cam.clip_start, cam.clip_end = 0.05, 4000.0
    if fstop:
        cam.dof.use_dof = True
        cam.dof.aperture_fstop = fstop
    obj = bpy.data.objects.new("Camera", cam)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "QUATERNION"
    bpy.context.scene.camera = obj
    return obj


def facilitar(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 0.35 * (t * t * (3 - 2 * t)) + 0.65 * t


def catmull(pontos, t: float) -> Vector:
    """Spline Catmull-Rom passando por `pontos` (lista de Vector), t em [0, 1]."""
    n = len(pontos)
    if n == 1:
        return Vector(pontos[0])
    x = min(max(t, 0.0), 1.0) * (n - 1)
    i = min(int(x), n - 2)
    u = x - i
    p0 = Vector(pontos[max(i - 1, 0)])
    p1, p2 = Vector(pontos[i]), Vector(pontos[i + 1])
    p3 = Vector(pontos[min(i + 2, n - 1)])
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def posicionar_camera(cam, pos, alvo, roll_graus=0.0, foco: bool = True):
    pos, alvo = Vector(pos), Vector(alvo)
    direcao = alvo - pos
    q = direcao.to_track_quat("-Z", "Y")
    if roll_graus:
        q = q @ Quaternion((0, 0, 1), math.radians(roll_graus))
    cam.location = pos
    cam.rotation_quaternion = q
    if foco and cam.data.dof.use_dof:
        cam.data.dof.focus_distance = max(0.1, direcao.length)


# ------------------------------------------------------------------ renderização ---

def renderizar_quadro(caminho: str):
    sc = bpy.context.scene
    sc.render.filepath = caminho
    bpy.ops.render.render(write_still=True)


def semente_aleatoria(s: int):
    random.seed(s)
    np.random.seed(s)


# ------------------------------------------------------------ terreno e árvores ---

def terreno(nome, xs, ys, altura_fn, mat, cores=None):
    """Terreno a partir de uma função de altura vetorizada altura_fn(X, Y) -> Z."""
    X, Y = np.meshgrid(xs, ys)
    return malha_de_grade(nome, xs, ys, altura_fn(X, Y), mat, cores)


def amostrar_altura(xs, ys, Z, x, y) -> float:
    """Altura do terreno (grade regular) no ponto (x, y), por interpolação bilinear."""
    fx = (x - xs[0]) / (xs[-1] - xs[0]) * (len(xs) - 1)
    fy = (y - ys[0]) / (ys[-1] - ys[0]) * (len(ys) - 1)
    ix, iy = int(np.clip(fx, 0, len(xs) - 2)), int(np.clip(fy, 0, len(ys) - 2))
    tx, ty = fx - ix, fy - iy
    return float((Z[iy, ix] * (1 - tx) + Z[iy, ix + 1] * tx) * (1 - ty) + (Z[iy + 1, ix] * (1 - tx) + Z[iy + 1, ix + 1] * tx) * ty)


def material_lava(nome="Lava"):
    """Rocha escura com veios incandescentes definidos pelo canal R do atributo de cor 'cor'."""
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "cor"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(at.outputs["Color"], sep.inputs["Color"])
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].color = (0.02, 0.012, 0.012, 1)
    rampa.color_ramp.elements[1].color = (1.0, 0.28, 0.04, 1)
    rampa.color_ramp.elements[0].position = 0.45
    rampa.color_ramp.elements[1].position = 0.62
    nt.links.new(sep.outputs["Red"], rampa.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 9.0
    nt.links.new(rampa.outputs["Color"], em.inputs["Color"])
    rocha = nt.nodes.new("ShaderNodeBsdfPrincipled")
    rocha.inputs["Base Color"].default_value = (0.03, 0.025, 0.025, 1)
    rocha.inputs["Roughness"].default_value = 0.9
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(sep.outputs["Red"], mix.inputs["Fac"])
    nt.links.new(rocha.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    sai = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs["Shader"], sai.inputs["Surface"])
    return m


# ------------------------------------------------------------ HDRI e modelos externos ---

def ceu_hdri(caminho: str, rotacao_graus: float = 0.0, forca: float = 1.0):
    """Ilumina a cena com um HDRI (ex.: Poly Haven, CC0), substituindo o céu procedural."""
    w = bpy.data.worlds.new("HDRI")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapa = nt.nodes.new("ShaderNodeMapping")
    mapa.inputs["Rotation"].default_value[2] = math.radians(rotacao_graus)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(caminho)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = forca
    sai = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(coord.outputs["Generated"], mapa.inputs["Vector"])
    nt.links.new(mapa.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], sai.inputs["Surface"])
    return w


def importar_modelo(caminho: str, loc=(0, 0, 0), escala: float = 1.0, rot=(0, 0, 0)):
    """Importa um modelo glTF/GLB (ex.: Poly Haven CC0) e o posiciona. Devolve os objetos importados."""
    antes = set(bpy.data.objects)
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=caminho)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=caminho)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=caminho)
    else:
        raise ValueError(f"Formato de modelo não suportado: {ext}")
    novos = [o for o in bpy.data.objects if o not in antes]
    raizes = [o for o in novos if o.parent is None]
    for o in raizes:
        o.location = Vector(loc) + o.location * escala
        o.scale = o.scale * escala
        o.rotation_euler = rot
    return novos


# ---------------------------------------------------------------- geodados ---

def polos_geojson(caminho: str, lon_c: float, lat_c: float, k: float, caixa=None):
    """Anéis externos de polígonos GeoJSON projetados em (x, y) = ((lon-lon_c)*k, (lat-lat_c)*k).

    `caixa=(lon0, lon1, lat0, lat1)` descarta polígonos fora da área.
    """
    import json
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    feicoes = dados.get("features", [dados])
    aneis = []
    for ft in feicoes:
        g = ft.get("geometry", ft)
        if g["type"] == "Polygon":
            polys = [g["coordinates"]]
        elif g["type"] == "MultiPolygon":
            polys = g["coordinates"]
        else:
            continue
        for poly in polys:
            anel = poly[0]
            if caixa and not any(caixa[0] <= p[0] <= caixa[1] and caixa[2] <= p[1] <= caixa[3] for p in anel):
                continue
            pts = [((p[0] - lon_c) * k, (p[1] - lat_c) * k) for p in anel[:-1]]
            if len(pts) >= 3:
                aneis.append(pts)
    return aneis


def terra_extrudada(nome: str, aneis, altura: float, mat):
    """Extruda anéis (polígonos) em massas de terra 3D (mapa em relevo)."""
    bm = bmesh.new()
    for pts in aneis:
        try:
            verts = [bm.verts.new((x, y, 0.0)) for x, y in pts]
            face = bm.faces.new(verts)
        except ValueError:
            continue
        ret = bmesh.ops.extrude_face_region(bm, geom=[face])
        topo = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=(0, 0, altura), verts=topo)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    malha = bpy.data.meshes.new(nome)
    bm.to_mesh(malha)
    bm.free()
    return _objeto(nome, malha, mat, suave=False)
