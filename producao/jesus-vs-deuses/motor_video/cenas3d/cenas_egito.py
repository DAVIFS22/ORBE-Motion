"""Egito antigo: templo hipostilo, relevo e representações estilizadas de Rá, Osíris e Anúbis."""

from __future__ import annotations

import math

import numpy as np
from mathutils import Vector

import lib3d as L
from cenas_base import (ROTULO_DEUS, ROTULO_RECONSTRUCAO, Cena3D, Figura, camera_orbita, materiais_estatua, palco_estatua, registrar,
                        rot)


def _duna(xs, ys, semente, amp):
    X, Y = np.meshgrid(xs, ys)
    r = L.ruido2d(len(xs), len(ys), 6, 5, semente)
    cristas = 1 - np.abs(2 * r - 1)  # cristas de duna
    return amp * (cristas ** 1.6)


@registrar("templo_egipcio")
def templo_egipcio(a):
    c = Cena3D(ROTULO_RECONSTRUCAO + ": templo egípcio",
               "Sala hipostila procedural inspirada na arquitetura egípcia; sem hieróglifos nem inscrições inventadas.")
    areia = L.material_pedra("arenito", (0.50, 0.34, 0.20), (0.80, 0.63, 0.40), 7, 0.92, 0.5)
    escuro = L.material_pedra("arenito_escuro", (0.36, 0.25, 0.15), (0.56, 0.42, 0.27), 11, 0.95, 0.4)
    ouro = L.material("ouro", (1.0, 0.72, 0.25), 0.3, 1.0)
    L.ceu(34, 60, poeira=2.4, ar=1.2, forca=0.035)
    L.sol(46, 28, 4.2, (1.0, 0.82, 0.58), 0.9)
    L.neblina(0.0042, (0.92, 0.8, 0.62), 0.75, (0, 4, 8), (34, 80, 18))

    L.caixa("piso", (34, 80, 0.5), (0, 2, -0.25), escuro)
    nx, ny = 70, 80
    xs, ys = np.linspace(-220, 220, nx), np.linspace(-160, 320, ny)
    X, Y = np.meshgrid(xs, ys)
    d = np.maximum(np.abs(X) / 22.0, np.abs(Y - 2) / 50.0)  # as dunas começam fora do edifício
    t = np.clip((d - 1.0) / 0.9, 0, 1)
    mascara = t * t * (3 - 2 * t)
    z = -0.9 + _duna(xs, ys, a.semente, 9.0) * mascara
    L.malha_de_grade("deserto", xs, ys, z, areia)

    ys_col = [-16 + 5.5 * i for i in range(7)]
    for fila, (x, h, r) in enumerate([(-3.4, 8.0, 0.72), (3.4, 8.0, 0.72), (-8.6, 5.2, 0.58), (8.6, 5.2, 0.58)]):
        for i, y in enumerate(ys_col):
            n = f"col{fila}_{i}"
            L.cilindro(n + "b", r * 1.3, 0.3, (x, y, 0), escuro, 20)
            L.cilindro(n + "f", r, h, (x, y, 0.3), areia, 18, r * 0.86)
            L.cilindro(n + "c", r * 0.86, 1.2, (x, y, 0.3 + h), areia, 18, r * 1.6)
            L.caixa(n + "a", (r * 3.3, r * 3.3, 0.4), (x, y, 0.3 + h + 1.2), escuro, base_no_chao=True)
        topo = 0.3 + h + 1.6
        L.caixa(f"arq{fila}", (1.5, 6 * 5.5 + 3, 1.1), (x, 1.0, topo), escuro, base_no_chao=True)
        if h < 6:  # nave lateral: laje completa
            L.caixa(f"laje{fila}", (4.6, 6 * 5.5 + 3, 0.7), (x + (0 if x < 0 else 0), 1.0, topo + 1.1), areia, base_no_chao=True)
    for i, y in enumerate(ys_col):  # nave central: lajes em baias alternadas (deixa entrar o sol)
        L.caixa(f"viga{i}", (8.2, 1.2, 1.0), (0, y, 0.3 + 8.0 + 1.6), escuro, base_no_chao=True)
    for x in (-12.6, 12.6):
        L.caixa(f"parede{x}", (1.4, 80, 8.6), (x, 2, 0), areia, base_no_chao=True)
        for k in range(8):  # faixas de relevo abstratas (retângulos rebaixados, sem inscrições)
            L.caixa(f"painel{x}_{k}", (0.3, 5.0, 3.2), (x - math.copysign(0.6, x), -16 + k * 5.5, 3.2), escuro, base_no_chao=True)
    # pilone ao fundo com a porta aberta para o deserto
    L.caixa("pilone_e", (9.5, 3.0, 17), (-8.2, 23, 0), areia, base_no_chao=True)
    L.caixa("pilone_d", (9.5, 3.0, 17), (8.2, 23, 0), areia, base_no_chao=True)
    L.caixa("verga", (7.0, 3.0, 5.0), (0, 23, 12.0), areia, base_no_chao=True)
    L.cilindro("obelisco", 1.3, 20, (7, 48, -0.5), areia, 4, 0.8, False, rot(0, 0, 45))
    L.cone("obelisco_topo", 0.8, 1.6, (7, 48, 19.5), ouro, 4, rot(0, 0, 45), False)
    # luz que entra pelas aberturas do teto (poços de luz): área quente apontada para baixo, invisível à câmera
    for i, y in enumerate(ys_col):
        if i % 2 == 1:
            L.luz_area((0, y, 12.5), (0, y, 0), 8, 5.0, 5500.0, (1.0, 0.82, 0.58), f"poco{i}").visible_camera = False
    L.luz_area((0, 28, 5.0), (0, -4, 3.0), 8, 6, 9000.0, (1.0, 0.85, 0.65), "porta_fundo").visible_camera = False
    poeira = L.Poeira(160, (-9, -20, 0.4), (9, 20, 8.0), 0.012, 5.0, (1.0, 0.9, 0.7), (0.03, 0.05, 0.02), 9)
    cam = L.criar_camera(28.0, 3.2)
    pts = [Vector(p) for p in [(-0.7, -22, 1.8), (0.5, -9, 1.85), (-0.4, 3, 1.75), (0.3, 14, 1.9)]]

    def anim(p, t):
        e = L.facilitar(p)
        pos = L.catmull(pts, e)
        alvo = pos + Vector((0.8 * math.sin(p * 2.1), 14.0, 1.0 + 0.5 * math.sin(p * 1.3)))
        L.posicionar_camera(cam, pos, alvo, 0.4 * math.sin(p * 2.6))
        poeira.atualizar(t)
    c.animar(anim)
    return c


