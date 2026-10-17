"""Grécia antiga (templo dórico, Zeus, Hades) e tradições nórdicas (fiorde, Odin, Ragnarök)."""

from __future__ import annotations

import math

import numpy as np
from mathutils import Vector

import lib3d as L
from cenas_base import (ROTULO_DEUS, ROTULO_RECONSTRUCAO, Cena3D, Figura, camera_orbita, materiais_estatua, palco_estatua, registrar,
                        rot)
from cenas_egito import _estatua_cena


# ================================================================== GRÉCIA ===

@registrar("templo_grego")
def templo_grego(a):
    c = Cena3D(ROTULO_RECONSTRUCAO + ": templo grego (ordem dórica)",
               "Templo períptero procedural de proporções inspiradas na arquitetura grega clássica; sem cores ou inscrições inventadas.")
    marmore = L.material_pedra("marmore", (0.80, 0.77, 0.70), (0.95, 0.93, 0.88), 5, 0.45, 0.12)
    base = L.material_pedra("calcario", (0.62, 0.57, 0.48), (0.80, 0.74, 0.63), 9, 0.8, 0.3)
    terra = L.material_pedra("colina", (0.06, 0.13, 0.04), (0.26, 0.34, 0.12), 6, 0.95, 0.35)
    L.ceu(14, 100, poeira=1.6, ar=1.0, forca=0.05)
    L.sol(13, 98, 4.0, (1.0, 0.8, 0.58), 0.7)
    L.neblina(0.0016, (0.9, 0.78, 0.65), 0.7, (0, 0, 60), (700, 700, 140))
    nx = 120
    xs = ys = np.linspace(-260, 260, nx)
    ruido = L.ruido2d(nx, nx, 7, 5, a.semente)

    def altura(X, Y):
        d = np.sqrt(X ** 2 + (Y * 0.8) ** 2)
        colina = 24 * np.exp(-(d / 70) ** 2)
        plat = np.minimum(colina, 18.0)  # platô aplanado no topo
        return -1.0 + plat + 9 * ruido * np.clip(d / 60, 0, 1) + 22 * np.clip((d - 160) / 100, 0, 2) * ruido
    terreno_ = L.terreno("colina", xs, ys, altura, terra)
    mar = L.caixa("mar", (2200, 2200, 0.2), (0, 0, -3.0), L.material_agua("mar", (0.03, 0.12, 0.2), 0.04, 0.03, 8))
    zt = 17.0  # altura do platô
    nc_x, nc_y = 6, 11
    esp, r, hc = 3.6, 0.66, 6.6
    larg, comp = (nc_x - 1) * esp, (nc_y - 1) * esp
    for k in range(3):  # degraus
        L.caixa(f"degrau{k}", (larg + 3 + (3 - k) * 1.4, comp + 3 + (3 - k) * 1.4, 0.34), (0, 0, zt + k * 0.34), base, base_no_chao=True)
    z0 = zt + 1.02
    posicoes = []
    for i in range(nc_x):
        posicoes += [(-larg / 2 + i * esp, -comp / 2), (-larg / 2 + i * esp, comp / 2)]
    for j in range(1, nc_y - 1):
        posicoes += [(-larg / 2, -comp / 2 + j * esp), (larg / 2, -comp / 2 + j * esp)]
    for n, (x, y) in enumerate(posicoes):
        L.cilindro(f"col{n}", r, hc, (x, y, z0), marmore, 20, r * 0.78, False)
        L.cilindro(f"eq{n}", r * 0.78, 0.35, (x, y, z0 + hc), marmore, 20, r * 1.05)
        L.caixa(f"aba{n}", (r * 2.5, r * 2.5, 0.3), (x, y, z0 + hc + 0.35), marmore, base_no_chao=True)
    zt2 = z0 + hc + 0.65
    L.caixa("arq_f", (larg + 2.4, 1.3, 1.0), (0, -comp / 2, zt2), marmore, base_no_chao=True)
    L.caixa("arq_t", (larg + 2.4, 1.3, 1.0), (0, comp / 2, zt2), marmore, base_no_chao=True)
    L.caixa("arq_e", (1.3, comp + 2.4, 1.0), (-larg / 2, 0, zt2), marmore, base_no_chao=True)
    L.caixa("arq_d", (1.3, comp + 2.4, 1.0), (larg / 2, 0, zt2), marmore, base_no_chao=True)
    for k, x in enumerate(np.arange(-larg / 2 - 0.5, larg / 2 + 0.6, 1.8)):  # tríglifos (friso dórico)
        for y in (-comp / 2, comp / 2):
            L.caixa(f"trig{k}{y}", (0.6, 1.36, 1.0), (x, y, zt2 + 1.0), marmore, base_no_chao=True)
    L.caixa("friso_f", (larg + 2.4, 1.2, 1.0), (0, -comp / 2, zt2 + 1.0), base, base_no_chao=True)
    L.caixa("cornija", (larg + 3.6, comp + 3.6, 0.4), (0, 0, zt2 + 2.0), marmore, base_no_chao=True)
    for y, sgn in ((-comp / 2 - 0.7, 1), (comp / 2 + 0.7, -1)):
        fr = L.prisma_triangular(f"frontao{sgn}", larg + 3.2, 2.6, 1.2, (0, y, zt2 + 2.4), marmore)
    L.caixa("telhado", (larg + 3.2, comp + 3.0, 0.4), (0, 0, zt2 + 3.0), base, base_no_chao=True, rot=(0, 0, 0)) if False else None
    for sx in (-1, 1):
        L.caixa(f"naos_l{sx}", (0.7, comp - 6, hc), (sx * (larg / 2 - 3.2), 0, z0), marmore, base_no_chao=True)
    L.caixa("naos_f", (larg - 6, 0.7, hc), (0, comp / 2 - 6, z0), marmore, base_no_chao=True)
    # ciprestes e oliveiras ao redor
    rng = np.random.default_rng(a.semente)
    cipreste = L.material("cipreste", (0.04, 0.12, 0.05), 0.9)
    base_c = L.cone("cip0", 1.0, 7.5, (0, 0, -100), cipreste, 10)
    Zg = altura(*np.meshgrid(xs, ys))
    for k in range(70):
        x, y = rng.uniform(-110, 110), rng.uniform(-110, 110)
        if abs(x) < 38 and abs(y) < 50:
            continue
        z = L.amostrar_altura(xs, ys, Zg, x, y)
        if z < 0:
            continue
        L.duplicar(base_c, f"cip{k}", (x, y, z - 0.2), None, (rng.uniform(0.7, 1.2),) * 2 + (rng.uniform(0.8, 1.5),))
    poeira = L.Poeira(90, (-40, -50, zt + 1), (40, 50, zt + 14), 0.03, 4.0, (1.0, 0.9, 0.75), (0.04, 0.02, 0.01), 7)
    cam = L.criar_camera(34.0, None)
    alvo = Vector((0, 0, zt + 5.5))

    def anim(p, t):
        e = L.facilitar(p)
        ang = math.radians(-62 + 105 * e)
        raio = 78 - 18 * e
        pos = alvo + Vector((raio * math.sin(ang), -raio * math.cos(ang), 2.0 + 11 * (1 - e) + 5 * e))
        L.posicionar_camera(cam, pos, alvo + Vector((0, 0, -1.0 + 0.5 * e)))
        poeira.atualizar(t)
    c.animar(anim)
    return c


