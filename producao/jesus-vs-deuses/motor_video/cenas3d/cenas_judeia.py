"""Judeia e Galileia (século I): aldeia, lago, colina das cruzes e túmulo. Reconstruções artísticas, não registro histórico."""

from __future__ import annotations

import math

import numpy as np
from mathutils import Vector

import lib3d as L
from cenas_base import ROTULO_RECONSTRUCAO, Cena3D, registrar, rot


def _colinas(a, nx=130, ny=130, tam=500, amp=40, escala=5):
    xs, ys = np.linspace(-tam / 2, tam / 2, nx), np.linspace(-tam / 2, tam / 2, ny)
    r = L.ruido2d(nx, ny, escala, 5, a.semente)
    return xs, ys, r, amp


def _oliveira(rng, base_tronco, base_folha, x, y, z, s=1.0):
    h = rng.uniform(2.4, 3.6) * s
    L.cilindro("tronco", 0.22 * s, h, (x, y, z), base_tronco, 8, 0.14 * s, True,
               (rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0))
    for k in range(4):
        L.esfera("folha", rng.uniform(0.9, 1.5) * s, (x + rng.uniform(-0.9, 0.9) * s, y + rng.uniform(-0.9, 0.9) * s, z + h + rng.uniform(0, 0.7)),
                 base_folha, (1.2, 1.2, 0.7), 10, 7)


