import json
import tempfile
import unittest
from pathlib import Path

from motor_video import asset_manager as am
from motor_video import image_research as ir

from .util import Servidor, gerar_video, imagem_bytes


def pagina(idx, titulo, w, h, mime, url, lic, cats="", nonfree=False, dur=None):
    meta = {"LicenseShortName": {"value": lic}, "Artist": {"value": "<a href='x'>Fulano de Tal</a>"}, "Categories": {"value": cats},
            "ImageDescription": {"value": "Karnak temple columns Egypt"}, "LicenseUrl": {"value": "https://lic.example"}}
    if nonfree:
        meta["NonFree"] = {"value": "true"}
    info = {"url": url, "thumburl": url, "descriptionurl": f"https://commons.example/{titulo}", "width": w, "height": h, "mime": mime,
            "extmetadata": meta}
    if dur is not None:
        info["duration"] = dur
    return {"pageid": idx, "title": f"File:{titulo}", "index": idx, "imageinfo": [info]}


class TestLicencas(unittest.TestCase):
    def test_classificacao(self):
        c = ir.classificar_licenca
        self.assertEqual(c("Public domain"), "dominio_publico")
        self.assertEqual(c("CC0"), "cc0")
        self.assertEqual(c("CC BY-SA 4.0"), "cc-by-sa")
        self.assertEqual(c("CC BY 2.0"), "cc-by")
        self.assertEqual(c("PD-old-70"), "dominio_publico")
        for ruim in ("CC BY-NC 4.0", "CC BY-ND 3.0", "CC BY-NC-SA 2.0", "Fair use", "All rights reserved", "", "GFDL"):
            self.assertIsNone(c(ruim), ruim)

    def test_suspeitos(self):
        cand = ir.Candidato("commons", "1", "x.jpg", "u", "p", 1600, 900, "image/jpeg", "CC0", "cc0", categorias=["AI-generated images"])
        self.assertIsNotNone(ir.e_suspeito(cand))
        cand.categorias = []
        cand.descricao = "Image with Shutterstock watermark"
        self.assertIsNotNone(ir.e_suspeito(cand))
        cand.descricao = "Karnak temple"
        self.assertIsNone(ir.e_suspeito(cand))

    def test_pontuacao_prefere_alta_resolucao_e_16x9(self):
        a = ir.Candidato("commons", "1", "Karnak temple.jpg", "u", "p", 3840, 2160, "image/jpeg", "CC0", "cc0", descricao="Karnak temple")
        b = ir.Candidato("commons", "2", "Karnak temple.jpg", "u", "p", 1400, 2000, "image/jpeg", "CC0", "cc0", descricao="Karnak temple")
        c = ir.Candidato("commons", "3", "Karnak temple.jpg", "u", "p", 640, 360, "image/jpeg", "CC0", "cc0", descricao="Karnak temple")
        pa, pb, pc = (ir.pontuar(x, "Karnak temple", 1280) for x in (a, b, c))
        self.assertGreater(pa, pb)
        self.assertGreater(pb, pc)


