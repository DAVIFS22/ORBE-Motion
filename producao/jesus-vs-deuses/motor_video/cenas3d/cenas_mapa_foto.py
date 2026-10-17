"""Mapa 3D (relevo + rotas animadas) e fotografia com paralaxe 2.5D (projeção de câmera em geometria simples)."""

from __future__ import annotations

import math
import os

import numpy as np
from mathutils import Vector

import bpy
import lib3d as L
from cenas_base import ROTULO_RECONSTRUCAO, Cena3D, registrar, rot

LUGARES = {  # nome exibido, longitude, latitude (coordenadas reais aproximadas)
    "Egito": ("Egito", 31.2, 30.0), "Atenas": ("Grécia", 23.7, 37.98), "Roma": ("Roma", 12.5, 41.9),
    "Jerusalém": ("Judeia", 35.2, 31.8), "Oslo": ("Escandinávia", 10.7, 59.9),
}
LON_C, LAT_C, K = 22.0, 42.0, 1.7


def _xy(chave):
    _, lon, lat = LUGARES[chave]
    return Vector(((lon - LON_C) * K, (lat - LAT_C) * K, 0.0))


@registrar("mapa_3d")
def mapa_3d(a):
    c = Cena3D("Mapa esquemático em 3D (rotas ilustrativas)",
               "Mapa 3D: relevo das terras vem de dados GeoJSON (Natural Earth, domínio público) quando fornecidos; "
               "sem eles, mostra apenas a grade de coordenadas, os pontos e as rotas.")
    p = a.params or {}
    lugares = p.get("lugares") or ["Egito", "Atenas", "Roma"]
    mesa = L.material_pedra("pergaminho", (0.55, 0.42, 0.24), (0.84, 0.72, 0.5), 3, 0.95, 0.15)
    mar = L.material_pedra("mar", (0.1, 0.16, 0.2), (0.2, 0.3, 0.34), 5, 0.4, 0.1)
    terra = L.material_pedra("terra", (0.38, 0.3, 0.16), (0.62, 0.55, 0.32), 6, 0.9, 0.5)
    tinta = L.material("tinta", (0.04, 0.025, 0.015), 0.7)
    vermelho = L.material_emissivo("rota", (1.0, 0.18, 0.08), 6.0)
    pino = L.material("pino", (0.62, 0.08, 0.06), 0.4)
    L.ceu(38, 200, poeira=1.0, ar=1.0, forca=0.07)
    L.sol(40, 215, 4.0, (1.0, 0.9, 0.78), 1.2)
    L.caixa("mesa", (190, 110, 1.0), (0, 0, -1.2), mesa)
    L.caixa("mar", (150, 100, 0.4), (0, 0, -0.5), mar)
    for lon in range(-30, 91, 10):  # grade geográfica real
        L.caixa(f"meridiano{lon}", (0.08, 100, 0.06), ((lon - LON_C) * K, 0, -0.28), tinta)
    for lat in range(10, 71, 10):
        L.caixa(f"paralelo{lat}", (150, 0.08, 0.06), (0, (lat - LAT_C) * K, -0.28), tinta)
    geo = p.get("geojson")
    if geo and os.path.exists(geo):
        aneis = L.polos_geojson(geo, LON_C, LAT_C, K, (-35, 80, 5, 75))
        L.terra_extrudada("terras", aneis, 0.5, terra)
        c.nota += f" Terras: {len(aneis)} polígonos de {os.path.basename(geo)}."
    pts = []
    for nome in lugares:
        pos = _xy(nome)
        L.cone(f"pino_{nome}", 0.55, 2.4, (pos.x, pos.y, 0.4), pino, 16)
        L.esfera(f"cabeca_{nome}", 0.55, (pos.x, pos.y, 3.0), pino)
        rotulo = bpy.data.curves.new(f"rot_{nome}", "FONT")
        rotulo.body = LUGARES[nome][0]
        rotulo.size = 1.5
        rotulo.extrude = 0.08
        ob = bpy.data.objects.new(f"rotulo_{nome}", rotulo)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = (pos.x + 1.0, pos.y - 2.7, 0.8)
        ob.rotation_euler = rot(62, 0, 0)
        rotulo.materials.append(tinta)
        pts.append(pos)
    # rota: curva elevada entre os pontos, desenhada progressivamente
    curva = bpy.data.curves.new("rota", "CURVE")
    curva.dimensions = "3D"
    curva.bevel_depth = 0.18
    spl = curva.splines.new("POLY")
    amostras = []
    for i in range(len(pts) - 1):
        for u in np.linspace(0, 1, 24, endpoint=(i == len(pts) - 2)):
            q = pts[i].lerp(pts[i + 1], float(u))
            q.z = 0.6 + 2.8 * math.sin(math.pi * float(u))
            amostras.append(q)
    spl.points.add(len(amostras) - 1)
    for i, q in enumerate(amostras):
        spl.points[i].co = (q.x, q.y, q.z, 1)
    obj_rota = bpy.data.objects.new("rota", curva)
    bpy.context.scene.collection.objects.link(obj_rota)
    curva.materials.append(vermelho)
    cam = L.criar_camera(34.0, 5.6)
    n = len(pts)

    def anim(prog, t):
        e = L.facilitar(prog)
        curva.bevel_factor_end = min(1.0, max(0.001, e * 1.08))
        x = min(e * (n - 1), n - 1 - 1e-6)
        i = int(x)
        u = x - i
        foco = pts[i].lerp(pts[min(i + 1, n - 1)], u)
        pos = foco + Vector((-6 + 12 * math.sin(prog * 1.6), -34 + 6 * (1 - e), 26 - 5 * e))
        L.posicionar_camera(cam, pos, foco + Vector((0, 0, 0.5)))
    c.animar(anim)
    return c