@registrar("aldeia_judeia")
def aldeia_judeia(a):
    c = Cena3D(ROTULO_RECONSTRUCAO + ": aldeia da Judeia/Galileia, século I",
               "Reconstrução procedural inspirada em casas de pedra caiada e telhados planos da região; sem pretensão de exatidão arqueológica.")
    rng = np.random.default_rng(a.semente)
    cal = L.material_pedra("calcario", (0.62, 0.52, 0.38), (0.86, 0.78, 0.62), 10, 0.92, 0.45)
    cal2 = L.material_pedra("calcario2", (0.5, 0.42, 0.3), (0.72, 0.64, 0.5), 14, 0.95, 0.5)
    chao = L.material_pedra("rua", (0.36, 0.28, 0.18), (0.58, 0.48, 0.34), 16, 0.98, 0.3)
    tronco = L.material("tronco", (0.17, 0.12, 0.08), 0.95)
    folha = L.material("oliva", (0.25, 0.3, 0.2), 0.8)
    L.ceu(12, 78, poeira=3.0, ar=1.0, forca=0.05)
    L.sol(13, 80, 4.0, (1.0, 0.78, 0.55), 0.8)
    L.neblina(0.0055, (0.95, 0.8, 0.62), 0.7, (0, 10, 6), (90, 120, 24))
    xs = np.linspace(-200, 200, 100)
    ys = np.linspace(-120, 220, 100)
    ruido = L.ruido2d(100, 100, 6, 5, a.semente)

    def altura(X, Y):
        rua = np.clip(np.abs(X) / 18, 0, 1)
        return -0.3 + 18 * ruido * rua ** 1.5 + 0.8 * np.sin(Y * 0.1) * (1 - rua)
    terr = L.terreno("terreno", xs, ys, altura, chao)
    L.caixa("rua", (6.5, 150, 0.12), (0, 28, -0.2), chao)
    # casas dos dois lados da rua: caixas de pedra com parapeito, porta e janelinha
    for lado in (-1, 1):
        y = -30.0
        k = 0
        while y < 110:
            larg, prof, alt = rng.uniform(5.0, 8.0), rng.uniform(5.0, 7.5), rng.uniform(3.0, 4.6)
            x = lado * (3.6 + prof / 2 + rng.uniform(0, 1.2))
            mat = cal if rng.random() < 0.6 else cal2
            L.caixa(f"casa{lado}{k}", (prof, larg, alt), (x, y + larg / 2, 0), mat, base_no_chao=True, bisel=0.06)
            L.caixa(f"parap{lado}{k}", (prof + 0.3, larg + 0.3, 0.32), (x, y + larg / 2, alt), mat, base_no_chao=True)
            if rng.random() < 0.4:   # cômodo superior (telhado plano com terraço)
                L.caixa(f"alto{lado}{k}", (prof * 0.55, larg * 0.5, 2.3), (x + lado * prof * 0.18, y + larg / 2, alt + 0.3), mat, base_no_chao=True, bisel=0.05)
            face_x = x - lado * prof / 2
            L.caixa(f"porta{lado}{k}", (0.25, 1.1, 2.1), (face_x - lado * 0.02, y + larg * 0.35, 0), L.material("madeira", (0.08, 0.05, 0.03), 0.8), base_no_chao=True)
            L.caixa(f"jan{lado}{k}", (0.2, 0.55, 0.55), (face_x - lado * 0.02, y + larg * 0.75, 2.0), L.material("janela", (0.01, 0.01, 0.01), 0.9))
            for j in range(3):  # degraus de pedra na entrada
                L.caixa(f"deg{lado}{k}{j}", (0.45, 1.5, 0.16), (face_x - lado * (0.4 + 0.4 * j), y + larg * 0.35, 0), cal2, base_no_chao=True)
            if rng.random() < 0.55:
                _oliveira(rng, tronco, folha, x + lado * (prof / 2 + 3.5), y + larg / 2, 0, rng.uniform(0.8, 1.2))
            y += larg + rng.uniform(0.6, 2.4)
            k += 1
    # barracas de mercado (postes + tecido) e jarros
    cores = [(0.55, 0.12, 0.08), (0.75, 0.55, 0.15), (0.14, 0.24, 0.45), (0.5, 0.35, 0.2)]
    for i, (yy, xx) in enumerate(((12, 2.2), (26, -2.3), (44, 2.0), (58, -2.2))):
        pano = L.material(f"pano{i}", cores[i % 4], 0.9)
        for dx in (-0.9, 0.9):
            for dy in (-0.9, 0.9):
                L.cilindro(f"poste{i}{dx}{dy}", 0.04, 2.3, (xx + dx, yy + dy, 0), tronco, 6)
        L.caixa(f"toldo{i}", (2.1, 2.1, 0.04), (xx, yy, 2.3), pano, rot=(math.radians(8 * (-1) ** i), 0, 0))
        L.caixa(f"balcao{i}", (1.6, 1.0, 0.8), (xx, yy + 0.2, 0), tronco, base_no_chao=True)
        for j in range(3):
            L.esfera(f"jarro{i}{j}", 0.17, (xx - 0.5 + 0.5 * j, yy + 0.2, 0.95), L.material("barro", (0.5, 0.25, 0.12), 0.7), (1, 1, 1.25))
    L.cilindro("poco", 0.9, 0.8, (-1.6, 70, 0), cal2, 16)
    poeira = L.Poeira(160, (-4, -25, 0.3), (4, 60, 5), 0.012, 4.5, (1.0, 0.88, 0.7), (0.04, 0.08, 0.02), 4)
    cam = L.criar_camera(28.0, 4.0)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((0.4 * math.sin(p * 3.0), -34 + 76 * e, 1.7 + 0.1 * math.sin(p * 5)))
        L.posicionar_camera(cam, pos, pos + Vector((0.8 * math.sin(p * 2.0), 18, 0.5)), 0.3 * math.sin(p * 3))
        poeira.atualizar(t)
    c.animar(anim)
    return c


