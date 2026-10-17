"""Testes da ponte com o Blender.

Os testes que precisam do Blender real (renderizar quadros e clipes) são pulados se ele não for encontrado.
Para rodá-los: instale o Blender (ou `pip install bpy`) ou aponte `MOTOR_BLENDER` para o executável / Python com bpy.
Os demais (nomes das cenas, planejamento por orçamento, chave de cache) rodam sempre.
"""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from motor_video import blender_bridge as bb
from motor_video import storyboard
from motor_video.config import Config
from motor_video.cenas3d import renderizar as _  # noqa: F401  (o módulo é importável sem bpy)

CENAS_DIR = Path(bb.SCRIPT).parent
_BLENDER = bb.localizar_blender()


def _nomes_registrados() -> set[str]:
    nomes = set()
    for arq in CENAS_DIR.glob("cenas_*.py"):
        nomes.update(re.findall(r'@registrar\("([a-z0-9_]+)"\)', arq.read_text(encoding="utf-8")))
    return nomes


class TestSemBlender(unittest.TestCase):
    def test_cenas_do_storyboard_existem(self):
        cenas, _ = storyboard.carregar()
        registradas = _nomes_registrados()
        usadas = {c.cena3d["cena"] for c in cenas if c.cena3d}
        self.assertTrue(usadas)
        self.assertEqual(usadas - registradas, set(), "o storyboard pede cenas 3D que não existem")

    def test_todas_as_cenas_exigidas_existem(self):
        exigidas = {"templo_egipcio", "templo_grego", "deus_ra", "deus_osiris", "deus_anubis", "deus_zeus", "deus_hades", "deus_odin",
                    "ragnarok", "aldeia_judeia", "lago_galileia", "colina_cruzes", "tumulo_vazio", "mapa_3d", "foto_2_5d"}
        self.assertEqual(exigidas - _nomes_registrados(), set())

    def test_chave_do_clipe_muda_com_o_conteudo(self):
        p = bb.Pedido3D("x#1", "mapa_3d", 5.0, 1, "sempre", {"a": 1}, semente=3)
        k = bb.chave_clipe(p, "teste", 30, "CYCLES")
        self.assertEqual(k, bb.chave_clipe(p, "teste", 30, "CYCLES"))
        self.assertNotEqual(k, bb.chave_clipe(p, "previa", 30, "CYCLES"))
        self.assertNotEqual(k, bb.chave_clipe(p, "teste", 24, "CYCLES"))
        p2 = bb.Pedido3D("x#1", "mapa_3d", 6.0, 1, "sempre", {"a": 1}, semente=3)
        self.assertNotEqual(k, bb.chave_clipe(p2, "teste", 30, "CYCLES"))
        p3 = bb.Pedido3D("x#1", "mapa_3d", 5.0, 1, "sempre", {"a": 2}, semente=3)
        self.assertNotEqual(k, bb.chave_clipe(p3, "teste", 30, "CYCLES"))

    def test_semente_estavel(self):
        self.assertEqual(bb.semente_da_cena("a03-templos#1"), bb.semente_da_cena("a03-templos#1"))
        self.assertNotEqual(bb.semente_da_cena("a03-templos#1"), bb.semente_da_cena("b02-grecia#1"))

    def test_planejamento_respeita_prioridade_e_orcamento(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            cfg = Config(saida=t, qualidade_3d="teste", orcamento_3d_min=8.0)
            pedidos = [bb.Pedido3D("c#1", "mapa_3d", 20.0, 2, "sem_imagem"), bb.Pedido3D("a#1", "templo_egipcio", 5.0, 1, "sempre"),
                       bb.Pedido3D("b#1", "templo_grego", 6.0, 1, "sempre")]
            out = bb.planejar(pedidos, cfg, None, t / "tmp", t / "medidas.json")
            st = {p.plano_id: p.status for p in out}
            self.assertEqual(st["a#1"], "selecionado")
            self.assertEqual(st["b#1"], "selecionado")
            self.assertEqual(st["c#1"], "cortado_orcamento")      # P2 de 20 s estoura o orçamento; as P1 vêm antes
            texto = bb.descrever_plano(out, cfg)
            self.assertIn("Total estimado", texto)
            self.assertIn("[ ]", texto)
            cfg.orcamento_3d_min = None
            out = bb.planejar(pedidos, cfg, None, t / "tmp", t / "medidas.json")
            self.assertTrue(all(p.status == "selecionado" for p in out))


@unittest.skipIf(_BLENDER is None, "Blender não encontrado (defina MOTOR_BLENDER para rodar estes testes)")
class TestComBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_listagem_das_cenas(self):
        proc = subprocess.run(_BLENDER.comando(["--listar"]), capture_output=True, text=True, timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        m = re.search(r"CENAS3D (\[.*\])", proc.stdout)
        self.assertIsNotNone(m, proc.stdout)
        self.assertEqual(set(json.loads(m.group(1))), _nomes_registrados())

    def test_cena_desconhecida_da_erro_claro(self):
        with self.assertRaises(bb.ErroBlender) as e:
            bb._executar_blender(_BLENDER, ["--cena", "nao_existe", "--saida", str(self.d / "x")], self.d / "x", 1)
        self.assertIn("cena desconhecida", str(e.exception))

    def test_quadro_unico_nao_e_preto(self):
        from PIL import Image
        import numpy as np
        saida = self.d / "um"
        bb._executar_blender(_BLENDER, ["--cena", "mapa_3d", "--saida", str(saida), "--duracao", "1", "--fps", "1", "--largura", "192", "--altura", "108",
                                        "--amostras", "2", "--rebotes", "2", "--quadro", "0.5"], saida, 1)
        im = Image.open(saida / "quadro_unico.png").convert("L")
        self.assertEqual(im.size, (192, 108))
        a = np.asarray(im, dtype=float)
        self.assertGreater(a.mean(), 8)
        self.assertGreater(a.std(), 4)         # tem conteúdo, não é uma cor lisa
        meta = json.loads((saida / "meta.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["rotulo"])

    def _quadro(self, nome, params):
        from PIL import Image
        import numpy as np
        saida = self.d / nome
        bb._executar_blender(_BLENDER, ["--cena", "mapa_3d", "--saida", str(saida), "--duracao", "1", "--fps", "1", "--largura", "192", "--altura", "108",
                                        "--amostras", "2", "--rebotes", "2", "--quadro", "0.5", "--params", json.dumps(params)], saida, 1)
        return np.asarray(Image.open(saida / "quadro_unico.png").convert("RGB"), dtype=float), json.loads((saida / "meta.json").read_text(encoding="utf-8"))

    def test_hdri_e_modelo_externos(self):
        """Recursos CC0 (HDRI / glTF) entram pelos parâmetros da cena; um recurso inválido é ignorado, não derruba o render."""
        from PIL import Image
        import numpy as np
        hdri = self.d / "ceu.png"
        grad = np.linspace(0, 255, 128, dtype=np.uint8)
        Image.fromarray(np.dstack([np.tile(grad, (64, 1)), np.full((64, 128), 40, np.uint8), np.full((64, 128), 200, np.uint8)])).save(hdri)
        glb = self.d / "caixa.glb"
        script = self.d / "cria_glb.py"
        script.write_text("import bpy, sys\nbpy.ops.wm.read_factory_settings(use_empty=True)\nbpy.ops.mesh.primitive_cube_add(size=40, location=(0, 0, 6))\n"
                          "bpy.ops.export_scene.gltf(filepath=sys.argv[sys.argv.index('--') + 1])\n", encoding="utf-8")
        proc = subprocess.run(_BLENDER.comando([str(glb)], script=script), capture_output=True, text=True, timeout=180)
        self.assertTrue(glb.is_file(), proc.stdout[-500:] + proc.stderr[-500:])
        base, meta0 = self._quadro("base", {})
        self.assertNotIn("recursos", meta0)
        com_hdri, meta1 = self._quadro("hdri", {"hdri": str(hdri), "hdri_forca": 2.0})
        self.assertEqual(meta1["recursos"]["hdri"], "ceu.png")
        self.assertGreater(np.abs(com_hdri - base).mean(), 1.0)          # a iluminação realmente mudou
        com_modelo, meta2 = self._quadro("modelo", {"modelos": [{"arquivo": str(glb), "loc": [0, 0, 6], "escala": 1.0}]})
        self.assertEqual(meta2["recursos"]["modelos"], ["caixa.glb"])
        self.assertGreater(np.abs(com_modelo - base).mean(), 1.0)
        _, meta3 = self._quadro("invalido", {"hdri": str(self.d / "nao_existe.hdr"), "modelos": [{"arquivo": str(self.d / "x.xyz")}]})
        self.assertEqual(len(meta3["recursos_ignorados"]), 2)

    def test_clipe_completo_cache_e_cancelamento(self):
        cfg = Config(saida=self.d / "saida", qualidade_3d="teste")
        cfg.saida.mkdir(parents=True)
        clipes, temp = self.d / "clipes", self.d / "temp"
        clipes.mkdir()
        p = bb.Pedido3D("t#1", "mapa_3d", 0.5, 1, "sempre", semente=5)
        prog = []
        arq = bb.renderizar_pedido(_BLENDER, p, cfg, clipes, temp, 30, lambda f, n: prog.append((f, n)))
        self.assertEqual(p.status, "renderizado")
        self.assertTrue(prog and prog[-1][0] == prog[-1][1])
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name",
                                          "-of", "json", str(arq)], capture_output=True, text=True).stdout)["streams"][0]
        self.assertEqual((info["width"], info["height"], info["codec_name"]), (1920, 1080, "h264"))
        self.assertEqual(info["r_frame_rate"], "30/1")
        self.assertAlmostEqual(int(info["nb_frames"]), 15, delta=2)         # 0,5 s a 30 fps
        # segunda chamada: reaproveita o clipe, sem abrir o Blender
        p2 = bb.Pedido3D("t#1", "mapa_3d", 0.5, 1, "sempre", semente=5)
        arq2 = bb.renderizar_pedido(_BLENDER, p2, cfg, clipes, temp, 30)
        self.assertEqual((p2.status, arq2), ("reaproveitado", arq))
        # cancelamento
        (cfg.saida / "CANCELAR.txt").write_text("x")
        p3 = bb.Pedido3D("t#2", "mapa_3d", 0.5, 1, "sempre", semente=6)
        with self.assertRaises(bb.ErroBlender) as e:
            bb.renderizar_pedido(_BLENDER, p3, cfg, clipes, temp, 30)
        self.assertIn("cancelado", str(e.exception))


if __name__ == "__main__":
    unittest.main()
