import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from motor_video import geodados, media_ingestion as mi, project_report, recursos3d
from motor_video.__main__ import main as cli
from motor_video.config import Config, ErroProducao
from motor_video.image_research import ClienteHTTP

from .util import Servidor, gerar_video, gerar_wav

RAIZ = Path(__file__).resolve().parent.parent


class TestPolyHaven(unittest.TestCase):
    def test_busca_download_e_checksum(self):
        with tempfile.TemporaryDirectory() as d, Servidor() as s:
            hdr = b"#?RADIANCE\n" + b"x" * 500
            gltf = json.dumps({"asset": {"version": "2.0"}}).encode()
            bin_ = b"b" * 100
            s.bytes("/dl/sunset_2k.hdr", hdr, tipo="application/octet-stream")
            s.bytes("/dl/rock.gltf", gltf, tipo="model/gltf+json")
            s.bytes("/dl/rock.bin", bin_, tipo="application/octet-stream")
            s.json("/assets", {"sunset_sky": {"name": "Sunset Sky", "categories": ["skies", "sunrise-sunset"], "tags": ["sun", "evening"]},
                               "indoor_lamp": {"name": "Indoor Lamp", "categories": ["indoor"], "tags": ["lamp"]}})
            s.json("/files/sunset_sky", {"hdri": {"2k": {"hdr": {"url": s.base + "/dl/sunset_2k.hdr", "md5": hashlib.md5(hdr).hexdigest(), "size": len(hdr)}}}})
            s.json("/files/rock", {"gltf": {"1k": {"gltf": {"url": s.base + "/dl/rock.gltf", "md5": hashlib.md5(gltf).hexdigest(),
                                                           "include": {"rock.bin": {"url": s.base + "/dl/rock.bin", "md5": hashlib.md5(bin_).hexdigest()}}}}}})
            s.json("/files/ruim", {"gltf": {"1k": {"gltf": {"url": s.base + "/dl/rock.gltf", "md5": hashlib.md5(gltf).hexdigest(),
                                                           "include": {"../../fora.bin": {"url": s.base + "/dl/rock.bin"}}}}}})
            s.json("/files/corrompido", {"hdri": {"2k": {"hdr": {"url": s.base + "/dl/sunset_2k.hdr", "md5": "0" * 32}}}})
            ph = recursos3d.PolyHaven(ClienteHTTP(intervalo=0, tentativas=1, timeout=5), base=s.base)
            achados = ph.buscar("hdris", ["sunset", "evening"])
            self.assertEqual(achados[0][0], "sunset_sky")
            self.assertEqual(len(ph.buscar("hdris", ["zzz"])), 0)
            r = ph.baixar_hdri("sunset_sky", Path(d))
            self.assertTrue(Path(r.caminho).is_file())
            self.assertEqual(r.licenca, "CC0 (Poly Haven)")
            m = ph.baixar_modelo("rock", Path(d))
            self.assertTrue((Path(d) / "rock" / "rock.bin").is_file())
            self.assertEqual(sorted(m.arquivos), ["rock.bin", "rock.gltf"])
            with self.assertRaises(ErroProducao) as e:                       # caminho malicioso no pacote
                ph.baixar_modelo("ruim", Path(d))
            self.assertIn("suspeito", str(e.exception))
            self.assertFalse((Path(d).parent / "fora.bin").exists())
            with self.assertRaises(ErroProducao) as e:                       # download corrompido
                ph.baixar_hdri("corrompido", Path(d) / "x")
            self.assertIn("Checksum", str(e.exception))
            self.assertFalse(list((Path(d) / "x").glob("*.hdr")))


class TestGeodados(unittest.TestCase):
    def test_validar_e_obter(self):
        with tempfile.TemporaryDirectory() as d, Servidor() as s:
            geo = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
                {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[2, 2], [3, 2], [3, 3], [2, 2]]], [[[5, 5], [6, 5], [6, 6], [5, 5]]]]}}]}
            s.json("/land.geojson", geo)
            s.json("/vazio.geojson", {"type": "FeatureCollection", "features": []})
            antigo = geodados.URL_TERRAS
            try:
                geodados.URL_TERRAS = s.base + "/land.geojson"
                http = ClienteHTTP(intervalo=0, tentativas=1, timeout=5)
                arq = geodados.obter_terras(Path(d), http)
                self.assertEqual(geodados.validar_geojson(arq), 3)
                self.assertEqual(geodados.obter_terras(Path(d), None), arq)       # já baixado: funciona offline
                geodados.URL_TERRAS = s.base + "/vazio.geojson"
                self.assertIsNone(geodados.obter_terras(Path(d) / "outro", http))   # inválido: não usa
            finally:
                geodados.URL_TERRAS = antigo
            self.assertIsNone(geodados.obter_terras(Path(d) / "sem", None))