@registrar("deus_zeus")
def deus_zeus(a):
    def construir(f: Figura):
        f.cil("tunica", 0.26, 1.25, (0, 0, 0.0), "marmore", r2=0.17, seg=28)           # manto longo (himation)
        f.cil("torso", 0.18, 0.5, (0, 0, 1.05), "marmore", r2=0.22, esc=(1, 0.7, 1))
        f.esf("ombro_e", 0.09, (-0.25, 0, 1.55), "marmore")
        f.esf("ombro_d", 0.09, (0.25, 0, 1.55), "marmore")
        f.braco("e", 8, 40, 0.55, "marmore")
        # braço direito erguido com o raio
        f.cil("braco_d", 0.052, 0.5, (0.25, 0, 1.55), "marmore", r2=0.045, rot_=rot(0, 38, 0), seg=14)
        f.esf("mao_d", 0.055, (0.25 + 0.5 * math.sin(math.radians(38)), 0, 1.55 + 0.5 * math.cos(math.radians(38))), "marmore")
        base = Vector((0.25 + 0.5 * math.sin(math.radians(38)), 0, 1.55 + 0.5 * math.cos(math.radians(38))))
        for k in range(4):  # raio em zigue-zague
            off = Vector((0.045 * (-1) ** k, 0, 0.07 * k))
            f.cx(f"raio{k}", (0.03, 0.03, 0.14), tuple(base + off + Vector((0, 0, 0.02))), "ouro", rot(0, 18 * (-1) ** k, 0))
        f.cil("pescoco", 0.055, 0.12, (0, 0, 1.6), "marmore")
        f.esf("cabeca", 0.118, (0, 0, 1.78), "marmore", (0.92, 1.0, 1.1))
        f.esf("barba", 0.095, (0, -0.045, 1.69), "marmore", (1.0, 0.8, 1.2))
        for k in range(7):  # cabelo cacheado
            ang = math.radians(-70 + k * 23)
            f.esf(f"cacho{k}", 0.05, (0.115 * math.sin(ang), 0.03 + 0.04 * abs(math.cos(ang)), 1.86 + 0.02 * math.cos(ang)), "marmore")
        return f.P(0, 0, 1.75)
    return _estatua_cena(a, ROTULO_DEUS + ": Zeus", "Figura procedural em mármore: barba, himation e raio; iconografia grega geral.", construir,
                         parede_cor=((0.5, 0.46, 0.4), (0.75, 0.7, 0.62)), chave=(1.0, 0.9, 0.78), aro=(0.55, 0.7, 1.0))


