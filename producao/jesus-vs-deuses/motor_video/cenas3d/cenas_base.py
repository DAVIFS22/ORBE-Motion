"""Base das cenas: registro, objeto de cena animada e a construção das figuras (estátuas) estilizadas."""

from __future__ import annotations

import math

import numpy as np
from mathutils import Vector

import lib3d as L

CENAS: dict = {}

ROTULO_RECONSTRUCAO = "Reconstrução artística em 3D, não é registro histórico"
ROTULO_DEUS = "Representação artística estilizada em 3D, não é registro histórico"


class Cena3D:
    def __init__(self, rotulo: str, nota: str = ""):
        self.rotulo, self.nota = rotulo, nota
        self._anim = []

    def animar(self, f):
        self._anim.append(f)

    def atualizar(self, p: float, t: float):
        for f in self._anim:
            f(p, t)


def registrar(nome: str):
    def deco(f):
        CENAS[nome] = f
        return f
    return deco


def rot(x=0.0, y=0.0, z=0.0):
    return (math.radians(x), math.radians(y), math.radians(z))


# ------------------------------------------------------------------ figuras ---

class Figura:
    """Escultura estilizada montada com primitivas. Origem no centro dos pés; a figura olha para -Y."""

    def __init__(self, nome, loc, escala, mats):
        self.nome, self.base, self.s, self.m = nome, Vector(loc), escala, mats
        self.partes = []

    def P(self, x, y, z):
        return self.base + Vector((x, y, z)) * self.s

    def add(self, obj):
        self.partes.append(obj)
        return obj

    def cil(self, n, r, h, p, mat, r2=None, rot_=(0, 0, 0), seg=20, esc=None):
        o = L.cilindro(f"{self.nome}_{n}", r * self.s, h * self.s, self.P(*p), self.m[mat], seg,
                       None if r2 is None else r2 * self.s, True, rot_)
        if esc:
            o.scale = esc
        return self.add(o)

    def esf(self, n, r, p, mat, esc=(1, 1, 1), rot_=(0, 0, 0)):
        return self.add(L.esfera(f"{self.nome}_{n}", r * self.s, self.P(*p), self.m[mat], esc, 20, 12, rot_))

    def cone(self, n, r, h, p, mat, rot_=(0, 0, 0), esc=None):
        o = L.cone(f"{self.nome}_{n}", r * self.s, h * self.s, self.P(*p), self.m[mat], 20, rot_)
        if esc:
            o.scale = esc
        return self.add(o)

    def cx(self, n, dim, p, mat, rot_=(0, 0, 0), bisel=0.0):
        return self.add(L.caixa(f"{self.nome}_{n}", tuple(d * self.s for d in dim), self.P(*p), self.m[mat], rot_, bisel=bisel * self.s))

    def toro(self, n, R, r, p, mat, rot_=(0, 0, 0)):
        import bpy
        bpy.ops.mesh.primitive_torus_add(major_radius=R * self.s, minor_radius=r * self.s, major_segments=28, minor_segments=10,
                                         location=self.P(*p), rotation=rot_)
        o = bpy.context.object
        o.name = f"{self.nome}_{n}"
        o.data.materials.append(self.m[mat])
        for poly in o.data.polygons:
            poly.use_smooth = True
        return self.add(o)

    # corpo humano de base --------------------------------------------------
    def corpo(self, pele="pele", saia="linho", ouro="ouro", saia_longa=False, torso_nu=True):
        if saia_longa:
            self.cil("saia", 0.25, 1.2, (0, 0, 0.05), saia, r2=0.19, rot_=(0, 0, 0))
        else:
            self.cil("perna_e", 0.075, 0.85, (-0.1, 0, 0.0), pele)
            self.cil("perna_d", 0.075, 0.85, (0.1, 0, 0.0), pele)
            self.cil("saia", 0.24, 0.6, (0, 0, 0.5), saia, r2=0.19)
        self.cil("torso", 0.18, 0.62, (0, 0, 1.0), pele if torso_nu else saia, r2=0.215, esc=(1, 0.66, 1))
        self.esf("ombro_e", 0.085, (-0.245, 0, 1.58), pele)
        self.esf("ombro_d", 0.085, (0.245, 0, 1.58), pele)
        self.cil("pescoco", 0.05, 0.14, (0, 0, 1.58), pele)
        self.cil("colar", 0.205, 0.06, (0, 0, 1.52), ouro, r2=0.13, seg=28)

    def braco(self, lado, ang_ombro=0.0, ang_cotovelo=0.0, comp=0.5, mat="pele"):
        """Braço em duas peças (braço + antebraço). Ângulos em graus; 0 = pendurado."""
        sx = -1 if lado == "e" else 1
        ombro = Vector((sx * 0.245, 0, 1.58))
        a = math.radians(ang_ombro)
        d1 = Vector((math.sin(a) * 0.0, -math.sin(a), -math.cos(a)))  # gira para a frente (-Y)
        L1, L2 = comp * 0.55, comp * 0.5
        cotovelo = ombro + d1 * L1
        a2 = math.radians(ang_ombro + ang_cotovelo)
        d2 = Vector((0, -math.sin(a2), -math.cos(a2)))
        punho = cotovelo + d2 * L2
        for nome, ini, fim in (("braco", ombro, cotovelo), ("antebraco", cotovelo, punho)):
            v = fim - ini
            q = v.to_track_quat("Z", "Y")
            r = 0.05 if nome == "braco" else 0.042
            self.cil(f"{nome}_{lado}", r, v.length, tuple(ini), mat, r2=r * 0.85, rot_=tuple(q.to_euler()), seg=14)
        self.esf(f"mao_{lado}", 0.05, tuple(punho), mat)
        return punho

    def cabeca(self, mat="pele", z=1.78):
        self.esf("cabeca", 0.115, (0, 0, z), mat, (0.92, 1.0, 1.12))
        return Vector((0, 0, z))


