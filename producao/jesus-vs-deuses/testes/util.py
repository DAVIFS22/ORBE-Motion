"""Utilitários de teste: servidor HTTP simulado (Commons/Met/AIC/Poly Haven) e geração de mídia sintética."""

from __future__ import annotations

import io
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image


class Servidor:
    """Servidor local. `rotas`: {caminho: callable(handler, consulta) -> (status, cabecalhos, corpo_bytes)}."""

    def __init__(self):
        self.rotas: dict = {}
        self.contagem: dict[str, int] = {}
        servidor = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silencioso
                pass

            def do_GET(self):
                from urllib.parse import parse_qs, urlparse
                u = urlparse(self.path)
                servidor.contagem[u.path] = servidor.contagem.get(u.path, 0) + 1
                f = servidor.rotas.get(u.path)
                if f is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                status, cab, corpo = f(self, parse_qs(u.query))
                self.send_response(status)
                for k, v in cab.items():
                    self.send_header(k, v)
                if "Content-Length" not in cab:
                    self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.porta = self.httpd.server_address[1]
        self.base = f"http://127.0.0.1:{self.porta}"
        self._t = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()

    def json(self, caminho: str, dados, status: int = 200, cab: dict | None = None):
        corpo = json.dumps(dados).encode()
        self.rotas[caminho] = lambda h, q: (status, {"Content-Type": "application/json", **(cab or {})}, corpo)

    def bytes(self, caminho: str, corpo: bytes, status: int = 200, tipo: str = "image/jpeg"):
        self.rotas[caminho] = lambda h, q: (status, {"Content-Type": tipo}, corpo)


def imagem_bytes(w=1600, h=900, semente=1, formato="JPEG") -> bytes:
    rng = np.random.default_rng(semente)
    base = rng.integers(0, 255, (h // 40 + 2, w // 40 + 2, 3), dtype=np.uint8)
    img = Image.fromarray(base).resize((w, h), Image.BICUBIC)
    buf = io.BytesIO()
    img.save(buf, formato, quality=90)
    return buf.getvalue()


def gerar_video(caminho: Path, dur=4.0, w=1280, h=720, fps=30, padrao="testsrc2"):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"{padrao}=s={w}x{h}:r={fps}:d={dur}", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-g", "30", str(caminho)], check=True)
    return caminho


def gerar_wav(caminho: Path, dur=5.0, sr=48000, freq=220.0, canais=1, nivel=0.1):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(dur * sr)) / sr
    x = (np.sin(2 * np.pi * freq * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)) * nivel).astype(np.float32)
    dados = np.repeat(x[:, None], canais, axis=1) if canais > 1 else x
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", str(canais), "-i", "-", "-c:a", "pcm_s24le", str(caminho)],
                   input=dados.tobytes(), check=True)
    return caminho