@registrar("deus_hades")
def deus_hades(a):
    def fundo(c, mats):
        # Cérbero (estilizado): corpo + três cabeças, aos pés do trono
        f = Figura("cerbero", (1.5, -0.9, 0.95), 1.2, mats)
        f.esf("corpo", 0.28, (0, 0, 0.3), "ebano", (1.5, 0.8, 0.8))
        for k, dx in enumerate((-0.16, 0.0, 0.16)):
            f.esf(f"cabeca{k}", 0.09, (dx, -0.38, 0.42), "ebano", (1, 1.1, 1))
            f.cil(f"foc{k}", 0.045, 0.14, (dx, -0.43, 0.4), "ebano", r2=0.025, rot_=rot(90, 0, 0), seg=10)
            f.cone(f"orelha{k}", 0.03, 0.09, (dx, -0.36, 0.5), "ebano")
        for dx in (-0.2, 0.2):
            f.cil(f"pata{dx}", 0.035, 0.3, (dx, -0.2, 0.0), "ebano")
            f.cil(f"pata_t{dx}", 0.035, 0.3, (dx, 0.25, 0.0), "ebano")

    def construir(f: Figura):
        # trono (bloco + encosto) e figura sentada
        f.cx("assento", (0.9, 0.8, 0.5), (0, 0.05, 0.25), "pedra")
        f.cx("encosto", (0.9, 0.18, 1.4), (0, 0.42, 0.95), "pedra")
        f.cx("braco_trono_e", (0.14, 0.7, 0.34), (-0.5, 0.05, 0.62), "pedra")
        f.cx("braco_trono_d", (0.14, 0.7, 0.34), (0.5, 0.05, 0.62), "pedra")
        z = 0.5
        f.cil("coxa_e", 0.085, 0.45, (-0.13, 0.05, z + 0.1), "roxo", rot_=rot(90, 0, 0), seg=14)
        f.cil("coxa_d", 0.085, 0.45, (0.13, 0.05, z + 0.1), "roxo", rot_=rot(90, 0, 0), seg=14)
        f.cil("canela_e", 0.07, 0.5, (-0.13, -0.4, z - 0.4), "roxo", seg=14)
        f.cil("canela_d", 0.07, 0.5, (0.13, -0.4, z - 0.4), "roxo", seg=14)
        f.cil("tunica", 0.2, 0.7, (0, 0.0, z + 0.12), "roxo", r2=0.24, esc=(1, 0.8, 1))
        f.cil("capa", 0.28, 0.9, (0, 0.16, z + 0.2), "ebano", r2=0.18, esc=(1.2, 0.35, 1))
        f.esf("ombro_e", 0.085, (-0.25, 0, z + 0.88), "roxo")
        f.esf("ombro_d", 0.085, (0.25, 0, z + 0.88), "roxo")
        f.cil("braco_e", 0.05, 0.5, (-0.25, 0, z + 0.88), "roxo", r2=0.045, rot_=rot(70, 0, 0), seg=12)
        f.cil("braco_d", 0.05, 0.5, (0.25, 0, z + 0.88), "roxo", r2=0.045, rot_=rot(35, 0, 0), seg=12)
        f.cil("pescoco", 0.05, 0.12, (0, 0, z + 0.88), "cinza")
        f.esf("cabeca", 0.115, (0, 0, z + 1.07), "cinza", (0.92, 1.0, 1.1))
        f.esf("barba", 0.09, (0, -0.045, z + 0.98), "ebano", (1.0, 0.8, 1.2))
        f.cil("coroa", 0.11, 0.08, (0, 0, z + 1.17), "ferro", r2=0.13, seg=20)
        for k in range(5):
            f.cone(f"ponta{k}", 0.02, 0.09, (0.1 * math.cos(k * 1.26), 0.1 * math.sin(k * 1.26), z + 1.25), "ferro")
        # bidente (cetro de duas pontas)
        f.cil("bidente", 0.012, 1.9, (0.4, -0.45, 0.0), "ferro", seg=10)
        for dx in (-0.05, 0.05):
            f.cone(f"dente{dx}", 0.013, 0.18, (0.4 + dx, -0.45, 1.9), "ferro")
        f.cil("traves", 0.012, 0.12, (0.35, -0.45, 1.88), "ferro", rot_=rot(0, 90, 0), seg=8)
        return f.P(0, 0, z + 0.6)
    return _estatua_cena(a, ROTULO_DEUS + ": Hades", "Figura procedural entronizada com bidente e Cérbero; iconografia grega geral.", construir,
                         parede_cor=((0.12, 0.1, 0.1), (0.26, 0.2, 0.2)), chave=(1.0, 0.42, 0.18), aro=(0.45, 0.2, 0.7),
                         escala=1.5, fundo_extra=fundo, orbita=dict(r=(9.5, 8.0), alvo_dz=(-0.4, -0.4)))