def materiais_estatua(escuro=False):
    """Conjunto de materiais para esculturas: pedra, ouro, linho, pele pintada."""
    return {
        "pedra": L.material_pedra("pedra", (0.55, 0.5, 0.44), (0.72, 0.66, 0.58), 14, 0.7, 0.15),
        "marmore": L.material_pedra("marmore", (0.78, 0.76, 0.72), (0.93, 0.92, 0.9), 6, 0.35, 0.05),
        "ouro": L.material("ouro", (1.0, 0.72, 0.25), 0.28, 1.0),
        "linho": L.material("linho", (0.9, 0.86, 0.76), 0.85),
        "ebano": L.material("ebano", (0.03, 0.03, 0.035), 0.4, 0.0),
        "pele": L.material("pele", (0.45, 0.2, 0.1), 0.6),
        "verde": L.material("verde", (0.09, 0.28, 0.14), 0.55),
        "azul": L.material("azul", (0.08, 0.18, 0.5), 0.5),
        "vermelho": L.material("vermelho", (0.55, 0.06, 0.05), 0.55),
        "branco": L.material("branco", (0.92, 0.9, 0.86), 0.5),
        "roxo": L.material("roxo", (0.1, 0.03, 0.14), 0.7),
        "cinza": L.material("cinza", (0.35, 0.36, 0.38), 0.75),
        "ferro": L.material("ferro", (0.22, 0.23, 0.25), 0.4, 1.0),
    }


def cor_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ------------------------------------------------------------------ palcos ---

def palco_estatua(c: Cena3D, mats: dict, parede, piso, cor_chave=(1.0, 0.78, 0.55), cor_aro=(0.55, 0.7, 1.0), neblina=0.009,
                  altura_pedestal=0.95, energia=900.0, cor_fundo=(0.01, 0.008, 0.01), cor_porta=(1.0, 0.72, 0.4)):
    """Sala escura: pedestal diante de uma porta iluminada (silhueta com contraluz), névoa, poeira e luz principal suave."""
    L.ceu_gradiente(cor_fundo, (0.025, 0.018, 0.016), 1.0)
    L.neblina(neblina, (0.8, 0.7, 0.6), 0.65, (0, 3, 5), (24, 24, 11))
    L.caixa("piso", (30, 30, 0.4), (0, 0, -0.2), piso)
    # parede de fundo com uma porta alta; atrás dela, um painel luminoso (luz do dia / fogo)
    L.caixa("parede_e", (6.0, 0.9, 11), (-5.2, 6.0, 0), parede, base_no_chao=True)
    L.caixa("parede_d", (6.0, 0.9, 11), (5.2, 6.0, 0), parede, base_no_chao=True)
    L.caixa("parede_alta", (4.6, 0.9, 3.0), (0, 6.0, 8.0), parede, base_no_chao=True)
    L.caixa("parede_lateral_e", (0.9, 14, 11), (-8.2, 0.0, 0), parede, base_no_chao=True)
    L.caixa("parede_lateral_d", (0.9, 14, 11), (8.2, 0.0, 0), parede, base_no_chao=True)
    luz_porta = L.material_emissivo("porta_luz", cor_porta, 1.6)
    L.caixa("porta_luz", (5.0, 0.2, 9.0), (0, 8.2, 0), luz_porta, base_no_chao=True)
    L.luz_area((0, 7.2, 4.5), (0, -2, 3.0), 4.4, 8.0, 700.0, cor_porta, "luz_da_porta").visible_camera = False
    L.caixa("pedestal", (1.9, 1.9, altura_pedestal), (0, 0, 0), parede, base_no_chao=True, bisel=0.04)
    topo = altura_pedestal
    alvo = (0, 0, topo + 1.6)
    L.luz_spot((-3.8, -5.2, 6.4), alvo, energia, cor_chave, 26.0, 0.6, "chave")
    L.luz_area((-5.5, 2.5, 3.5), alvo, 2.0, 4.0, 400.0, cor_aro, "contraluz_e")
    L.luz_area((5.5, 2.5, 3.5), alvo, 2.0, 4.0, 400.0, cor_chave, "contraluz_d")
    p = L.Poeira(150, (-4.5, -3.5, 0.2), (4.5, 6.0, 7.0), 0.007, 3.5, (1.0, 0.9, 0.75), (0.02, 0.0, 0.025), 5)
    c.animar(lambda t_, t: p.atualizar(t))
    return topo


def camera_orbita(c: Cena3D, alvo, r=(6.0, 4.6), az=(-36.0, 28.0), h=(1.9, 2.4), lente=50.0, fstop=2.8, alvo_dz=(0.0, 0.0)):
    cam = L.criar_camera(lente, fstop)
    alvo = Vector(alvo)

    def f(p, t):
        e = L.facilitar(p)
        rr = r[0] + (r[1] - r[0]) * e
        a = math.radians(az[0] + (az[1] - az[0]) * e)
        hh = h[0] + (h[1] - h[0]) * e
        pos = alvo + Vector((rr * math.sin(a), -rr * math.cos(a), hh - alvo.z))
        L.posicionar_camera(cam, pos, alvo + Vector((0, 0, alvo_dz[0] + (alvo_dz[1] - alvo_dz[0]) * e)))
    c.animar(f)
    return cam
