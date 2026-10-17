import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from motor_video import audio_mixer as am
from motor_video import quality_checker as qc
from motor_video import video_renderer as vr
from motor_video.config import Config, ErroProducao
from motor_video.timeline_builder import Plano, Timeline

from .test_audio import _fala


def _plano(i, ini, fim, motivo, trans="dissolve", overlays=None, preset="deriva"):
    return Plano(id=f"p{i}#1", cena_id=f"p{i}", secao="1-abertura", inicio=ini, fim=fim, narracao="", descricao="", cor="neutro",
                 fundo={"tipo": "motivo", "motivo": motivo, "semente": 3 + i}, camera={"preset": preset, "intensidade": 1.0},
                 transicao_entrada={"tipo": "corte" if i == 0 else trans, "duracao": 0.0 if i == 0 else 0.6}, overlays=overlays or [],
                 fonte={"origem": "gerada por código"})


class TestRenderizacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        cls.cfg = Config(saida=cls.d / "saida", largura=320, altura=180, fps=12, crf=30, preset="ultrafast", trabalhadores=2,
                         segundos_por_bloco=1.5, rapido=True)
        cls.cfg.saida.mkdir(parents=True)
        cls.dur = 4.0
        cls.planos = [_plano(0, 0.0, 1.8, "ceu_estrelado", overlays=[{"tipo": "titulo", "texto": "Teste", "subtitulo": None, "atraso": 0.2, "duracao": 1.4}]),
                      _plano(1, 1.8, 3.0, "deserto_egito", "dip_gold"), _plano(2, 3.0, 4.0, "amanhecer", "dissolve")]
        cls.tl = Timeline(cls.dur - 0.5, cls.dur, 12, cls.planos, [], [])
        cls.fala = _fala(cls.d / "fala.wav", cls.dur - 0.5, [(0.3, 3.2)])
        cls.narr = am.medir_narracao(cls.fala)
        cls.mix = cls.d / "mix.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(cls.fala), "-af", f"apad=whole_dur={cls.dur},pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s24le",
                        str(cls.mix)], check=True)
        cls.temp = cls.cfg.saida / "06-temporarios"
        cls.mp4 = cls.d / "saida" / "final.mp4"
        cls.stats = vr.renderizar_video(cls.cfg, cls.tl, cls.d / "imagens", cls.temp, None, None, cls.mix, cls.mp4)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_video_gerado_e_validado(self):
        self.assertEqual(self.stats["encoder"], "libx264")
        res = qc.verificar(self.mp4, self.fala, self.narr, self.tl, self.cfg, self.d / "imagens", None, None, self.temp / "procedural")
        falhas = [(i.nome, i.detalhe) for i in res.itens if i.status == "falha"]
        self.assertEqual(falhas, [])
        nomes = {i.nome for i in res.itens}
        self.assertTrue({"fluxos", "duração e sincronia de faixas", "quadros", "reprodução", "telas pretas", "sincronia áudio",
                         "quadros x linha do tempo", "clipping"} <= nomes)

    def test_frames_e_duracao_exatos(self):
        p = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames,width,height,r_frame_rate",
                            "-of", "json", str(self.mp4)], capture_output=True, text=True)
        v = json.loads(p.stdout)["streams"][0]
        self.assertEqual(int(v["nb_read_frames"]), 48)
        self.assertEqual((v["width"], v["height"], v["r_frame_rate"]), (320, 180, "12/1"))

    def test_blocos_sao_reaproveitados(self):
        stats2 = vr.renderizar_video(self.cfg, self.tl, self.d / "imagens", self.temp, None, None, self.mix, self.d / "saida" / "final2.mp4")
        self.assertEqual(stats2["blocos_reaproveitados"], stats2["blocos"])
        self.assertGreaterEqual(stats2["blocos"], 3)

    def test_chave_do_bloco_so_depende_dos_planos_proximos(self):
        planos = [Plano(id=f"p{i}", cena_id="c", secao="s", inicio=i * 5.0, fim=(i + 1) * 5.0, narracao="", descricao="", cor="neutro",
                        fundo={"tipo": "motivo", "motivo": "ceu_estrelado", "semente": i}, camera={}, transicao_entrada={"tipo": "dissolve", "duracao": 0.6},
                        overlays=[], fonte={}) for i in range(100)]
        ds = [dict(p.__dict__) for p in planos]

        def chave(lista, t0, t1):
            t = {"f0": int(t0 * 12), "f1": int(t1 * 12), "w": 320, "h": 180, "fps": 12, "dur_total": 500.0, "enc": [], "legendas": [], "rapido": True,
                 "planos": vr._planos_para_bloco(lista, t0, t1)}
            return vr._chave_bloco(t)
        antes = chave(ds, 10.0, 30.0)
        ds[90]["fundo"] = {"tipo": "motivo", "motivo": "luz_dourada", "semente": 1}       # plano distante é alterado
        self.assertEqual(chave(ds, 10.0, 30.0), antes)                                     # o bloco do início continua válido
        ds[4]["fundo"] = {"tipo": "motivo", "motivo": "luz_dourada", "semente": 1}         # plano dentro do bloco é alterado
        self.assertNotEqual(chave(ds, 10.0, 30.0), antes)
        self.assertLess(len(vr._planos_para_bloco(ds, 10.0, 30.0)), 12)                    # só os planos próximos entram no bloco

    def test_qc_reprova_video_com_tela_preta_e_quadros_errados(self):
        ruim = self.d / "ruim.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s=320x180:r=12:d={self.dur}", "-i", str(self.mix),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(ruim)], check=True)
        res = qc.verificar(ruim, self.fala, self.narr, self.tl, self.cfg, self.d / "imagens", None, None, self.temp / "procedural")
        self.assertFalse(res.ok)
        reprovados = {i.nome for i in res.itens if i.status == "falha"}
        self.assertIn("telas pretas", reprovados)
        self.assertIn("quadros x linha do tempo", reprovados)

    def test_qc_reprova_video_mais_curto_que_a_narracao(self):
        curto = self.d / "curto.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(self.mp4), "-t", "2.0", "-c", "copy", str(curto)], check=True)
        res = qc.verificar(curto, self.fala, self.narr, self.tl, self.cfg, self.d / "imagens", None, None, self.temp / "procedural")
        self.assertFalse(res.ok)
        self.assertIn("duração e sincronia de faixas", {i.nome for i in res.itens if i.status == "falha"})

    def test_qc_detecta_atraso_de_audio(self):
        atrasado = self.d / "atrasado.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(self.mp4), "-itsoffset", "0", "-i", str(self.mp4), "-map", "0:v", "-map", "1:a",
                        "-af", "adelay=120|120", "-c:v", "copy", "-c:a", "aac", str(atrasado)], check=True)
        res = qc.verificar(atrasado, self.fala, self.narr, self.tl, self.cfg, self.d / "imagens", None, None, self.temp / "procedural")
        self.assertIn("sincronia áudio", {i.nome for i in res.itens if i.status == "falha"})