@registrar("relevo_egipcio")
def relevo_egipcio(a):
    """Close-up (macro) sobre um painel de relevo com símbolos conhecidos: anel de vida (ankh) e disco solar com raios."""
    c = Cena3D(ROTULO_RECONSTRUCAO + ": relevo em pedra",
               "Painel procedural com símbolos reconhecíveis (ankh e disco solar); sem escrita hieroglífica inventada.")
    pedra = L.material_pedra("relevo_pedra", (0.46, 0.33, 0.2), (0.74, 0.58, 0.38), 5, 0.85, 0.7)
    ouro = L.material("ouro", (0.9, 0.62, 0.2), 0.4, 0.8)
    L.ceu_gradiente((0.02, 0.02, 0.03), (0.05, 0.035, 0.03), 0.3)
    L.neblina(0.02, (0.9, 0.75, 0.6), 0.5, (0, -1, 2), (16, 8, 6))
    L.caixa("parede", (14, 0.8, 5), (0, 0.4, 0), pedra, base_no_chao=True)

    def ankh(x, z, s):
        L.caixa("ankh_h", (0.5 * s, 0.07, 0.09 * s), (x, -0.02, z + 0.05 * s), pedra)
        L.caixa("ankh_v", (0.1 * s, 0.07, 0.9 * s), (x, -0.02, z - 0.35 * s), pedra)
        import bpy
        bpy.ops.mesh.primitive_torus_add(major_radius=0.17 * s, minor_radius=0.05 * s, major_segments=24, minor_segments=8,
                                         location=(x, -0.02, z + 0.3 * s), rotation=rot(90, 0, 0))
        o = bpy.context.object
        o.scale = (1, 1, 0.7)
        o.data.materials.append(pedra)
    for i, x in enumerate((-2.4, -1.2, 1.2, 2.4)):
        ankh(x, 2.0, 1.2)
    # disco solar com raios
    L.cilindro("disco", 0.62, 0.1, (0, -0.05, 2.0), pedra, 40, rot=rot(90, 0, 0))
    for k in range(16):
        ang = 2 * math.pi * k / 16
        L.caixa(f"raio{k}", (0.07, 0.07, 0.62), (math.cos(ang) * 1.12, -0.03, 2.0 + math.sin(ang) * 1.12), pedra,
                (0, -(ang - math.pi / 2), 0))
    L.caixa("faixa_a", (14, 0.12, 0.18), (0, -0.04, 3.55), pedra)
    L.caixa("faixa_b", (14, 0.12, 0.18), (0, -0.04, 0.5), pedra)
    L.sol(18, 105, 4.5, (1.0, 0.8, 0.55), 0.8)   # luz rasante: realça o relevo
    L.luz_area((-4, -3, 3), (0, 0, 2), 3, 3, 250.0, (1, 0.8, 0.6))
    poeira = L.Poeira(70, (-3.5, -2.5, 0.8), (3.5, -0.1, 3.4), 0.01, 6.0, (1.0, 0.9, 0.75), (0.015, 0.0, 0.01), 4)
    cam = L.criar_camera(70.0, 2.4)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((-3.0 + 6.0 * e, -3.1 + 0.6 * e, 1.9 + 0.15 * math.sin(p * 3)))
        L.posicionar_camera(cam, pos, Vector((pos.x * 0.9, 0.0, 2.0)))
        poeira.atualizar(t)
    c.animar(anim)
    return c


