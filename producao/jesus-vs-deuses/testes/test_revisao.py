"""Testes do ciclo de revisão: escolha de quadros por batida, níveis de áudio, métricas e registro auditável das notas."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from motor_video import revisao as rv
from motor_video.config import ErroProducao


def _tl():
    planos = []
    for i, (a, b) in enumerate([(0.0, 5.0), (5.0, 9.0), (9.0, 21.0)]):
        planos.append({"id": f"c{i}#1", "cena_id": f"c{i}", "inicio": a, "fim": b, "fundo": {"tipo": "motivo", "origem": "motion" if i == 1 else None},
                       "cena3d": None, "transicao_entrada": {"tipo": "corte", "duracao": 0.0}})
    return {"duracao_video_s": 21.0, "fps": 30, "planos": planos, "eventos_audio": [{"t": 6.0, "tipo": "revelar"}, {"t": 12.0, "tipo": "impacto"}, {"t": 14.0, "tipo": "whoosh"}]}


def _grade(bpm=60.0, total=21.0):
    beat = 60 / bpm
    batidas = [{"t": round(i * beat, 4), "secao": 0, "compasso": i // 4 + 1, "tempo": i % 4 + 1, "forte": i % 4 == 0} for i in range(int(total / beat))]
    return {"secoes": [{"indice": 0, "id": "1-abertura", "inicio": 0.0, "fim": total, "bpm": bpm}], "batidas": batidas, "eventos": []}


def _wav24(caminho: Path, x: np.ndarray, sr=48000):
    v = np.clip(x, -1, 1)
    i = (v * ((1 << 23) - 1)).astype(np.int32)
    b = np.stack([i & 0xFF, (i >> 8) & 0xFF, (i >> 16) & 0xFF], axis=1).astype(np.uint8).tobytes()
    cab = b"RIFF" + struct.pack("<I", 36 + len(b)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 3, 3, 24) + b"data" + struct.pack("<I", len(b))
    caminho.write_bytes(cab + b)


class TestAmostras(unittest.TestCase):
    def test_abertura_secoes_planos_e_eventos_sao_cobertos_sem_quase_duplicatas(self):
        am, decisao = rv.escolher_amostras(_tl(), _grade())
        ts = [a["t"] for a in am]
        self.assertTrue(any(abs(t - 0.5) < 0.3 for t in ts) and any(abs(t - 2.0) < 0.3 for t in ts))      # abertura (0–2 s)
        self.assertTrue(all(b - a >= 0.69 for a, b in zip(ts, ts[1:])), ts)
        self.assertTrue(any(a["plano"] == "c2#1" for a in am))                                               # todo plano é visto
        self.assertTrue(any("evento sonoro 'impacto'" in a["motivo"] for a in am) or any(abs(t - 12.12) < 0.8 for t in ts))
        self.assertTrue(any(a["plano"] == "c1#1" and "animação" in a["motivo"] for a in am))                 # motion ganha quadros extras
        self.assertIn("batidas", decisao)
        for a in am:
            self.assertIsNotNone(a["compasso"])
            self.assertLess(abs(a["dt_batida_ms"]), 520)

    def test_limite_corta_a_previa(self):
        am, _ = rv.escolher_amostras(_tl(), _grade(), limite=8.0)
        self.assertTrue(all(a["t"] < 8.0 for a in am))


class TestAudioEMetricas(unittest.TestCase):
    def test_nivel_db_le_wav_24_bits(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d) / "a.wav"
            sr = 48000
            t = np.arange(sr * 4) / sr
            x = np.where(t < 2, 0.1, 0.01) * np.sin(2 * np.pi * 440 * t)
            _wav24(w, x)
            alto, baixo = rv.nivel_db(w, 1.0), rv.nivel_db(w, 3.0)
            self.assertAlmostEqual(alto, 20 * np.log10(0.1 / np.sqrt(2)), delta=0.6)
            self.assertAlmostEqual(alto - baixo, 20.0, delta=0.8)
            self.assertIsNone(rv.nivel_db(Path(d) / "nao-existe.wav", 1.0))

    def test_metricas_variedade_e_sincronia(self):
        tl, g = _tl(), _grade()
        am, _ = rv.escolher_amostras(tl, g)
        m = rv.metricas_objetivas(tl, g, am, [])
        self.assertGreaterEqual(m["variedade_visual"]["mudancas_significativas"], 3)
        self.assertGreater(m["variedade_visual"]["tempo_em_janelas_maiores_que_4s_pct"], 0)     # o plano de 12 s é uma janela estática
        self.assertEqual(m["variedade_visual"]["maiores_janelas_estaticas"][0], {"inicio_s": 9.0, "duracao_s": 12.0})   # plano de 12 s sem evento visual
        self.assertEqual(m["sincronia_cortes_com_grade"]["dentro_de_120ms_pct"], 100.0)           # cortes em 5, 9 s: batidas a 60 BPM


class TestAvaliacao(unittest.TestCase):
    def _dados(self, nota=8):
        return {c: nota for c in rv.CRITERIOS}, {c: "justificativa observada na folha 1" for c in rv.CRITERIOS}

    def test_recusa_nota_sem_evidencia_ou_sem_justificativa(self):
        with tempfile.TemporaryDirectory() as d:
            rod = Path(d)
            (rod / "folha-01.png").write_bytes(b"x")
            notas, just = self._dados()
            with self.assertRaises(ErroProducao):
                rv.registrar_avaliacao(rod, notas, just, [], [])                              # sem evidências
            with self.assertRaises(ErroProducao):
                rv.registrar_avaliacao(rod, notas, just, [], ["folha-99.png"])                # evidência inexistente
            with self.assertRaises(ErroProducao):
                rv.registrar_avaliacao(rod, notas, {**just, "impacto_2s": ""}, [], ["folha-01.png"])
            notas.pop("sincronia_audiovisual")
            with self.assertRaises(ErroProducao):
                rv.registrar_avaliacao(rod, notas, just, [], ["folha-01.png"])

    def test_reprovada_exige_tres_problemas_e_aprovada_exige_todas_as_notas_8(self):
        with tempfile.TemporaryDirectory() as d:
            rod = Path(d) / "rodada-01"
            rod.mkdir()
            (rod / "folha-01.png").write_bytes(b"x")
            notas, just = self._dados(7)
            with self.assertRaises(ErroProducao):
                rv.registrar_avaliacao(rod, notas, just, [{"problema": "a"}], ["folha-01.png"])
            ruim = rv.registrar_avaliacao(rod, notas, just, [{"problema": "a", "correcao": "x"}] * 3, ["folha-01.png"])
            self.assertFalse(ruim["aprovado"])
            notas, just = self._dados(8)
            ok = rv.registrar_avaliacao(rod, notas, just, [], ["folha-01.png"], ["corrigi a luz"])
            self.assertTrue(ok["aprovado"])
            md = rv.resumo_markdown(rod.parent)
            self.assertIn("APROVADA", md)
            self.assertIn("corrigi a luz", md)


if __name__ == "__main__":
    unittest.main()
