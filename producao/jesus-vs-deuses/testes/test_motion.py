"""Testes do motor de motion graphics (conteúdo, ponte, cache) e da trilha Web Audio (grade de batidas, medição)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from motor_video import audio_webaudio as aw
from motor_video import motion_bridge as mb
from motor_video import motion_conteudo as mc
from motor_video import script_analyzer as sa
from motor_video import storyboard as sb
from motor_video import timeline_builder as tb
from motor_video.config import Config
from motor_video.timeline_builder import Plano, Timeline

_MOTION = mb.localizar_motion()


def _plano(i, ini, fim, mo=None, fundo=None):
    return Plano(id=f"c{i}#1", cena_id=f"c{i}", secao="1-abertura", inicio=ini, fim=fim, narracao="", descricao="", cor="neutro",
                 fundo=fundo or {"tipo": "motivo", "motivo": "ceu_estrelado", "semente": 1}, camera={"preset": "deriva", "intensidade": 1.0},
                 transicao_entrada={"tipo": "corte" if i == 0 else "dissolve", "duracao": 0.0 if i == 0 else 0.8}, overlays=[{"tipo": "capitulo", "texto": "x"}],
                 fonte={"origem": "gerada por código"}, motion=mo)


class TestConteudo(unittest.TestCase):
    def test_conteudo_coerente(self):
        mc.validar_conteudo()

    def test_cenas_do_storyboard_com_motion(self):
        cenas, _ = sb.carregar()
        com = [c for c in cenas if c.mo]
        self.assertGreaterEqual(len(com), 12)
        self.assertLessEqual(len(com), 0.12 * len(cenas))          # motion é seletivo, não é regra
        for c in com:
            self.assertIn(c.mo, mc.CONTEUDO)
            self.assertFalse(any(o["tipo"] in ("versiculo", "lista", "titulo") for o in c.overlays),
                             f"{c.id}: a ficha de motion não pode colidir com um cartão de versículo/título")

    def test_toda_ficha_diz_a_ordem_da_informacao_e_a_procedencia(self):
        for k, v in mc.CONTEUDO.items():
            p = v["params"]
            self.assertIn(p["ficha"]["categoria"], ("historico", "mitologico", "academico", "religioso", "fonte"), k)
            if v["comp"] == "deus":                                   # ilustração fornecida: nunca apresentada como arte antiga
                self.assertIn("ilustra", p["rodape"].lower(), k)
                self.assertTrue(v["exige_imagem"])
            if v["comp"] in ("mapa", "periodo"):
                self.assertTrue(p.get("rodape"), k)
            if v["comp"].startswith("cena3d_"):                      # reconstrução 3D: sempre rotulada como artística/não arqueológica
                self.assertRegex(p["rodape"].lower(), r"art[ií]stic", k)
                self.assertFalse(v["exige_imagem"], k)

    def test_params_sincronizam_palavras_e_batidas(self):
        al = sa.Alinhamento(palavras=["a", "sabedoria", "poesia", "guerra"], normalizadas=["a", "sabedoria", "poesia", "guerra"],
                            t_ini=[10.0, 10.5, 12.0, 13.0], t_fim=[10.4, 11.9, 12.9, 13.6], reconhecida=[True] * 4, frases=[], duracao_transcricao=14)
        pl = _plano(0, 10.0, 14.0)
        params = mb.montar_params("deus_odin_atributos", pl, al, [9.0, 10.5, 11.5, 14.2, 20.0])
        self.assertEqual([a["t"] for a in params["atributos"]], [0.5, 2.0, 3.0])           # relativos ao início do plano
        self.assertEqual(params["batidas"], [0.5, 1.5, 4.2])                                # só as batidas dentro do plano

    def test_chave_muda_com_conteudo_semente_e_imagem(self):
        p = mb.PedidoMotion("c#1", "mapa_belem", "mapa", 6.0, 0.4, 0.4, params={"a": 1}, seed=3)
        k = mb.chave_pedido(p, 30, 1920, 1080, None, "x")
        self.assertEqual(k, mb.chave_pedido(p, 30, 1920, 1080, None, "x"))
        for outra in (mb.chave_pedido(p, 24, 1920, 1080, None, "x"), mb.chave_pedido(p, 30, 960, 540, None, "x"), mb.chave_pedido(p, 30, 1920, 1080, "abc", "x"),
                      mb.chave_pedido(p, 30, 1920, 1080, None, "y")):
            self.assertNotEqual(k, outra)
        p.params = {"a": 2}
        self.assertNotEqual(k, mb.chave_pedido(p, 30, 1920, 1080, None, "x"))

    def test_planos_e_aplicacao_dos_clipes(self):
        mo = {"conteudo": "mapa_belem", "comp": "mapa", "exige_imagem": False, "imagem": None}
        tl = Timeline(20.0, 20.0, 30, [_plano(0, 0.0, 6.0), _plano(1, 6.0, 13.0, mo=mo), _plano(2, 13.0, 20.0)], [], [])
        ped = tb.coletar_pedidos_motion(tl, None, Path("."), [6.5, 7.0, 25.0])
        self.assertEqual(len(ped), 1)
        p = ped[0]
        self.assertAlmostEqual(p.dur_visivel, 7.0)
        self.assertAlmostEqual(p.t0, 0.4)                            # metade da transição de entrada
        self.assertAlmostEqual(p.t1, 0.4)                            # metade da transição de saída
        self.assertEqual(p.params["batidas"], [0.5, 1.0])
        p.status, p.clipe, p.eventos = "renderizado", "/tmp/x.mp4", [{"t": 1.0, "tipo": "revelar"}, {"t": 2.0, "tipo": "entrada"}]
        tb.aplicar_clipes_motion(tl, ped, 30)
        pl = tl.planos[1]
        self.assertEqual(pl.fundo["tipo"], "video")
        self.assertEqual(pl.fundo["origem"], "motion")
        self.assertFalse(any(o["tipo"] == "capitulo" for o in pl.overlays))
        self.assertEqual([(e["t"], e["tipo"]) for e in tl.eventos_audio], [(7.0, "revelar")])   # só eventos sonoros, no tempo absoluto

    def test_motion_so_quando_ha_imagem_exigida(self):
        c = sb.C("x", "1-abertura", "texto", "d")
        c.mo = "deus_osiris"
        self.assertIsNone(tb._pedido_motion(c, 0, None, 6.0, {"ok": True}))                  # sem imagem fornecida: não há placa
        self.assertIsNone(tb._pedido_motion(c, 0, object(), 6.0, {"ok": False}))              # sem Node/Chromium
        self.assertIsNotNone(tb._pedido_motion(c, 0, type("A", (), {"arquivo_trabalho": "a.jpg"})(), 6.0, {"ok": True}))
        c.mo = "mapa_belem"
        self.assertIsNotNone(tb._pedido_motion(c, 0, None, 6.0, {"ok": True}))
        self.assertIsNone(tb._pedido_motion(c, 1, None, 6.0, {"ok": True}))                  # só o primeiro plano da cena


class TestGradeDeBatidas(unittest.TestCase):
    def _tl(self):
        secoes = [{"secao": "1-abertura", "musica": "misterio", "inicio": 0.0, "fim": 20.0, "ambiencia": []},
                  {"secao": "2-civilizacoes", "musica": "identidade", "inicio": 20.0, "fim": 30.0, "ambiencia": []}]
        return Timeline(30.0, 30.0, 30, [], [], secoes)

    def test_grade_segue_o_andamento_definido_na_composicao(self):
        g = aw.grade_planejada(self._tl())
        self.assertEqual([s["bpm"] for s in g["secoes"]], [60.0, 72.0])
        a = [b for b in g["batidas"] if b["secao"] == 0]
        self.assertEqual(len(a), 20)                                          # 20 s a 60 BPM
        self.assertAlmostEqual(a[1]["t"] - a[0]["t"], 1.0, places=3)
        b = [x for x in g["batidas"] if x["secao"] == 1]
        self.assertAlmostEqual(b[0]["t"], 20.0)                              # cada seção começa no compasso 1
        self.assertTrue(b[0]["forte"] and b[0]["tempo"] == 1)
        self.assertAlmostEqual(b[1]["t"] - b[0]["t"], 60 / 72, places=3)
        self.assertEqual([x["tempo"] for x in b[:5]], [1, 2, 3, 4, 1])

    def test_medicao_reconhece_pulso_e_recusa_o_que_nao_e_mensuravel(self):
        g = aw.grade_planejada(self._tl())
        sr = 48000
        x = np.zeros(int(30 * sr), np.float32)
        t = np.arange(int(0.4 * sr)) / sr
        thump = (np.sin(2 * np.pi * (46 + 70 * np.exp(-t * 25)) * t) * np.exp(-t * 9) * 0.6).astype(np.float32)
        for b in g["batidas"]:
            if b["secao"] == 0:                                               # seção 0: pulso real, com 12 ms de atraso em relação à grade
                i = int((b["t"] + 0.012) * sr)
                x[i:i + len(thump)] += thump[: len(x) - i]
        x[20 * sr:] += (np.sin(2 * np.pi * 220 * np.arange(10 * sr) / sr) * 0.1).astype(np.float32)   # seção 1: só um pad contínuo
        g["secoes"][0]["pulsos"] = [b["t"] for b in g["batidas"] if b["secao"] == 0]       # pulsos que a partitura agendou (vêm do manifesto)
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "m.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", str(wav)], input=x.tobytes(), check=True)
            g = aw.medir_grade(wav, g)
        m0, m1 = g["secoes"][0]["medicao"], g["secoes"][1]["medicao"]
        self.assertTrue(m0["mensuravel"], m0)
        self.assertTrue(m0["confirmada"], m0)
        self.assertGreaterEqual(m0["cobertura_pulsos"], 0.9)
        self.assertLess(abs(m0["desvio_medio_ms"] - 12), 25)                  # o atraso introduzido (12 ms) é medido
        self.assertLess(abs(m0["bpm_medido"] - 60), 1.5)
        self.assertFalse(m1["mensuravel"], m1)                                # sem pulsos planejados: não se inventa grade confirmada
        self.assertFalse(m1["confirmada"], m1)


@unittest.skipIf(_MOTION is None, "Node.js/Chromium do motion não disponíveis")
class TestRenderMotion(unittest.TestCase):
    def test_clipe_h264_yuv420p_e_cache(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cfg = Config(saida=d, motion_largura=320, motion_altura=180, motion_trabalhadores=1)
            cfg.motion_preset = "ultrafast"
            ped = [mb.PedidoMotion("t#1", "teste", "teste", 1.2, 0.1, 0.1, params={}, seed=4)]
            mb.renderizar_clipes(_MOTION, ped, cfg, d / "clipes", d / "tmp", 30)
            self.assertEqual(ped[0].status, "renderizado")
            info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt,width,height,nb_frames,r_frame_rate",
                                              "-of", "json", ped[0].clipe], capture_output=True, text=True).stdout)["streams"][0]
            self.assertEqual((info["codec_name"], info["pix_fmt"], info["width"], info["height"], info["r_frame_rate"]), ("h264", "yuv420p", 320, 180, "30/1"))
            self.assertEqual(int(info["nb_frames"]), 42)                      # (1,2 + 0,1 + 0,1) s a 30 fps
            outro = [mb.PedidoMotion("t#1", "teste", "teste", 1.2, 0.1, 0.1, params={}, seed=4)]
            mb.renderizar_clipes(_MOTION, outro, cfg, d / "clipes", d / "tmp", 30)
            self.assertEqual((outro[0].status, outro[0].clipe), ("reaproveitado", ped[0].clipe))


@unittest.skipIf(_MOTION is None, "Node.js/Chromium do motion não disponíveis")
class TestAudioWeb(unittest.TestCase):
    def test_secao_sintetizada_com_nivel_pico_e_deterministica(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            spec = {"saida": d / "a", "ref": -27.0, "xf": 2.5, "cauda": 4, "janela": 30, "total": 12,
                    "secoes": [{"id": "x", "clima": "identidade", "bpm": 72, "ini": 0, "fim": 10, "nivelDb": -1.0, "ambiencias": ["vento_suave"], "primeira": True}],
                    "eventos": [{"t": 3.0, "tipo": "impacto", "variante": 0}, {"t": 6.0, "tipo": "ping", "variante": 1}]}
            man = aw._executar_node(_MOTION, spec, d, 1)
            s = man["secoes"][0]
            self.assertAlmostEqual(s["rmsMusicaDb"], -27 - 17 - 1.0, delta=1.0)           # corpo da seção no nível pedido
            self.assertLess(s["picoMusicaDb"], -3.0)
            x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", s["musica"], "-f", "f32le", "-"], capture_output=True).stdout, np.float32)
            self.assertTrue(np.isfinite(x).all())
            self.assertGreater(float(np.abs(x).max()), 1e-4)
            self.assertAlmostEqual(man["sfx"][0]["picoDb"], -27 - 4, delta=2.0)               # o impacto fica no pico-alvo (ref - 4 dB)
            # mesma entrada, mesma saída (síntese determinística)
            spec["saida"] = d / "b"
            man2 = aw._executar_node(_MOTION, spec, d, 1)
            y = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", man2["secoes"][0]["musica"], "-f", "f32le", "-"], capture_output=True).stdout, np.float32)
            self.assertTrue(np.array_equal(x, y))


if __name__ == "__main__":
    unittest.main()