class TestIngestao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mp3_vira_wav_48k24_sem_alterar_o_original(self):
        wav = gerar_wav(self.d / "origem.wav", 3.0, 44100, 300.0, 2)
        mp3 = self.d / "narracao.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3)], check=True)
        antes = hashlib.sha256(mp3.read_bytes()).hexdigest()
        roteiro = self.d / "roteiro.txt"
        roteiro.write_text("Texto.", encoding="utf-8")
        cfg = Config(saida=self.d / "saida", narracao=mp3, roteiro=roteiro)
        ent = mi.ingerir(cfg, None)
        info = mi.sondar(ent.narracao_wav)
        self.assertEqual(info.taxa_amostragem, 48000)
        self.assertAlmostEqual(info.duracao, ent.narracao_original.duracao, delta=0.05)    # duração preservada
        self.assertEqual(ent.narracao_original.sha256, antes)
        self.assertTrue(mi.conferir_originais(ent)["narracao"]["inalterado"])
        mp3.write_bytes(mp3.read_bytes() + b"\0")                                           # alteração é detectada
        self.assertFalse(mi.conferir_originais(ent)["narracao"]["inalterado"])

    def test_video_com_audio_extrai_so_o_audio(self):
        v = self.d / "captura.mp4"
        gerar_video(self.d / "v.mp4", 2.0, 320, 180, 10)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(self.d / "v.mp4"), "-f", "lavfi", "-i", "sine=f=300:d=2", "-c:v", "copy", "-c:a", "aac", "-shortest", str(v)], check=True)
        info = mi.sondar(v)
        self.assertTrue(info.tem_video and info.tem_audio)
        self.assertAlmostEqual(info.duracao, 2.0, delta=0.2)

    def test_erros_claros(self):
        with self.assertRaises(ErroProducao) as e:
            mi.sondar(self.d / "nao_existe.mp3")
        self.assertIn("não encontrado", str(e.exception))
        vazio = self.d / "vazio.wav"
        vazio.write_bytes(b"")
        with self.assertRaises(ErroProducao) as e:
            mi.sondar(vazio)
        self.assertIn("vazio", str(e.exception))
        mudo = gerar_video(self.d / "mudo.mp4", 1.0, 160, 90, 10)
        with self.assertRaises(ErroProducao) as e:
            mi.sondar(mudo)
        self.assertIn("não tem faixa de áudio", str(e.exception))

    def test_deteccao_automatica_prefere_narracao_tratada(self):
        gerar_wav(self.d / "bruta.wav", 1.0)
        gerar_wav(self.d / "x-narracao-tratada-48k24.wav", 1.0)
        gerar_video(self.d / "captura.mp4", 1.0, 160, 90, 10)
        (self.d / "mix-final.wav").write_bytes(b"x")
        nomes = [p.name for p in mi.candidatos_narracao(self.d)]
        self.assertEqual(nomes[0], "x-narracao-tratada-48k24.wav")
        self.assertNotIn("mix-final.wav", nomes)
        self.assertEqual(nomes[-1], "captura.mp4")
        (self.d / "a.txt").write_text("nada", encoding="utf-8")
        (self.d / "b.txt").write_text("== INÍCIO DA NARRAÇÃO COMPLETA ==\nOi\n== FIM DA NARRAÇÃO COMPLETA ==", encoding="utf-8")
        self.assertEqual(mi.candidatos_roteiro(self.d)[0].name, "b.txt")