class TestRobustez(unittest.TestCase):
    def test_encoder_cpu_e_fallback_gpu(self):
        cfg = Config(saida=Path("."), encoder="cpu")
        self.assertEqual(vr.detectar_encoder(cfg).nome, "libx264")
        cfg.encoder = "gpu"
        enc = vr.detectar_encoder(cfg)        # neste ambiente não há GPU: volta para a CPU sem quebrar
        self.assertIn(enc.nome, ("libx264", "h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"))
        self.assertEqual(vr.detectar_encoder(Config(saida=Path("."), encoder="auto")).nome, "libx264")

    def test_espaco_em_disco_insuficiente(self):
        with tempfile.TemporaryDirectory() as d, mock.patch("shutil.disk_usage") as du:
            du.return_value = mock.Mock(free=50_000_000)
            with self.assertRaises(ErroProducao) as e:
                vr.verificar_espaco(Path(d), 1800.0)
            self.assertIn("insuficiente", str(e.exception))
            du.return_value = mock.Mock(free=500_000_000_000)
            vr.verificar_espaco(Path(d), 1800.0)

    def test_cancelamento_por_arquivo(self):
        with tempfile.TemporaryDirectory() as d:
            cancelar = Path(d) / "CANCELAR.txt"
            cancelar.write_text("x")
            tarefa = {"idx": 0, "f0": 0, "f1": 10, "saida": str(Path(d) / "b.mp4")}
            with self.assertRaises(vr.Cancelado):
                vr._executar_blocos([tarefa], 1, [tarefa], vr._Progresso(10), cancelar)

    def test_limpeza_so_apaga_a_pasta_de_temporarios(self):
        with tempfile.TemporaryDirectory() as d:
            seguro = Path(d) / "importante"
            seguro.mkdir()
            (seguro / "a.txt").write_text("x")
            vr.limpar_temporarios(seguro)
            self.assertTrue((seguro / "a.txt").exists())          # nome diferente de 06-temporarios: não apaga
            temp = Path(d) / "06-temporarios"
            temp.mkdir()
            (temp / "bloco.mp4").write_text("x")
            vr.limpar_temporarios(temp)
            self.assertFalse(temp.exists())


if __name__ == "__main__":
    unittest.main()