@registrar("foto_2_5d")
def foto_2_5d(a):
    """Fotografia projetada em geometria 3D (piso + fundo): a câmera se move e a paralaxe é real, sem recorte 2D."""
    c = Cena3D("Fotografia com paralaxe 2.5D", "A imagem original é projetada sobre planos 3D e a câmera virtual se desloca.")
    p = a.params or {}
    caminho = p["imagem"]
    hz = float(p.get("horizonte", 0.5))       # posição do horizonte na foto (0 = topo, 1 = base)
    inten = float(p.get("intensidade", 1.0))
    sc = bpy.context.scene
    try:
        sc.view_settings.view_transform = "Standard"      # preserva as cores da fotografia
        sc.view_settings.look = "None"
    except Exception:
        pass
    mat = L.material_imagem("foto", caminho, 1.0)
    # céu neutro (a foto cobre todo o quadro; o mundo só aparece em eventuais bordas)
    L.ceu_gradiente((0.02, 0.02, 0.025), (0.05, 0.05, 0.05), 0.2)
    D, h = 70.0, 2.0
    cam = L.criar_camera(35.0, None)
    asp = a.largura / a.altura
    cam.data.shift_y = -(0.5 - hz) * (1.0 / asp)
    L.posicionar_camera(cam, Vector((0, 0, h)), Vector((0, 100, h)), 0.0, False)
    bpy.context.view_layer.update()
    from bpy_extras.object_utils import world_to_camera_view
    X = D * math.tan(math.atan(18 / 35)) * 2.2

    def malha(nome, nx, ny, f):
        us = np.linspace(0, 1, nx)
        vs = np.linspace(0, 1, ny)
        verts, uvs = [], []
        for v in vs:
            for u in us:
                P = f(u, v)
                verts.append(tuple(P))
                co = world_to_camera_view(sc, cam, Vector(P))
                uvs.append((co.x, co.y))
        faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i) for j in range(ny - 1) for i in range(nx - 1)]
        m = bpy.data.meshes.new(nome)
        m.from_pydata(verts, [], faces)
        m.update()
        uv = m.uv_layers.new(name="UV")
        for loop in m.loops:
            uv.data[loop.index].uv = uvs[loop.vertex_index]
        o = bpy.data.objects.new(nome, m)
        bpy.context.scene.collection.objects.link(o)
        m.materials.append(mat)
        for poly in m.polygons:
            poly.use_smooth = True
    # piso: z=0, de y=0,4 a D (espaçamento geométrico: mais densidade perto da câmera)
    malha("piso", 28, 40, lambda u, v: (-X + 2 * X * u, 0.4 * (D / 0.4) ** v, 0.0))
    # fundo: plano vertical em y=D
    malha("fundo", 28, 14, lambda u, v: (-X + 2 * X * u, D, v * (h + 70.0 * math.tan(math.atan(18 / 35 / asp)) * 1.6 + 8)))
    # a imagem original é um retângulo: o que ficar fora de [0,1] repete a borda (EXTEND)
    dy = 0.10 * D * inten

    def anim(prog, t):
        e = L.facilitar(prog)
        pos = Vector((1.6 * inten * math.sin(prog * math.pi - math.pi / 2) * -1, dy * e, h + 0.25 * inten * e))
        L.posicionar_camera(cam, pos, pos + Vector((0, 100, 0)), 0.0, False)
    c.animar(anim)
    return c