class TestRelatorioECli(unittest.TestCase):
    def _ctx(self, aprovado):
        asset = {"id": "a1", "cenas": ["c1"], "arquivo_original": "originais/a.jpg", "fonte": "commons", "titulo": "Karnak", "autor": "Fulano de Tal",
                 "licenca": "CC BY-SA 4.0", "url_pagina": "https://commons.example/Karnak", "url_arquivo": "u", "natureza": "imagem de acervo aberto",
                 "largura": 1920, "altura": 1080}
        return {"versao": "1.0.0", "validacao": False, "cfg": {"largura": 1920, "altura": 1080, "fps": 30},
                "qc": {"aprovado": aprovado, "itens": [{"nome": "fluxos", "status": "ok" if aprovado else "falha", "detalhe": "x"}]},
                "timeline": {"cenas": 1, "planos": 1, "planos_com_imagem": 1, "planos_gerados": 0, "transicoes": {"dissolve": 1}},
                "assets": [asset], "pendencias": [{"cena": "c9", "motivo": "sem rede"}], "falhas_download": [{"motivo": "acesso negado: 403"}],
                "entradas": {"narracao_original": "n.mp3", "narracao_duracao_s": 10.0, "narracao_sha256": "a" * 64, "roteiro": "r.txt",
                             "transcricao": "t.vtt", "narracao_tratada": False},
                "alinhamento": {"cobertura": 0.97, "palavras": 100, "lacunas": []}, "avisos": ["aviso de teste"],
                "audio": {"narracao_rms_db": -20.0, "narracao_pico_db": -3.0, "fontes": [{"tipo": "musica", "origem": "sintetizada por código"}],
                          "mix_lufs": "-14.0", "alvo_lufs": -14.0, "true_peak": -1.5},
                "render": {"encoder": "libx264", "hardware": False, "blocos": 2, "quadros": 10, "tempo_renderizacao_s": 1},
                "cenas3d": [], "tempos": {"x": 1.0}, "comando": "python -m motor_video produzir", "video": "v.mp4", "video_mb": 1.0,
                "duracao_video_s": 10.0, "srt": "a.srt", "n_legendas": 3, "timeline_json": "t.json", "log": "l.log", "rede": ""}

    def test_relatorio_e_creditos(self):
        with tempfile.TemporaryDirectory() as d:
            md = project_report.gerar(self._ctx(False), Path(d))
            texto = md.read_text(encoding="utf-8")
            self.assertIn("NÃO APROVADO", texto)
            self.assertIn("Pendências", texto)
            self.assertIn("sem rede", texto)
            cred = (Path(d) / "creditos-imagens.md").read_text(encoding="utf-8")
            self.assertIn("Fulano de Tal", cred)
            self.assertIn("CC BY-SA 4.0", cred)
            csv = (Path(d) / "fontes-imagens.csv").read_text(encoding="utf-8-sig")
            self.assertIn("url_pagina", csv.splitlines()[0])
            self.assertIn("https://commons.example/Karnak", csv)
            self.assertTrue(json.loads((Path(d) / "relatorio-producao.json").read_text(encoding="utf-8"))["qc"]["aprovado"] is False)
            md2 = project_report.gerar(self._ctx(True), Path(d) / "ok")
            self.assertIn("APROVADO em todas", md2.read_text(encoding="utf-8"))

    def test_relatorio_secao_3d(self):
        sem = self._ctx(True)
        with tempfile.TemporaryDirectory() as d:
            t0 = project_report.gerar(sem, Path(d)).read_text(encoding="utf-8")
        self.assertIn("Animação 3D (Blender), uso seletivo", t0)
        self.assertIn("Nenhuma cena 3D nesta execução", t0)
        ctx = self._ctx(True)
        ctx["blender"] = "python: /x/bin/python (versão 5.2.2)"
        ctx["config3d"] = {"prioridade": 2, "qualidade": "teste", "dispositivo": "cpu", "motor": "CYCLES", "orcamento_min": 40.0}
        ctx["timeline"].update({"planos_3d": 2, "planos_video": 0})
        ctx["cenas3d"] = [
            {"plano_id": "a03-templos#1", "cena": "templo_egipcio", "prioridade": 1, "duracao": 5.0, "status": "renderizado", "tempo_real_s": 150.0},
            {"plano_id": "d04-anubis#1", "cena": "deus_anubis", "prioridade": 2, "duracao": 5.0, "status": "reaproveitado", "tempo_real_s": 0.0},
            {"plano_id": "d05-ra#1", "cena": "deus_ra", "prioridade": 2, "duracao": 4.0, "status": "cortado_orcamento", "tempo_real_s": 0.0}]
        with tempfile.TemporaryDirectory() as d:
            t1 = project_report.gerar(ctx, Path(d)).read_text(encoding="utf-8")
        self.assertIn("2 clipe(s) usados, 10 s no total = 100.0% do vídeo", t1)       # 10 s de 10 s no contexto de teste
        self.assertIn("| `a03-templos#1` | templo_egipcio | P1 | 5.0 s | renderizado | 2.5 min |", t1)
        self.assertIn("cortado (orçamento)", t1)
        self.assertIn("reconstruções ou representações artísticas", t1)
        self.assertIn("orçamento de 40 min", t1)
        self.assertIn("2 com animação 3D", t1)

    def test_cli(self):
        with self.assertRaises(SystemExit) as e, contextlib.redirect_stdout(io.StringIO()):
            cli(["--help"])
        self.assertEqual(e.exception.code, 0)
        self.assertEqual(cli(["produzir"]), 1)                         # sem narração: erro claro, não exceção
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli(["storyboard", "--roteiro", str(RAIZ / "entrada" / "prompt_narracao_e_producao_jesus.txt"),
                      "--transcricao", str(RAIZ / "entrada" / "lv_0_20261017144122.vtt")])
        self.assertEqual(rc, 0)
        saida = buf.getvalue()
        self.assertIn("a01-titulo", saida)
        self.assertIn("k33-pergunta-final", saida)
        self.assertIn("AVISO", saida)                                  # cenas descartadas são avisadas


if __name__ == "__main__":
    unittest.main()