def _estatua_cena(a, rotulo, nota, construir, parede_cor=((0.3, 0.2, 0.12), (0.5, 0.36, 0.22)), chave=(1.0, 0.78, 0.55), aro=(0.5, 0.7, 1.0),
                  escala=1.35, orbita=None, fundo_extra=None):
    c = Cena3D(rotulo, nota)
    mats = materiais_estatua()
    parede = L.material_pedra("parede", parede_cor[0], parede_cor[1], 8, 0.9, 0.5)
    piso = L.material_pedra("piso", (0.12, 0.09, 0.07), (0.22, 0.17, 0.12), 6, 0.6, 0.2)
    topo = palco_estatua(c, mats, parede, piso, chave, aro)
    fig = Figura("deus", (0, 0, topo), escala, mats)
    alvo_cabeca = construir(fig)
    if fundo_extra:
        fundo_extra(c, mats)
    kw = dict(r=(9.5, 8.0), az=(-26, 22), h=(2.1, 2.8), lente=40.0, fstop=3.2, alvo_dz=(-0.9, -0.9))
    if orbita:
        kw.update(orbita)
    camera_orbita(c, alvo_cabeca, **kw)
    return c


@registrar("deus_anubis")
def deus_anubis(a):
    def construir(f: Figura):
        f.corpo(pele="ebano", saia="linho", ouro="ouro")
        f.braco("e", 6, 35, 0.55, "ebano")
        punho = f.braco("d", 8, 30, 0.55, "ebano")
        # cabeça de chacal: crânio, focinho alongado, orelhas altas
        f.esf("cranio", 0.1, (0, 0.0, 1.8), "ebano", (0.9, 1.0, 1.0))
        f.cil("focinho", 0.062, 0.26, (0, -0.07, 1.78), "ebano", r2=0.026, rot_=rot(90, 0, 0), seg=14)
        f.esf("nariz", 0.03, (0, -0.33, 1.78), "ebano")
        for lado in (-1, 1):
            f.cone(f"orelha{lado}", 0.05, 0.34, (lado * 0.065, 0.03, 1.88), "ebano", esc=(1, 0.35, 1))
            f.esf(f"olho{lado}", 0.016, (lado * 0.05, -0.085, 1.83), "ouro")
        f.cil("peitoral", 0.21, 0.07, (0, 0, 1.5), "ouro", r2=0.13, seg=28)
        f.toro("ankh_anel", 0.07, 0.014, tuple(punho + Vector((0.0, -0.1, 0.28))), "ouro", rot(90, 0, 0))
        f.cx("ankh_v", (0.03, 0.03, 0.3), tuple(punho + Vector((0.0, -0.1, 0.0))), "ouro")
        f.cx("ankh_h", (0.17, 0.03, 0.03), tuple(punho + Vector((0.0, -0.1, 0.15))), "ouro")
        return f.P(0, 0, 1.75)
    return _estatua_cena(a, ROTULO_DEUS + ": Anúbis", "Figura procedural: corpo humano com cabeça de chacal, iconografia egípcia geral.", construir)