class TestPesquisaComServidorSimulado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.srv = Servidor().__enter__()
        s = self.srv
        s.bytes("/img/a.jpg", imagem_bytes(1600, 900, 1))
        s.bytes("/img/a_dup.jpg", imagem_bytes(1600, 900, 1))                 # idêntica à A
        s.bytes("/img/b.jpg", imagem_bytes(1800, 1000, 2))
        s.bytes("/img/c.jpg", imagem_bytes(1700, 950, 3))
        s.bytes("/img/d.jpg", imagem_bytes(1700, 950, 4))
        s.bytes("/img/ia.jpg", imagem_bytes(1700, 950, 5))
        s.bytes("/img/quebrada.jpg", b"isto nao e uma imagem")
        s.bytes("/img/proibida.jpg", b"", status=403)
        s.bytes("/img/pequena.jpg", imagem_bytes(900, 500, 6))
        paginas = [
            pagina(1, "Karnak A.jpg", 1600, 900, "image/jpeg", s.base + "/img/a.jpg", "Public domain"),
            pagina(2, "Karnak NC.jpg", 1600, 900, "image/jpeg", s.base + "/img/c.jpg", "CC BY-NC 4.0"),
            pagina(3, "Karnak IA.jpg", 1700, 950, "image/jpeg", s.base + "/img/ia.jpg", "CC0", cats="AI-generated images"),
            pagina(4, "Karnak B.jpg", 1800, 1000, "image/jpeg", s.base + "/img/b.jpg", "CC BY-SA 4.0"),
            pagina(5, "Karnak proibida.jpg", 1700, 950, "image/jpeg", s.base + "/img/proibida.jpg", "CC0"),
            pagina(6, "Karnak quebrada.jpg", 1700, 950, "image/jpeg", s.base + "/img/quebrada.jpg", "CC0"),
            pagina(7, "Karnak dup.jpg", 1600, 900, "image/jpeg", s.base + "/img/a_dup.jpg", "CC0"),
            pagina(8, "Karnak nao livre.jpg", 1700, 950, "image/jpeg", s.base + "/img/d.jpg", "CC0", nonfree=True),
            pagina(9, "Karnak pequena.jpg", 800, 450, "image/jpeg", s.base + "/img/pequena.jpg", "CC0"),
            pagina(10, "Karnak D.jpg", 1700, 950, "image/jpeg", s.base + "/img/d.jpg", "CC0"),
        ]
        s.json("/w/api.php", {"query": {"pages": paginas}})
        self.http = ir.ClienteHTTP(intervalo=0, tentativas=2, timeout=5)
        self.commons = ir.ProvedorCommons(self.http, base=s.base + "/w/api.php")
        self.ger = am.GerenciadorAssets(self.pasta / "imagens", self.http)

    def tearDown(self):
        self.srv.__exit__()
        self.tmp.cleanup()

    def test_filtra_licencas_ia_dupes_quebradas_e_substitui(self):
        achadas = am.obter_imagens_para_cena("cena1", [{"q": "Karnak temple", "fontes": ["commons"]}], 3, self.ger, [self.commons])
        titulos = sorted(a.titulo for a in achadas)
        self.assertEqual(titulos, ["Karnak A.jpg", "Karnak B.jpg", "Karnak D.jpg"])
        motivos = " | ".join(f["motivo"] for f in self.ger.falhas)
        self.assertIn("IA", motivos)                    # gerada por IA
        self.assertIn("acesso negado", motivos)          # 403: sem insistir
        self.assertIn("não abre como imagem", motivos)   # arquivo quebrado
        self.assertIn("duplicada", motivos)              # mesma imagem, outro arquivo
        self.assertEqual(self.ger.pendencias, [])
        for a in achadas:                                # só arquivos locais validados, com fonte/autor/licença
            self.assertTrue((self.ger.pasta / a.arquivo_trabalho).is_file())
            self.assertEqual(a.autor, "Fulano de Tal")
            self.assertTrue(a.licenca and a.url_pagina)
        self.assertEqual({a.licenca_categoria for a in achadas}, {"dominio_publico", "cc-by-sa", "cc0"})

    def test_pendencia_quando_faltam_imagens(self):
        achadas = am.obter_imagens_para_cena("cena2", [{"q": "Karnak temple", "fontes": ["commons"]}], 6, self.ger, [self.commons])
        self.assertEqual(len(achadas), 3)
        self.assertEqual(len(self.ger.pendencias), 1)
        self.assertIn("faltam 3 de 6", self.ger.pendencias[0]["motivo"])

    def test_manifesto_persiste_e_buscas_ficam_em_cache(self):
        am.obter_imagens_para_cena("cena1", [{"q": "Karnak temple", "fontes": ["commons"]}], 2, self.ger, [self.commons])
        n = self.srv.contagem["/w/api.php"]
        ger2 = am.GerenciadorAssets(self.pasta / "imagens", self.http)
        self.assertEqual(len(ger2.assets), len(self.ger.assets))
        am.obter_imagens_para_cena("cena9", [{"q": "Karnak temple", "fontes": ["commons"]}], 1, ger2, [self.commons])
        self.assertEqual(self.srv.contagem["/w/api.php"], n)   # a busca repetida vem do cache, sem nova chamada

    def test_429_com_retry_after_e_repetido(self):
        chamadas = {"n": 0}

        def f(h, q):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return 429, {"Retry-After": "0"}, b""
            return 200, {"Content-Type": "application/json"}, b'{"ok": 1}'
        self.srv.rotas["/lento"] = f
        self.assertEqual(self.http.json(self.srv.base + "/lento"), {"ok": 1})
        self.assertEqual(chamadas["n"], 2)

    def test_download_incompleto_e_rejeitado(self):
        # o servidor anuncia 100 bytes e envia só 10, depois encerra a conexão
        self.srv.rotas["/trunca"] = lambda h, q: (200, {"Content-Type": "image/jpeg", "Content-Length": "100"}, b"x" * 10)
        destino = self.pasta / "t.jpg"
        with self.assertRaises(ir.ErroProducao) as e:
            self.http.baixar(self.srv.base + "/trunca", destino)
        self.assertIn("incompleto", str(e.exception))
        self.assertFalse(destino.exists())                     # nada de arquivo parcial deixado como válido
        self.assertFalse(list(self.pasta.glob("*.part")))
        # arquivo íntegro: baixa normalmente
        self.srv.rotas["/ok"] = lambda h, q: (200, {"Content-Type": "image/jpeg"}, b"y" * 10)
        self.assertEqual(self.http.baixar(self.srv.base + "/ok", destino), 10)

    def test_disjuntor_de_rede(self):
        http = ir.ClienteHTTP(intervalo=0, tentativas=1, timeout=1)
        for _ in range(2):
            with self.assertRaises(ir.RedeIndisponivel):
                http.json("http://127.0.0.1:1/x")
        self.assertFalse(http.conectado())
        with self.assertRaises(ir.RedeIndisponivel) as e:
            http.json(self.srv.base + "/w/api.php")        # mesmo com servidor ok: não insiste
        self.assertIn("não insistindo", str(e.exception))

    def test_modo_offline_registra_pendencia(self):
        ger = am.GerenciadorAssets(self.pasta / "off", None)
        achadas = am.obter_imagens_para_cena("c", [{"q": "x", "fontes": ["commons"]}], 1, ger, [])
        self.assertEqual(achadas, [])
        self.assertEqual(len(ger.pendencias), 1)


