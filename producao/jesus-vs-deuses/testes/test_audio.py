import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from motor_video import audio_mixer as am
from motor_video import audio_synth as syn
from motor_video.timeline_builder import Timeline

from .util import gerar_wav


def _rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12)


def _ler(caminho, taxa=48000):
    # canal esquerdo apenas: o downmix estéreo->mono do FFmpeg somaria L+R (+3 dB) e distorceria as comparações
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(caminho), "-af", "pan=mono|c0=c0", "-ar", str(taxa), "-f", "f32le", "-"],
                          capture_output=True, check=True)
    return np.frombuffer(proc.stdout, np.float32)


def _fala(caminho: Path, dur: float, trechos, nivel=0.15):
    """WAV mono: ruído banda-passante apenas nos `trechos` (início, fim) em segundos."""
    rng = np.random.default_rng(1)
    x = syn._ruido_banda(int(dur * 48000), 200, 3000, rng, 2) * nivel
    env = np.zeros(len(x), np.float32)
    for a, b in trechos:
        env[int(a * 48000):int(b * 48000)] = 1
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", "48000", "-ac", "1", "-i", "-", "-c:a", "pcm_s24le", str(caminho)],
                   input=(x * env).astype(np.float32).tobytes(), check=True)
    return caminho


class TestSintese(unittest.TestCase):
    def test_ambiencias_validas(self):
        for nome in syn.BEDS:
            x = syn.ambiencia(nome, 12.0, 3)
            self.assertEqual(x.shape, (12 * 48000, 2), nome)
            self.assertTrue(np.isfinite(x).all(), nome)
            self.assertGreater(np.abs(x).max(), 0.01, nome)

    def test_efeitos_normalizados_e_variantes_diferentes(self):
        for f in (syn.impacto, syn.whoosh):
            a, b = f(0), f(1)
            self.assertTrue(np.isfinite(a).all())
            self.assertAlmostEqual(float(np.abs(a).max()), 1.0, places=3)
            self.assertFalse(a.shape == b.shape and np.allclose(a, b), f.__name__)    # não repete o mesmo efeito
        self.assertEqual(len(syn.impacto(0)) / 48000, syn.PRELUDIO_S + 3.4)

    def test_climas_musicais(self):
        for clima in syn.CLIMAS:
            x = syn.segmento_musica(clima, 0, 3.0, 1)
            self.assertTrue(np.isfinite(x).all(), clima)
            self.assertAlmostEqual(_rms_db(x), -20.0, delta=0.5)

    def test_passos_e_piano(self):
        self.assertTrue(np.isfinite(syn.passos(5.0)).all())
        n = syn.nota_piano(syn.f("A4"), 2.0)
        espectro = np.abs(np.fft.rfft(n[:, 0]))
        pico = np.argmax(espectro) * 48000 / len(n)
        self.assertAlmostEqual(pico, 440.0, delta=3.0)        # a nota tem a afinação pedida


class TestAutomacao(unittest.TestCase):
    def test_curva(self):
        c = am.Curva(10.0)
        c.chaves([(0, 0.0), (5, -10.0), (10, 0.0)])
        self.assertAlmostEqual(float(c.db[int(2.5 * am.RES_CURVA)]), -5.0, places=1)
        c.limitar(6.0, 8.0, -50.0, 0.5, 0.5)
        self.assertLess(float(c.db[int(7 * am.RES_CURVA)]), -45)
        self.assertGreater(float(c.db[int(9 * am.RES_CURVA)]), -10)    # voltou
        d = am.Curva(10.0)
        d.somar_local(2.0, 4.0, 0.0, 6.0, manter=True)
        self.assertAlmostEqual(float(d.db[int(9 * am.RES_CURVA)]), 6.0, places=1)


