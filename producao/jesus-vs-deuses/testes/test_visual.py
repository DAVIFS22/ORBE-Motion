import random
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from motor_video import visual_effects as ve

from .util import gerar_video


class TestCamera(unittest.TestCase):
    def test_recorte_sempre_dentro_da_imagem_e_contem_o_foco(self):
        rnd = random.Random(3)
        for _ in range(300):
            w, h = rnd.choice([(3000, 1800), (2400, 1350), (4000, 1500), (2000, 1400)])
            x0, y0 = rnd.uniform(0, 0.6), rnd.uniform(0, 0.6)
            foco = (x0, y0, x0 + rnd.uniform(0.08, 0.35), y0 + rnd.uniform(0.08, 0.35))
            preset = rnd.choice(ve.PRESETS)
            cam = ve.calcular_camera(w, h, preset, rnd.uniform(0.5, 2.0), foco, rnd.uniform(3, 20))
            if cam.layout != "cover":
                continue
            fx0, fy0, fx1, fy1 = foco[0] * w, foco[1] * h, foco[2] * w, foco[3] * h
            for p in (0, 0.2, 0.5, 0.8, 1):
                x, y, cw, ch = cam.retangulo(p)
                self.assertGreaterEqual(x, -1e-6, preset)
                self.assertGreaterEqual(y, -1e-6, preset)
                self.assertLessEqual(x + cw, w + 1e-6, preset)
                self.assertLessEqual(y + ch, h + 1e-6, preset)
                self.assertAlmostEqual(cw / ch, 16 / 9, places=5)
                if fx1 - fx0 <= cw and fy1 - fy0 <= ch:      # o foco cabe: nunca é cortado
                    self.assertLessEqual(x, fx0 + 1e-6, f"{preset} {foco}")
                    self.assertGreaterEqual(x + cw, fx1 - 1e-6, f"{preset} {foco}")
                    self.assertLessEqual(y, fy0 + 1e-6, f"{preset} {foco}")
                    self.assertGreaterEqual(y + ch, fy1 - 1e-6, f"{preset} {foco}")

    def test_zoom_nao_corta_foco_grande(self):
        cam = ve.calcular_camera(3000, 1700, "zoom_in", 2.0, (0.02, 0.05, 0.98, 0.95), 10)   # monumento ocupa quase tudo
        x, y, cw, ch = cam.retangulo(1.0)
        self.assertGreater(cw, 0.93 * 3000 * 0.9)      # praticamente sem zoom

    def test_layout_contain_para_retratos(self):
        self.assertEqual(ve.calcular_camera(2000, 3000, "zoom_in").layout, "contain")
        self.assertEqual(ve.calcular_camera(3000, 1700, "zoom_in").layout, "cover")

    def test_panoramica_limitada_em_velocidade(self):
        cam = ve.calcular_camera(8000, 1500, "pan_dir", 1.0, None, 10.0)
        _, _, cw, _ = cam.retangulo(0)
        percorrido = abs(cam.cx1 - cam.cx0)
        self.assertLessEqual(percorrido, 0.05 * 10.0 * (1500 * 16 / 9) + 1)
        self.assertGreater(percorrido, 0)

    def test_foco_automatico_fica_na_regiao_contrastada(self):
        img = Image.new("RGB", (800, 450), (90, 90, 90))
        for x in range(500, 650):
            for y in range(100, 250):
                img.putpixel((x, y), (255, 255, 255) if (x // 6 + y // 6) % 2 else (0, 0, 0))
        x0, y0, x1, y1 = ve.detectar_foco(img)
        self.assertTrue(x0 > 0.35 and x1 < 0.95 and y0 < 0.45)


class TestFontesEComposicao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _img(self, nome, cor, w=1600, h=900, ruido=6.0):
        rng = np.random.default_rng(5)
        a = np.clip(np.array(cor, np.float32) + rng.normal(0, ruido, (h, w, 3)), 0, 255).astype(np.uint8)
        caminho = self.d / nome
        Image.fromarray(a).save(caminho, quality=95)
        return str(caminho)

    def test_movimento_muda_o_quadro_e_respiro_quase_nao(self):
        arq = self._img("a.jpg", (120, 90, 60))
        im = np.asarray(Image.open(arq))
        im2 = im.copy()
        im2[:, :800] = 200
        Image.fromarray(im2).save(self.d / "b.jpg", quality=95)
        mov = ve.FonteVisual({"tipo": "imagem", "arquivo": str(self.d / "b.jpg")}, "neutro",
                             {"preset": "pan_dir", "intensidade": 1.0, "foco": [0.45, 0.4, 0.55, 0.6]}, 8, 640, 360, None, True)
        q0, q1 = np.asarray(mov.quadro(0.0), np.float32), np.asarray(mov.quadro(1.0), np.float32)
        self.assertEqual(q0.shape, (360, 640, 3))
        self.assertGreater(np.abs(q0 - q1).mean(), 0.2)
        sub = ve.FonteVisual({"tipo": "imagem", "arquivo": arq}, "neutro", {"preset": "respiro"}, 8, 640, 360, None, True)
        self.assertLess(np.abs(np.asarray(sub.quadro(0.0), np.float32) - np.asarray(sub.quadro(1.0), np.float32)).mean(), 3.0)

    def test_retrato_vai_para_contain_com_fundo_desfocado(self):
        arq = self._img("r.jpg", (30, 120, 60), 800, 1200)
        f = ve.FonteVisual({"tipo": "imagem", "arquivo": arq}, "neutro", {"preset": "zoom_in"}, 6, 640, 360, None, True)
        self.assertEqual(f.camera.layout, "contain")
        q = np.asarray(f.quadro(0.5))
        self.assertEqual(q.shape, (360, 640, 3))
        self.assertGreater(q[:, 5:60].mean(), 10)          # as laterais não ficam pretas (fundo desfocado)

    def test_transicoes_e_fades(self):
        a, b = self._img("a.jpg", (220, 40, 40)), self._img("b.jpg", (40, 40, 220))
        planos = [{"id": "a", "inicio": 0.0, "fim": 4.0, "fundo": {"tipo": "imagem", "arquivo": a}, "camera": {"preset": "respiro"}, "cor": "neutro", "overlays": []},
                  {"id": "b", "inicio": 4.0, "fim": 8.0, "fundo": {"tipo": "imagem", "arquivo": b}, "camera": {"preset": "respiro"}, "cor": "neutro",
                   "transicao_entrada": {"tipo": "dissolve", "duracao": 1.0}, "overlays": []}]
        comp = ve.Compositor(planos, 320, 180, 10, 8.0, None, fade_inicio=1.0, fade_fim=1.0, rapido=True, grao=False)
        med = lambda n: np.asarray(comp.quadro(n), np.float32).reshape(-1, 3).mean(axis=0)
        self.assertGreater(med(30)[0], med(30)[2] + 60)         # antes: vermelho
        self.assertGreater(med(50)[2], med(50)[0] + 60)         # depois: azul
        meio = med(40)
        self.assertGreater(meio[0], 40)                         # no meio da dissolução há os dois
        self.assertGreater(meio[2], 40)
        self.assertLess(med(0).max(), 15)                       # começa em preto (fade-in)
        self.assertLess(med(79).max(), 40)                      # termina em preto (fade-out)
        comp.fechar()

    def test_grade_preserva_o_matiz(self):
        for cor, canal in (((220, 40, 40), 0), ((40, 200, 60), 1), ((40, 60, 220), 2)):
            arq = self._img("m.jpg", cor)
            f = ve.FonteVisual({"tipo": "imagem", "arquivo": arq}, "neutro", {"preset": "respiro"}, 4, 320, 180, None, True)
            media = np.asarray(f.quadro(0.5), np.float32).reshape(-1, 3).mean(axis=0)
            self.assertEqual(int(np.argmax(media)), canal)
            self.assertGreater(media[canal], media.mean() + 40)

    def test_dip_black_escurece_no_meio(self):
        a, b = self._img("a.jpg", (200, 200, 200)), self._img("b.jpg", (200, 200, 200))
        planos = [{"id": "a", "inicio": 0.0, "fim": 3.0, "fundo": {"tipo": "imagem", "arquivo": a}, "camera": {"preset": "respiro"}, "overlays": []},
                  {"id": "b", "inicio": 3.0, "fim": 6.0, "fundo": {"tipo": "imagem", "arquivo": b}, "camera": {"preset": "respiro"},
                   "transicao_entrada": {"tipo": "dip_black", "duracao": 1.0}, "overlays": []}]
        comp = ve.Compositor(planos, 320, 180, 10, 6.0, None, fade_inicio=0.0, fade_fim=0.0, rapido=True, grao=False)
        escuro = np.asarray(comp.quadro(30), np.float32).mean()
        claro = np.asarray(comp.quadro(15), np.float32).mean()
        self.assertLess(escuro, claro * 0.35)

    def test_overlays_aparecem_so_na_janela(self):
        a = self._img("a.jpg", (60, 60, 60), ruido=0.0)
        planos = [{"id": "a", "inicio": 0.0, "fim": 6.0, "fundo": {"tipo": "imagem", "arquivo": a}, "camera": {"preset": "respiro"}, "overlays": [
            {"tipo": "rotulo", "texto": "Reconstrução artística em 3D, não é registro histórico", "atraso": 2.0, "duracao": 2.0}]}]
        comp = ve.Compositor(planos, 640, 360, 10, 6.0, None, fade_inicio=0.0, fade_fim=0.0, rapido=True, grao=False)
        antes, durante, depois = (np.asarray(comp.quadro(n), np.float32) for n in (10, 30, 55))
        zona = (slice(300, 350), slice(0, 400))
        self.assertGreater(np.abs(durante[zona] - antes[zona]).mean(), 1.0)
        self.assertLess(np.abs(depois[zona] - antes[zona]).mean(), 0.5)

    def test_fonte_video_sequencial_igual_ao_acesso_aleatorio(self):
        v = gerar_video(self.d / "v.mp4", 3.0, 640, 360, 10)
        seq = ve.FonteVideo(str(v), 0.0, 3.0, 320, 180, 10)
        quadros = [np.asarray(seq.quadro(k / 30.0), np.float32) for k in range(0, 31, 5)]
        for k, q in zip(range(0, 31, 5), quadros):
            novo = ve.FonteVideo(str(v), 0.0, 3.0, 320, 180, 10)
            self.assertLess(np.abs(np.asarray(novo.quadro(k / 30.0), np.float32) - q).mean(), 0.5, k)
            novo.fechar()
        self.assertGreater(np.abs(quadros[0] - quadros[-1]).mean(), 5)       # o vídeo realmente muda
        ultimo = seq.quadro(1.2)                                              # além do fim: mantém o último quadro
        self.assertEqual(ultimo.size, (320, 180))
        seq.fechar()

    def test_cena_com_video_no_compositor(self):
        v = gerar_video(self.d / "v.mp4", 4.0, 640, 360, 10)
        planos = [{"id": "v", "inicio": 0.0, "fim": 3.0, "fundo": {"tipo": "video", "arquivo": str(v), "fps": 10, "inicio_clip": 0.0},
                   "camera": {}, "overlays": []}]
        comp = ve.Compositor(planos, 320, 180, 10, 3.0, None, fade_inicio=0.0, fade_fim=0.0, rapido=True, grao=False)
        self.assertGreater(np.abs(np.asarray(comp.quadro(2), np.float32) - np.asarray(comp.quadro(25), np.float32)).mean(), 5)
        comp.fechar()


if __name__ == "__main__":
    unittest.main()
