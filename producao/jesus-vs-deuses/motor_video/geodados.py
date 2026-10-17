"""Dados geográficos abertos (Natural Earth, domínio público) para o mapa 3D em relevo."""

from __future__ import annotations

import json
from pathlib import Path

from .config import ErroProducao, log
from .image_research import ClienteHTTP

URL_TERRAS = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"


def validar_geojson(caminho: Path) -> int:
    """Número de polígonos válidos do GeoJSON (levanta erro se o arquivo não servir)."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErroProducao(f"GeoJSON inválido ({e})") from e
    n = 0
    for ft in dados.get("features", []):
        g = ft.get("geometry") or {}
        if g.get("type") == "Polygon":
            n += 1
        elif g.get("type") == "MultiPolygon":
            n += len(g.get("coordinates", []))
    if n == 0:
        raise ErroProducao("GeoJSON sem polígonos.")
    return n


def obter_terras(pasta: Path, http: ClienteHTTP | None) -> Path | None:
    """Caminho do GeoJSON de terras emersas (baixa e valida uma vez; None se offline)."""
    destino = pasta / "ne_110m_land.geojson"
    if destino.is_file():
        try:
            validar_geojson(destino)
            return destino
        except ErroProducao:
            destino.unlink(missing_ok=True)
    if http is None or not http.conectado():
        return None
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        http.baixar(URL_TERRAS, destino, max_bytes=20 * 1024 * 1024)
        n = validar_geojson(destino)
        log().info("Natural Earth (domínio público): %d polígonos de terra baixados.", n)
        return destino
    except ErroProducao as e:
        destino.unlink(missing_ok=True)
        log().warning("Não foi possível obter os dados de terras (Natural Earth): %s", str(e)[:160])
        return None