@registrar("deus_ra")
def deus_ra(a):
    def construir(f: Figura):
        f.corpo(pele="pele", saia="linho", ouro="ouro")
        f.braco("e", 6, 35, 0.55, "pele")
        punho = f.braco("d", 8, 30, 0.55, "pele")
        # cabeça de falcão e disco solar com ureu
        f.esf("cabeca_falcao", 0.098, (0, 0, 1.8), "pele", (0.95, 1.05, 1.0))
        f.cone("bico", 0.04, 0.16, (0, -0.1, 1.79), "ouro", rot(100, 0, 0))
        for lado in (-1, 1):
            f.esf(f"olho{lado}", 0.016, (lado * 0.055, -0.08, 1.83), "ebano")
        f.cil("disco", 0.2, 0.035, (0, 0.0, 2.06), "ouro", rot_=rot(90, 0, 0), seg=40)
        f.cone("ureu", 0.022, 0.1, (0, -0.06, 1.93), "ouro")
        f.cil("peitoral", 0.21, 0.07, (0, 0, 1.5), "ouro", r2=0.13, seg=28)
        f.toro("ankh_anel", 0.07, 0.014, tuple(punho + Vector((0.0, -0.1, 0.28))), "ouro", rot(90, 0, 0))
        f.cx("ankh_v", (0.03, 0.03, 0.3), tuple(punho + Vector((0.0, -0.1, 0.0))), "ouro")
        f.cx("ankh_h", (0.17, 0.03, 0.03), tuple(punho + Vector((0.0, -0.1, 0.15))), "ouro")
        return f.P(0, 0, 1.85)
    return _estatua_cena(a, ROTULO_DEUS + ": Rá", "Figura procedural: cabeça de falcão com disco solar e ureu, iconografia egípcia geral.", construir,
                         chave=(1.0, 0.72, 0.4))


@registrar("deus_osiris")
def deus_osiris(a):
    def construir(f: Figura):
        # corpo mumiforme envolto em linho; pele verde; coroa atef branca; cajado e mangual cruzados
        f.cil("corpo", 0.15, 1.45, (0, 0, 0.1), "linho", r2=0.24, seg=24)
        f.esf("ombros", 0.24, (0, 0, 1.52), "linho", (1.0, 0.7, 0.55))
        f.cil("pescoco", 0.05, 0.14, (0, 0, 1.6), "verde")
        f.esf("cabeca", 0.115, (0, 0, 1.78), "verde", (0.92, 1.0, 1.12))
        f.cil("barba", 0.026, 0.28, (0, -0.1, 1.7), "azul", r2=0.04, rot_=rot(8, 0, 0), seg=10)
        f.cil("coroa", 0.075, 0.42, (0, 0, 1.88), "branco", r2=0.045, seg=20)
        f.esf("coroa_topo", 0.05, (0, 0, 2.32), "branco")
        for lado in (-1, 1):
            f.esf(f"pluma{lado}", 0.075, (lado * 0.115, 0, 2.0), "vermelho", (0.4, 0.35, 2.4))
        f.cil("cajado", 0.014, 0.9, (-0.1, -0.13, 1.0), "ouro", rot_=rot(0, -12, 0), seg=10)
        f.toro("cajado_gancho", 0.05, 0.012, (f.P(-0.19, -0.13, 1.93)[0], f.P(-0.19, -0.13, 1.93)[1], f.P(-0.19, -0.13, 1.93)[2]), "ouro", rot(90, 0, 0))
        f.cil("mangual", 0.014, 0.8, (0.1, -0.13, 1.05), "ouro", rot_=rot(0, 12, 0), seg=10)
        for k in range(3):
            f.cil(f"mangual_t{k}", 0.008, 0.2, (0.2 + 0.03 * k, -0.13, 1.7), "ouro", rot_=rot(0, 180, 0), seg=8)
        f.cil("peitoral", 0.21, 0.06, (0, 0, 1.52), "ouro", r2=0.14, seg=28)
        return f.P(0, 0, 1.9)
    return _estatua_cena(a, ROTULO_DEUS + ": Osíris", "Figura procedural: corpo mumiforme, coroa atef, cajado e mangual; iconografia egípcia geral.",
                         construir, chave=(0.85, 1.0, 0.7), aro=(0.4, 0.8, 0.6))