@registrar("lago_galileia")
def lago_galileia(a):
    c = Cena3D(ROTULO_RECONSTRUCAO + ": lago na Galileia ao amanhecer", "Paisagem procedural inspirada nas colinas ao redor de um lago; barco estilizado.")
    cal = L.material_pedra("colinas", (0.2, 0.22, 0.1), (0.5, 0.46, 0.26), 5, 0.95, 0.35)
    madeira = L.material_pedra("madeira", (0.14, 0.08, 0.04), (0.3, 0.19, 0.1), 30, 0.8, 0.3)
    L.ceu(8, 20, poeira=2.0, ar=1.0, forca=0.12)
    L.sol(9, 22, 6.5, (1.0, 0.76, 0.54), 0.7)
    L.neblina(0.0012, (0.95, 0.85, 0.75), 0.75, (0, 80, 30), (900, 900, 120))
    nx = 140
    xs = ys = np.linspace(-400, 400, nx)
    r = L.ruido2d(nx, nx, 7, 5, a.semente)

    def altura(X, Y):
        d = np.sqrt((X / 1.15) ** 2 + (Y - 10) ** 2)
        margem = np.clip((d - 150) / 160, 0, 1.6)
        return -3 + 85 * margem ** 1.3 * (0.4 + 0.9 * r)
    L.terreno("colinas", xs, ys, altura, cal)
    L.caixa("agua", (3000, 3000, 0.2), (0, 0, -0.1), L.material_agua("agua", (0.02, 0.05, 0.07), 0.025, 0.025, 30))
    L.esfera("casco", 2.4, (14, 16, 0.2), madeira, (1.8, 0.55, 0.38), 24, 12)
    L.cilindro("mastro", 0.07, 4.2, (14.5, 16, 0.4), madeira, 8)
    L.prisma_triangular("vela", 3.0, 3.4, 0.05, (14.7, 16, 0.9), L.material("vela", (0.82, 0.72, 0.55), 0.9))
    cam = L.criar_camera(32.0, 4.5)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((-26 + 30 * e, -56 + 38 * e, 2.4 + 0.3 * math.sin(p * 4.0)))
        L.posicionar_camera(cam, pos, Vector((14, 22, 4.5)), 0.5 * math.sin(p * 2))
    c.animar(anim)
    return c


@registrar("colina_cruzes")
def colina_cruzes(a):
    c = Cena3D(ROTULO_RECONSTRUCAO + ": colina ao entardecer", "Cena simbólica e contida: colina, três cruzes em silhueta, céu de tempestade. Sem violência gráfica.")
    pedra = L.material_pedra("colina", (0.05, 0.04, 0.03), (0.2, 0.15, 0.1), 5, 0.95, 0.4)
    madeira = L.material("madeira", (0.02, 0.015, 0.012), 0.9)
    L.ceu(3.0, 8, poeira=9.0, ar=1.6, forca=0.07)
    L.sol(4.5, 8, 7.0, (1.0, 0.5, 0.2), 1.2)
    L.neblina(0.0035, (0.95, 0.55, 0.3), 0.85, (0, 40, 20), (500, 500, 90))
    nx = 120
    xs = ys = np.linspace(-150, 150, nx)
    r = L.ruido2d(nx, nx, 6, 5, a.semente)

    def altura(X, Y):
        d = np.sqrt(X ** 2 + (Y * 0.85) ** 2)
        return -4 + 26 * np.exp(-(d / 55) ** 2) + 6 * r * np.clip(d / 40, 0, 1) + 14 * np.clip((d - 90) / 70, 0, 1)
    L.terreno("colina", xs, ys, altura, pedra)
    topo = float(altura(np.array([[0.0]]), np.array([[0.0]]))[0, 0])
    Zg = altura(*np.meshgrid(xs, ys))
    for x, h, w in ((-5.0, 3.4, 1.8), (0.0, 4.8, 2.5), (5.0, 3.4, 1.8)):
        L.caixa(f"poste{x}", (0.22, 0.22, h), (x, 0, topo - 0.2), madeira, base_no_chao=True)
        L.caixa(f"travessa{x}", (w, 0.2, 0.2), (x, 0, topo - 0.2 + h * 0.72), madeira)
    cam = L.criar_camera(38.0, None)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((-12 + 9 * e, -56 + 24 * e, 0.0))
        pos.z = L.amostrar_altura(xs, ys, Zg, pos.x, pos.y) + 9.0 + 2.0 * e
        L.posicionar_camera(cam, pos, Vector((0, 0, topo + 3.0)), 0.0)
    c.animar(anim)
    return c