# ================================================================== NÓRDICO ===

def _vale(a, nx=150, ny=190, larg=1400, comp=1800, altura_max=380):
    xs, ys = np.linspace(-larg / 2, larg / 2, nx), np.linspace(-comp / 2, comp / 2, ny)
    r = L.ruido2d(nx, ny, 6, 6, a.semente)
    X, Y = np.meshgrid(xs, ys)
    cristas = 1 - np.abs(2 * r - 1)
    parede = np.clip((np.abs(X) - 120) / 380, 0, 1.4) ** 1.2
    Z = -6 + altura_max * parede * (0.35 + 0.65 * cristas) + 30 * r
    Z = np.where(np.abs(X) < 130, -6 + 8 * r, Z)
    return xs, ys, Z


@registrar("fiorde_nordico")
def fiorde_nordico(a):
    c = Cena3D(ROTULO_RECONSTRUCAO + ": fiorde nórdico", "Paisagem procedural (montanhas, floresta e água) inspirada nos fiordes escandinavos.")
    rocha = L.material_pedra("rocha", (0.08, 0.08, 0.09), (0.28, 0.27, 0.27), 4, 0.9, 0.5)
    L.ceu(7, 195, poeira=1.2, ar=1.1, forca=0.05)
    L.sol(6, 200, 3.4, (1.0, 0.72, 0.5), 0.7)
    L.neblina(0.0011, (0.78, 0.82, 0.9), 0.7, (0, 0, 120), (1500, 1900, 360))
    xs, ys, Z = _vale(a)
    L.malha_de_grade("montanhas", xs, ys, Z, rocha)
    L.caixa("agua", (3000, 3000, 0.2), (0, 0, -0.1), L.material_agua("agua", (0.012, 0.03, 0.05), 0.03, 0.02, 20))
    rng = np.random.default_rng(a.semente)
    pinho = L.material("pinho", (0.015, 0.05, 0.03), 0.9)
    arv = L.cone("pinho0", 3.2, 15, (0, 0, -300), pinho, 8)
    colocados = 0
    for _ in range(2200):
        x, y = rng.uniform(-650, 650), rng.uniform(-850, 850)
        z = L.amostrar_altura(xs, ys, Z, x, y)
        if 3 < z < 130 and colocados < 600:
            L.duplicar(arv, f"p{colocados}", (x, y, z - 0.5), None, (rng.uniform(0.7, 1.5),) * 2 + (rng.uniform(0.8, 1.8),))
            colocados += 1
    cam = L.criar_camera(30.0, None)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((-30 + 70 * math.sin(p * 1.7), -760 + 1050 * e, 34 - 10 * e + 8 * math.sin(p * 2.3)))
        L.posicionar_camera(cam, pos, pos + Vector((20 * math.sin(p * 1.2), 300, 16)), 0.8 * math.sin(p * 2.0))
    c.animar(anim)
    return c


