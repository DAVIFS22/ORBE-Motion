"""Gera motion/data/mapa.json a partir do Natural Earth (domínio público): costas, rios e lagos do mundo mediterrâneo.

Uso: python motion/tools/preparar_mapas.py [pasta_com_geojson]
Sem argumento baixa os arquivos do repositório nvkelso/natural-earth-vector. Só biblioteca padrão.
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
CAIXA = (-32.0, 8.0, 62.0, 76.0)          # lon_min, lat_min, lon_max, lat_max
RIOS = {"Nile", "Damietta Branch", "Rosetta Branch", "Euphrates", "Tigris", "Jordan", "Danube", "Rhine"}
LAGOS = {"Sea of Galilee", "Dead Sea"}
TOL_TERRA, TOL_LINHA = 0.012, 0.01


def obter(nome, pasta):
    if pasta and (Path(pasta) / f"{nome}.geojson").is_file():
        return json.loads((Path(pasta) / f"{nome}.geojson").read_text(encoding="utf-8"))
    with urllib.request.urlopen(BASE + nome + ".geojson", timeout=120) as r:
        return json.loads(r.read())


def recortar(anel, caixa):
    """Sutherland–Hodgman contra o retângulo (serve para preenchimento par-ímpar de anéis de costa)."""
    x0, y0, x1, y1 = caixa
    def lado(pts, dentro, inter):
        saida = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if dentro(p):
                if not dentro(q):
                    saida.append(inter(q, p))
                saida.append(p)
            elif dentro(q):
                saida.append(inter(q, p))
        return saida
    def ix(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
    def iy(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y)
    pts = list(anel)
    for dentro, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)), (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        if not pts:
            break
        pts = lado(pts, dentro, inter)
    return pts


def douglas(pts, tol):
    if len(pts) < 3:
        return pts
    def dist(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = dx * dx + dy * dy
        if d == 0:
            return ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d))
        return ((p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2) ** 0.5
    manter = [False] * len(pts)
    manter[0] = manter[-1] = True
    pilha = [(0, len(pts) - 1)]
    while pilha:
        i, j = pilha.pop()
        mx, k = 0.0, -1
        for n in range(i + 1, j):
            d = dist(pts[n], pts[i], pts[j])
            if d > mx:
                mx, k = d, n
        if mx > tol:
            manter[k] = True
            pilha += [(i, k), (k, j)]
    return [p for p, m in zip(pts, manter) if m]


def plano(pts):
    return [round(v, 3) for p in pts for v in p]


def aneis_de(geom):
    if geom["type"] == "Polygon":
        return list(geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return [a for poli in geom["coordinates"] for a in poli]
    return []


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else None
    terra = []
    for ft in obter("ne_10m_land", pasta)["features"]:
        for anel in aneis_de(ft["geometry"]):
            xs = [p[0] for p in anel]
            ys = [p[1] for p in anel]
            if max(xs) < CAIXA[0] or min(xs) > CAIXA[2] or max(ys) < CAIXA[1] or min(ys) > CAIXA[3]:
                continue
            r = douglas(recortar([tuple(p) for p in anel], CAIXA), TOL_TERRA)
            if len(r) >= 3:
                terra.append(plano(r))
    rios = []
    for ft in obter("ne_10m_rivers_lake_centerlines", pasta)["features"]:
        nome = ft["properties"].get("name")
        if nome not in RIOS:
            continue
        g = ft["geometry"]
        linhas = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        rios.append({"nome": nome, "linhas": [plano(douglas([tuple(p[:2]) for p in ln], TOL_LINHA)) for ln in linhas]})
    lagos = []
    for ft in obter("ne_10m_lakes", pasta)["features"]:
        if ft["properties"].get("name") in LAGOS:
            lagos.append({"nome": ft["properties"]["name"], "aneis": [plano(douglas([tuple(p) for p in a], TOL_LINHA / 2)) for a in aneis_de(ft["geometry"])]})
    destino = Path(__file__).resolve().parent.parent / "data" / "mapa.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps({"caixa": CAIXA, "terra": terra, "rios": rios, "lagos": lagos,
                                   "fonte": "Natural Earth (domínio público), naturalearthdata.com; simplificado para este projeto"},
                                  separators=(",", ":")), encoding="utf-8")
    print(f"{destino}: {len(terra)} anéis de terra, {len(rios)} rios, {len(lagos)} lagos, {destino.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