class TestMixagem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _tl(self, eventos=None, dur_audio=20.0, dur_video=22.5):
        secoes = [{"secao": "a", "inicio": 0.0, "fim": 10.0, "musica": "misterio", "ambiencia": ["vento_suave"]},
                  {"secao": "b", "inicio": 10.0, "fim": dur_video, "musica": "encerramento", "ambiencia": ["vento_suave"]}]
        return Timeline(dur_audio, dur_video, 30, [], eventos or [], secoes)

    def test_stems_efeitos_e_silencios(self):
        eventos = [{"t": 3.0, "tipo": "impacto"}, {"t": 5.0, "tipo": "whoosh"}, {"t": 6.0, "tipo": "nota"}, {"t": 8.0, "tipo": "passos", "dur": 3.0},
                   {"t": 12.0, "tipo": "silencio", "dur": 3.0, "cena": "x"}]
        tl = self._tl(eventos)
        fala = _fala(self.d / "n.wav", 20.0, [(0, 20)])
        narr = am.medir_narracao(fala)
        st = am.construir_stems(tl, narr, self.d / "audio")
        for chave in ("musica", "efeitos"):
            x = _ler(st[chave])
            self.assertAlmostEqual(len(x) / 48000, 22.5, delta=0.05)           # stems têm a duração do vídeo
            self.assertTrue(np.isfinite(x).all())
            self.assertLess(np.abs(x).max(), 0.99)                              # sem clipping
        m = _ler(st["musica"])
        fx = _ler(st["efeitos"])
        seg = lambda x, a, b: x[int(a * 48000):int(b * 48000)]
        self.assertLess(_rms_db(seg(m, 13.2, 14.5)), _rms_db(seg(m, 10.5, 11.5)) - 20)     # silêncio sob demanda (música)
        self.assertLess(_rms_db(seg(fx, 13.2, 14.5)), _rms_db(seg(fx, 10.5, 11.5)) - 15)   # e dos efeitos
        self.assertLess(_rms_db(seg(m, 21.5, 22.5)), _rms_db(seg(m, 1.0, 3.0)) - 20)        # fade-out final limpo
        self.assertGreater(_rms_db(seg(fx, 3.0, 3.6)), _rms_db(seg(fx, 1.0, 1.5)) + 6)      # o impacto aparece no tempo certo
        usados = {u["tipo"] for u in st["fontes"]}
        self.assertTrue({"musica", "ambiencia", "impacto", "whoosh", "nota", "passos"} <= usados)
        self.assertTrue(all("sintetiz" in u["origem"] or "arquivo" in u["origem"] for u in st["fontes"]))

    def test_arquivo_do_usuario_tem_prioridade(self):
        pasta = self.d / "musicas"
        gerar_wav(pasta / "misterio-trilha.wav", 6.0, 48000, 330.0, 2, 0.2)
        tl = self._tl()
        narr = am.medir_narracao(_fala(self.d / "n.wav", 20.0, [(0, 20)]))
        st = am.construir_stems(tl, narr, self.d / "audio", [pasta / "misterio-trilha.wav"], None)
        orig = [u["origem"] for u in st["fontes"] if u["tipo"] == "musica" and u["nome"] == "misterio"]
        self.assertTrue(orig and "arquivo do usuário" in orig[0])

    def test_ducking_sincronia_e_sem_clipping(self):
        tl = self._tl(dur_audio=20.0, dur_video=22.5)
        fala = _fala(self.d / "n.wav", 20.0, [(1.0, 8.0), (12.0, 19.0)])
        narr = am.medir_narracao(fala)
        st = am.construir_stems(tl, narr, self.d / "audio")
        mix = self.d / "mix.wav"
        info = am.mixar(fala, 1, st["musica"], st["efeitos"], 22.5, narr, mix, normalizar=False)
        self.assertIsNone(info["aviso"])
        m = _ler(mix)
        n = np.pad(_ler(fala), (0, len(m) - len(_ler(fala))))
        self.assertEqual(len(m) / 48000, 22.5)
        resto = m - n[:len(m)]                                 # o que não é narração: música + efeitos já com ducking
        soma_stems = _ler(st["musica"]) + _ler(st["efeitos"])  # a mesma mistura SEM ducking
        seg = lambda x, a, b: x[int(a * 48000):int(b * 48000)]
        # narração intacta: o mix correlaciona perfeitamente com ela, no mesmo instante (sem atraso)
        c = np.corrcoef(seg(m, 2, 7), seg(n, 2, 7))[0, 1]
        self.assertGreater(c, 0.97)
        # durante a fala, música e efeitos caem bem abaixo do que seriam sem ducking; nas pausas ficam como estão
        queda_fala = _rms_db(seg(resto, 3, 7)) - _rms_db(seg(soma_stems, 3, 7))
        queda_pausa = _rms_db(seg(resto, 8.6, 9.6)) - _rms_db(seg(soma_stems, 8.6, 9.6))
        self.assertLess(queda_fala, -4.0)
        self.assertGreater(queda_pausa, -1.5)
        self.assertLess(np.abs(m).max(), 0.99)                 # sem clipping

    def test_loudness_alvo_e_pico(self):
        tl = self._tl()
        fala = _fala(self.d / "n.wav", 20.0, [(1.0, 19.0)])
        narr = am.medir_narracao(fala)
        st = am.construir_stems(tl, narr, self.d / "audio")
        mix = self.d / "mix.wav"
        info = am.mixar(fala, 1, st["musica"], st["efeitos"], 22.5, narr, mix, alvo_lufs=-16.0)
        med = am.loudness(mix, -16.0)
        self.assertAlmostEqual(float(med["input_i"]), -16.0, delta=0.8)
        self.assertLessEqual(float(med["input_tp"]), -1.0)

    def test_medir_narracao(self):
        w = _fala(self.d / "n.wav", 10.0, [(2.0, 4.0)], 0.2)
        narr = am.medir_narracao(w)
        self.assertAlmostEqual(narr["duracao_s"], 10.0, places=1)
        ativ = narr["atividade"]
        hz = narr["resolucao_hz"]
        self.assertTrue(ativ[int(2.5 * hz):int(3.5 * hz)].all())
        self.assertFalse(ativ[int(6 * hz):int(9 * hz)].any())
        self.assertLess(narr["rms_ativo_db"], -5)


if __name__ == "__main__":
    unittest.main()