@registrar("tumulo_vazio")
def tumulo_vazio(a):
    import bpy
    c = Cena3D(ROTULO_RECONSTRUCAO + ": túmulo escavado na rocha ao amanhecer",
               "Cena simbólica e contida: entrada de túmulo com pedra circular rolada, luz do amanhecer; sem efeitos sobrenaturais.")
    rocha = L.material_pedra("rocha", (0.07, 0.055, 0.045), (0.24, 0.19, 0.14), 6, 0.95, 0.8)
    chao = L.material_pedra("chao", (0.12, 0.09, 0.06), (0.32, 0.26, 0.18), 9, 0.97, 0.5)
    L.ceu(3, 195, poeira=0.6, ar=1.6, forca=0.05)
    L.sol(6, 195, 3.2, (1.0, 0.68, 0.4), 0.8)
    L.neblina(0.0014, (0.95, 0.82, 0.68), 0.8, (0, 0, 8), (70, 70, 24))
    nx = 100
    xs = ys = np.linspace(-90, 90, nx)
    r = L.ruido2d(nx, nx, 7, 5, a.semente)

    def altura(X, Y):
        plano = np.where(np.abs(X) < 14, np.clip((Y - 2.5) / 6, 0, 1), 1.0) * 0 + 0.0
        encosta = np.clip((Y - 16) / 30, 0, 1.3) ** 1.4 * 20
        return -0.15 + encosta * (0.6 + 0.6 * r) + 0.5 * r * np.clip(np.abs(Y + 10) / 30, 0, 1) + plano
    L.terreno("chao", xs, ys, altura, chao)
    # penhasco com o vão escavado: subtração booleana (rocha menos câmara/porta)
    pen = L.caixa("penhasco", (46, 15, 14), (0, 10.0, 0), rocha, base_no_chao=True, bisel=0.15)
    corte_porta = L.caixa("corte_porta", (1.9, 8.0, 2.35), (0, 3.2, 0), rocha, base_no_chao=True)
    corte_camara = L.caixa("corte_camara", (3.8, 7.0, 2.7), (0, 10.0, 0), rocha, base_no_chao=True)
    bpy.context.view_layer.objects.active = pen
    for corte in (corte_porta, corte_camara):
        mod = pen.modifiers.new("Corte", "BOOLEAN")
        mod.operation, mod.object = "DIFFERENCE", corte
        try:
            mod.solver = "EXACT"
        except Exception:
            pass
        bpy.ops.object.modifier_apply(modifier="Corte")
        bpy.data.objects.remove(corte, do_unlink=True)
    L.caixa("banco", (1.2, 2.6, 0.5), (0, 10.0, 0), L.material("lencol", (0.85, 0.8, 0.7), 0.9), base_no_chao=True)
    L.cilindro("pedra_rolada", 1.4, 0.55, (-3.1, 1.2, 1.4), rocha, 48, None, True, rot(90, 0, 8))
    L.caixa("trilho", (6.0, 0.4, 0.2), (-0.6, 1.2, 0.0), chao, base_no_chao=True)
    L.luz_area((0, 11.5, 1.6), (0, -6, 1.2), 2.6, 1.8, 900.0, (1.0, 0.86, 0.62), "luz_interior").visible_camera = False
    rng = np.random.default_rng(a.semente)
    tronco = L.material("tronco", (0.15, 0.11, 0.07), 0.95)
    folha = L.material("oliva", (0.22, 0.27, 0.17), 0.8)
    for k in range(10):
        lado = -1 if k % 2 else 1
        _oliveira(rng, tronco, folha, lado * rng.uniform(12, 26), rng.uniform(-30, -2), 0, rng.uniform(0.9, 1.4))
    poeira = L.Poeira(120, (-4, -6, 0.4), (4, 8, 3.6), 0.01, 4.0, (1.0, 0.9, 0.72), (0.0, 0.06, 0.03), 8)
    cam = L.criar_camera(26.0, 4.0)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((1.8 - 1.8 * e, -19 + 11 * e, 1.9 - 0.15 * e))
        L.posicionar_camera(cam, pos, Vector((0, 4.0, 1.3)), 0.0)
        poeira.atualizar(t)
    c.animar(anim)
    return c
