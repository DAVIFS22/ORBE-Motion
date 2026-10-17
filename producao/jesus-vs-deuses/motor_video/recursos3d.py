"""Recursos 3D abertos: HDRIs, modelos e texturas do Poly Haven (todos CC0).

Usados como iluminação (HDRI) e objetos extras nas cenas 3D; a pesquisa registra fonte e licença como as
imagens. Sem rede, as cenas usam o céu procedural e os objetos gerados por código.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .config import ErroProducao, log, salvar_json
from .image_research import ClienteHTTP

API = "https://api.polyhaven.com"
LICENCA = "CC0 (Poly Haven)"


@dataclass
class Recurso3D:
    id: str
    tipo: str          # hdris | models | textures
    nome: str
    arquivos: list[str]
    caminho: str       # arquivo principal local (.hdr/.exr/.gltf)
    licenca: str = LICENCA
    url_pagina: str = ""


class PolyHaven:
    def __init__(self, http: ClienteHTTP, base: str = API):
        self.http, self.base = http, base

    def listar(self, tipo: str = "hdris") -> dict:
        return self.http.json(f"{self.base}/assets", {"t": tipo})

    def buscar(self, tipo: str, termos: list[str], limite: int = 5) -> list[tuple[str, dict]]:
        """Recursos cujo nome, tags ou categorias contêm algum termo (mais termos casados = mais acima)."""
        catalogo = self.listar(tipo)
        ach = []
        for rid, meta in catalogo.items():
            texto = " ".join([rid, meta.get("name", ""), *meta.get("tags", []), *meta.get("categories", [])]).lower()
            pontos = sum(1 for t in termos if t.lower() in texto)
            if pontos:
                ach.append((pontos, rid, meta))
        ach.sort(key=lambda x: (-x[0], x[1]))
        return [(rid, meta) for _, rid, meta in ach[:limite]]

    def _baixar_verificando(self, info: dict, destino: Path) -> None:
        if destino.is_file() and (not info.get("md5") or hashlib.md5(destino.read_bytes()).hexdigest() == info["md5"]):
            return
        self.http.baixar(info["url"], destino, max_bytes=300 * 1024 * 1024)
        if info.get("md5") and hashlib.md5(destino.read_bytes()).hexdigest() != info["md5"]:
            destino.unlink(missing_ok=True)
            raise ErroProducao(f"Checksum inválido em {destino.name} (download corrompido).")

    def baixar_hdri(self, rid: str, pasta: Path, resolucao: str = "2k") -> Recurso3D:
        arquivos = self.http.json(f"{self.base}/files/{rid}")
        niveis = arquivos.get("hdri") or {}
        nivel = niveis.get(resolucao) or niveis.get("1k") or next(iter(niveis.values()), None)
        if not nivel or "hdr" not in nivel:
            raise ErroProducao(f"HDRI {rid} sem arquivo .hdr utilizável.")
        destino = pasta / f"{rid}_{resolucao}.hdr"
        self._baixar_verificando(nivel["hdr"], destino)
        return Recurso3D(rid, "hdris", rid, [destino.name], str(destino), url_pagina=f"https://polyhaven.com/a/{rid}")

    def baixar_modelo(self, rid: str, pasta: Path, resolucao: str = "1k") -> Recurso3D:
        arquivos = self.http.json(f"{self.base}/files/{rid}")
        niveis = (arquivos.get("gltf") or {})
        nivel = niveis.get(resolucao) or next(iter(niveis.values()), None)
        if not nivel or "gltf" not in nivel:
            raise ErroProducao(f"Modelo {rid} sem glTF utilizável.")
        base = pasta / rid
        principal = base / f"{rid}.gltf"
        self._baixar_verificando(nivel["gltf"], principal)
        baixados = [principal.name]
        for rel, info in (nivel["gltf"].get("include") or {}).items():
            alvo = (base / rel).resolve()
            if base.resolve() not in alvo.parents:
                raise ErroProducao(f"Caminho suspeito no modelo {rid}: {rel}")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            self._baixar_verificando(info, alvo)
            baixados.append(rel)
        return Recurso3D(rid, "models", rid, baixados, str(principal), url_pagina=f"https://polyhaven.com/a/{rid}")


def registrar_recursos(pasta: Path, recursos: list[Recurso3D]):
    salvar_json(pasta / "recursos-3d.json", [r.__dict__ for r in recursos])