@registrar("deus_odin")
def deus_odin(a):
    c = Cena3D(ROTULO_DEUS + ": Odin (tradição nórdica)",
               "Figura procedural ao crepúsculo: manto, chapéu de abas largas, lança e corvos; iconografia nórdica geral.")
    mats = materiais_estatua()
    rocha = L.material_pedra("rocha", (0.05, 0.05, 0.055), (0.24, 0.23, 0.22), 3, 0.9, 0.7)
    L.ceu_gradiente((0.015, 0.025, 0.07), (0.95, 0.42, 0.15), 1.0, (0.1, 0.06, 0.05))
    L.neblina(0.0035, (0.8, 0.6, 0.5), 0.6, (0, 40, 30), (500, 500, 120))
    nx = 120
    xs = ys = np.linspace(-120, 120, nx)
    r = L.ruido2d(nx, nx, 6, 6, a.semente)

    def altura(X, Y):
        d = np.sqrt(X ** 2 + (Y + 2) ** 2)
        base = -30 + 30 * np.clip(1 - np.sqrt(X ** 2 + (Y * 0.6) ** 2) / 160, 0, 1) ** 0.5 + 8 * r
        pico = 26 * np.exp(-(d ** 2) / 380)
        plato = 23.0 + 0.4 * r  # platô de pedra (raio ~10 m) onde a figura fica
        t = np.clip((d - 10.0) / 16.0, 0, 1)
        mist = plato * (1 - t * t * (3 - 2 * t)) + (base + pico) * (t * t * (3 - 2 * t))
        return mist
    L.terreno("penhasco", xs, ys, altura, rocha)
    topo = float(altura(np.array([[0.0]]), np.array([[0.0]]))[0, 0])
    L.luz_area((9, 60, topo + 14), (0, 0, topo + 2), 28, 8, 90000.0, (1.0, 0.5, 0.2), "luz_poente").visible_camera = False
    L.luz_area((-14, -16, topo + 12), (0, 0, topo + 3), 6, 6, 5000.0, (0.45, 0.6, 1.0), "luz_lua")
    f = Figura("odin", (0, 0, topo), 1.45, mats)
    f.cil("capa", 0.34, 1.55, (0, 0.02, 0.0), "cinza", r2=0.1, seg=26)
    f.cil("capa_t", 0.3, 1.4, (0, 0.14, 0.05), "ebano", r2=0.08, esc=(1.1, 0.4, 1))
    f.esf("ombros", 0.2, (0, 0, 1.5), "cinza", (1.2, 0.7, 0.55))
    f.esf("cabeca", 0.105, (0, -0.01, 1.7), "pele", (0.92, 1.0, 1.1))
    f.esf("barba", 0.1, (0, -0.06, 1.6), "branco", (1.0, 0.85, 1.4))
    f.cil("chapeu_aba", 0.26, 0.025, (0, 0, 1.79), "ebano", seg=28)
    f.cil("chapeu", 0.13, 0.2, (0, 0, 1.8), "ebano", r2=0.08, seg=20)
    f.esf("tapa_olho", 0.025, (0.04, -0.1, 1.72), "ebano")
    f.cil("lanca", 0.013, 2.5, (0.34, -0.1, 0.0), "ferro", seg=10)
    f.cone("ponta_lanca", 0.03, 0.22, (0.34, -0.1, 2.5), "ferro")
    f.cil("braco", 0.05, 0.55, (0.24, -0.04, 1.5), "cinza", r2=0.045, rot_=rot(0, -16, 0), seg=12)
    for k, (x, z, y) in enumerate(((-0.22, 1.66, -0.02), (0.78, 0.55, -0.4))):   # dois corvos
        f.esf(f"corvo{k}", 0.065, (x, y, z), "ebano", (1.5, 0.75, 0.8))
        f.esf(f"corvo_cab{k}", 0.036, (x - 0.09, y - 0.02, z + 0.03), "ebano")
        f.cone(f"corvo_bico{k}", 0.012, 0.06, (x - 0.12, y - 0.02, z + 0.03), "ebano", rot(0, 90, 0))
    poeira = L.Poeira(110, (-6, -8, topo), (6, 6, topo + 9), 0.02, 3.0, (1.0, 0.7, 0.5), (0.1, 0.0, 0.02), 6)
    cam = L.criar_camera(40.0, 3.0)
    alvo = f.P(0, 0, 1.0)
    Zg = altura(*np.meshgrid(xs, ys))

    def anim(p, t):
        e = L.facilitar(p)
        ang = math.radians(-30 + 50 * e)
        raio = 9.0 - 2.0 * e
        pos = alvo + Vector((raio * math.sin(ang), -raio * math.cos(ang), 0.4 + 0.5 * e))
        pos.z = max(pos.z, L.amostrar_altura(xs, ys, Zg, pos.x, pos.y) + 1.7)
        L.posicionar_camera(cam, pos, alvo + Vector((0, 0, 0.4)))
        poeira.atualizar(t)
    c.animar(anim)
    return c