class TestMuseus(unittest.TestCase):
    def test_met_e_aic(self):
        with tempfile.TemporaryDirectory() as d, Servidor() as s:
            s.bytes("/met/img1.jpg", imagem_bytes(1700, 1300, 11))
            s.bytes("/iiif/abc/full/1686,/0/default.jpg", imagem_bytes(1686, 1100, 12))
            s.json("/met/search", {"total": 2, "objectIDs": [1, 2]})
            s.json("/met/objects/1", {"objectID": 1, "isPublicDomain": True, "primaryImage": s.base + "/met/img1.jpg", "title": "Head of Christ",
                                      "artistDisplayName": "Rembrandt", "objectURL": "https://met.example/1", "creditLine": "Gift", "medium": "Oil"})
            s.json("/met/objects/2", {"objectID": 2, "isPublicDomain": False, "primaryImage": s.base + "/x.jpg", "title": "Protegida"})
            s.json("/aic/artworks/search", {"config": {"iiif_url": s.base + "/iiif"}, "data": [
                {"id": 7, "title": "Crucifixion", "image_id": "abc", "is_public_domain": True, "artist_display": "Artista", "thumbnail": {"width": 3, "height": 2}},
                {"id": 8, "title": "Protegida", "image_id": "zzz", "is_public_domain": False}]})
            http = ir.ClienteHTTP(intervalo=0, tentativas=1, timeout=5)
            met, aic = ir.ProvedorMet(http, base=s.base + "/met"), ir.ProvedorAIC(http, base=s.base + "/aic")
            ger = am.GerenciadorAssets(Path(d), http)
            achadas = am.obter_imagens_para_cena("c", [{"q": "Christ", "fontes": ["met", "aic"]}], 2, ger, [met, aic])
            self.assertEqual({a.fonte for a in achadas}, {"met", "aic"})
            self.assertTrue(all(a.licenca_categoria == "cc0" for a in achadas))
            self.assertTrue(all("obra de arte" in a.natureza for a in achadas))   # arte aparece como arte
            self.assertEqual(len(ger.pendencias), 0)


class TestVideos(unittest.TestCase):
    def test_busca_e_validacao_de_filmagens(self):
        with tempfile.TemporaryDirectory() as d, Servidor() as s:
            tmp = Path(d)
            ok = gerar_video(tmp / "ok.mp4", 8.0, 1280, 720)
            curto = gerar_video(tmp / "curto.mp4", 2.0, 1280, 720)
            baixa = gerar_video(tmp / "baixa.mp4", 8.0, 640, 360)
            for nome, arq in (("ok", ok), ("curto", curto), ("baixa", baixa)):
                s.bytes(f"/v/{nome}.mp4", arq.read_bytes(), tipo="video/mp4")
            s.bytes("/v/img.jpg", imagem_bytes(), tipo="image/jpeg")
            pg = [pagina(1, "Baixa.mp4", 640, 360, "video/mp4", s.base + "/v/baixa.mp4", "CC0", dur=8.0),
                  pagina(2, "Curto.mp4", 1280, 720, "video/mp4", s.base + "/v/curto.mp4", "CC0", dur=2.0),
                  pagina(3, "Foto.jpg", 1600, 900, "image/jpeg", s.base + "/v/img.jpg", "CC0"),
                  pagina(4, "NC.mp4", 1280, 720, "video/mp4", s.base + "/v/ok.mp4", "CC BY-NC 4.0", dur=8.0),
                  pagina(5, "Bom.mp4", 1280, 720, "video/mp4", s.base + "/v/ok.mp4", "CC BY 4.0", dur=8.0)]
            s.json("/w/api.php", {"query": {"pages": pg}})
            http = ir.ClienteHTTP(intervalo=0, tentativas=1, timeout=10)
            commons = ir.ProvedorCommons(http, base=s.base + "/w/api.php")
            ger = am.GerenciadorAssets(tmp / "assets", http)
            v = am.obter_videos_para_cena("cena", ["nile"], 5.0, ger, [commons])
            self.assertIsNotNone(v)
            self.assertEqual(v.titulo, "Bom.mp4")
            self.assertEqual(v.tipo, "video")
            self.assertGreater(v.duracao, 7.5)
            self.assertEqual(v.licenca_categoria, "cc-by")
            self.assertTrue((ger.pasta / v.arquivo_trabalho).is_file())
            # sem candidato adequado (duração mínima maior que qualquer clipe): pendência, sem inventar fonte
            ger2 = am.GerenciadorAssets(tmp / "assets2", http)
            self.assertIsNone(am.obter_videos_para_cena("cena", ["nile"], 30.0, ger2, [commons]))
            self.assertEqual(len(ger2.pendencias), 1)


if __name__ == "__main__":
    unittest.main()
