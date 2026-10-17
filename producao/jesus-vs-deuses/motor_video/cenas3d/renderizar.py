"""Ponto de entrada executado pelo Blender: monta uma cena e renderiza a sequência de quadros (PNG).

Uso (o motor chama isto pela `blender_bridge`):
    blender -b --python renderizar.py -- --cena templo_egipcio --saida DIR --duracao 8 --fps 24 ...
    python  renderizar.py -- ...            (Python com o módulo `bpy` instalado)

Quadros já existentes na pasta de saída são pulados: um render interrompido continua de onde parou.
"""

import argparse
import json
import math
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)


def _argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--cena", required=False)
    ap.add_argument("--saida", required=False)
    ap.add_argument("--duracao", type=float, default=6.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--largura", type=int, default=960)
    ap.add_argument("--altura", type=int, default=540)
    ap.add_argument("--amostras", type=int, default=12)
    ap.add_argument("--rebotes", type=int, default=3)
    ap.add_argument("--motor", default="CYCLES")
    ap.add_argument("--dispositivo", default="CPU")
    ap.add_argument("--semente", type=int, default=7)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--quadro", type=float, default=None, help="renderiza só um quadro, no progresso 0..1 da cena")
    ap.add_argument("--listar", action="store_true")
    return ap.parse_args(argv)


def _recursos_externos(L, params):
    """Aplica HDRI e modelos glTF/OBJ/FBX opcionais (ex.: Poly Haven, CC0) pedidos nos parâmetros da cena.

    Um recurso que não carrega é ignorado com aviso: o render continua com o céu e os objetos gerados por código.
    Devolve (usados, ignorados) para o meta.json.
    """
    import bpy
    usados, ignorados = {}, []
    if params.get("hdri"):
        mundo = bpy.context.scene.world
        try:
            L.ceu_hdri(params["hdri"], params.get("hdri_rotacao", 0.0), params.get("hdri_forca", 1.0))
            usados["hdri"] = os.path.basename(params["hdri"])
        except Exception as e:  # noqa: BLE001 - qualquer falha de leitura do arquivo
            bpy.context.scene.world = mundo       # volta ao céu da cena (ceu_hdri já trocou o mundo antes de ler a imagem)
            ignorados.append(f"hdri {os.path.basename(str(params['hdri']))}: {str(e).splitlines()[0][:120]}")
            print(f"AVISO recurso externo ignorado (HDRI): {e}", flush=True)
    for m in params.get("modelos", []):
        try:
            L.importar_modelo(m["arquivo"], tuple(m.get("loc", (0, 0, 0))), m.get("escala", 1.0),
                              tuple(math.radians(g) for g in m.get("rot_graus", (0, 0, 0))))
            usados.setdefault("modelos", []).append(os.path.basename(m["arquivo"]))
        except Exception as e:  # noqa: BLE001
            ignorados.append(f"modelo {os.path.basename(str(m.get('arquivo')))}: {str(e).splitlines()[0][:120]}")
            print(f"AVISO recurso externo ignorado (modelo): {e}", flush=True)
    return usados, ignorados


def main():
    a = _argumentos()
    import bpy  # noqa: F401  (primeiro: registra bmesh/mathutils no modo módulo)
    import lib3d as L
    import cenas
    if a.listar:
        print("CENAS3D " + json.dumps(sorted(cenas.CENAS)), flush=True)
        return 0
    if a.cena not in cenas.CENAS:
        print(f"ERRO cena desconhecida: {a.cena}. Disponíveis: {', '.join(sorted(cenas.CENAS))}", flush=True)
        return 2
    a.params = json.loads(a.params or "{}")
    a.saida = os.path.abspath(a.saida)
    os.makedirs(a.saida, exist_ok=True)
    L.reiniciar()
    info = L.configurar_render(a)
    L.semente_aleatoria(a.semente)
    t0 = time.time()
    cena = cenas.CENAS[a.cena](a)
    usados, ignorados = _recursos_externos(L, a.params)
    print(f"CENA_PRONTA {a.cena} montada em {time.time() - t0:.1f}s ({info['motor']}/{info['dispositivo']})", flush=True)
    n = max(1, int(round(a.duracao * a.fps)))
    indices = [0] if a.quadro is not None else range(n)
    feitos = 0
    for i in indices:
        p = a.quadro if a.quadro is not None else (i / (n - 1) if n > 1 else 0.0)
        destino = os.path.join(a.saida, f"quadro_{i + 1:05d}.png" if a.quadro is None else "quadro_unico.png")
        if a.quadro is None and os.path.exists(destino) and os.path.getsize(destino) > 1000:
            feitos += 1
            continue
        cena.atualizar(p, i / a.fps)
        t1 = time.time()
        L.renderizar_quadro(destino + ".parcial.png")
        os.replace(destino + ".parcial.png", destino)
        feitos += 1
        print(f"PROGRESSO {feitos}/{len(indices) if a.quadro is None else 1} {time.time() - t1:.1f}s", flush=True)
    meta = {"cena": a.cena, "quadros": n if a.quadro is None else 1, "fps": a.fps, "largura": a.largura, "altura": a.altura,
            "amostras": a.amostras, "motor": info, "rotulo": cena.rotulo, "nota": cena.nota}
    if usados:
        meta["recursos"] = usados
    if ignorados:
        meta["recursos_ignorados"] = ignorados
    with open(os.path.join(a.saida, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("CONCLUIDO", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