@registrar("ragnarok")
def ragnarok(a):
    c = Cena3D(ROTULO_RECONSTRUCAO.replace("Reconstrução artística em 3D", "Representação artística do Ragnarök (mitologia nórdica)"),
               "Cena mitológica estilizada (fim de uma era na tradição nórdica); não é registro histórico.")
    nx, ny = 150, 190
    xs, ys = np.linspace(-300, 300, nx), np.linspace(-200, 700, ny)
    r = L.ruido2d(nx, ny, 9, 6, a.semente)
    r2 = L.ruido2d(nx, ny, 5, 4, a.semente + 3)
    X, Y = np.meshgrid(xs, ys)
    cratera = np.exp(-((X ** 2 + (Y - 420) ** 2) / 9000))
    Z = -5 + 75 * np.clip(1 - np.abs(Y - 420) / 420, 0, 1) * r + 40 * r2 - 85 * cratera
    lava = np.clip((0.55 - r) * 3.4 + cratera * 1.8, 0, 1)  # fissuras incandescentes nos vales do ruído
    cores = np.stack([lava, lava, lava, np.ones_like(lava)], axis=2)
    L.malha_de_grade("terra_ardente", xs, ys, Z, L.material_lava(), cores)
    L.ceu_gradiente((0.006, 0.0, 0.0), (0.55, 0.1, 0.03), 0.8, (0.05, 0.012, 0.005))
    L.neblina(0.0011, (0.9, 0.3, 0.12), 0.5, (0, 250, 60), (800, 1100, 200))
    L.luz_area((0, 430, 30), (0, 200, 0), 80, 80, 6.0e5, (1.0, 0.35, 0.08), "brilho_cratera").visible_camera = False
    brasas = L.Poeira(260, (-110, 40, 0), (110, 420, 90), 0.5, 14.0, (1.0, 0.45, 0.1), (0.5, 3.0, 5.0), 3)
    cam = L.criar_camera(28.0, None)

    def anim(p, t):
        e = L.facilitar(p)
        pos = Vector((12 * math.sin(p * 2.0), -120 + 330 * e, 38 + 16 * (1 - e) + 4 * math.sin(p * 4)))
        L.posicionar_camera(cam, pos, Vector((0, 430, 36)), 0.6 * math.sin(p * 3))
        brasas.atualizar(t)
    c.animar(anim)
    return c
