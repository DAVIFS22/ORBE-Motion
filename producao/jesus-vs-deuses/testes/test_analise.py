import unittest
from pathlib import Path

from motor_video import script_analyzer as sa
from motor_video import subtitle_generator as sg

RAIZ = Path(__file__).resolve().parent.parent
ROTEIRO = RAIZ / "entrada" / "prompt_narracao_e_producao_jesus.txt"
VTT = RAIZ / "entrada" / "lv_0_20261017144122.vtt"


class TestTranscricao(unittest.TestCase):
    def test_vtt_formatos_de_tempo(self):
        cues = sa.parse_transcricao("WEBVTT\n\n00:04.400 --> 00:07.520\nOlá mundo\n\n01:02:03.500 --> 01:02:05.000\nfim\n")
        self.assertEqual(len(cues), 2)
        self.assertAlmostEqual(cues[0].ini, 4.4)
        self.assertAlmostEqual(cues[1].ini, 3723.5)

    def test_srt_com_virgula(self):
        cues = sa.parse_transcricao("1\n00:00:01,250 --> 00:00:03,000\nPrimeira\nlinha\n\n2\n00:00:03,500 --> 00:00:04,000\nSegunda\n")
        self.assertEqual(cues[0].texto, "Primeira linha")
        self.assertAlmostEqual(cues[0].ini, 1.25)

    def test_vazio_e_fora_de_ordem(self):
        with self.assertRaises(sa.ErroRoteiro):
            sa.parse_transcricao("WEBVTT\n\nsem tempos\n")
        with self.assertRaises(sa.ErroRoteiro):
            sa.parse_transcricao("00:10.000 --> 00:11.000\na\n\n00:01.000 --> 00:02.000\nb\n")


class TestRoteiro(unittest.TestCase):
    def test_extrai_so_a_narracao(self):
        txt = sa.extrair_narracao(ROTEIRO.read_text(encoding="utf-8"))
        self.assertTrue(txt.startswith("JESUS CONTRA TODOS OS DEUSES"))
        self.assertNotIn("DIREÇÃO DE PRODUÇÃO", txt)
        self.assertTrue(txt.rstrip().endswith("Quem é Jesus para você?"))

    def test_referencias_biblicas_nao_quebram_a_frase(self):
        _, frases = sa.dividir_frases("João 1:1.\nEm João 8:58, Jesus declara: “Antes que Abraão existisse, eu sou.” Fim.")
        textos = [f.texto for f in frases]
        self.assertEqual(textos[0], "João 1:1.")
        self.assertTrue(any("8:58" in t and "Jesus declara" in t for t in textos))

    def test_normalizar(self):
        self.assertEqual(sa.normalizar("Ressurreição,"), "ressurreicao")
        self.assertEqual(sa.normalizar("“1:1.”"), "11")


class TestAlinhamento(unittest.TestCase):
    TEXTO = "Primeira frase do roteiro aqui. Segunda frase continua depois. Terceira frase termina tudo."

    def test_tempos_e_erros_de_reconhecimento(self):
        cues = sa.parse_transcricao("00:00.000 --> 00:03.000\nPrimeira frase do roteiro aqui\n\n"
                                    "00:03.000 --> 00:06.000\nSegunda frase continua depois\n\n"
                                    "00:06.000 --> 00:09.000\nTerceira frase termina tudo\n")
        al = sa.alinhar(self.TEXTO, cues)
        self.assertAlmostEqual(al.cobertura, 1.0)
        self.assertAlmostEqual(al.tempo_frase(al.frases[1])[0], 3.0, places=1)
        # a transcrição tem erro de grafia: as palavras corretas do roteiro continuam sendo usadas
        cues2 = sa.parse_transcricao("00:00.000 --> 00:03.000\nPrimeira frase do roterio aqui\n")
        al2 = sa.alinhar("Primeira frase do roteiro aqui.", cues2)
        self.assertIn("roteiro", al2.palavras)
        self.assertLess(al2.cobertura, 1.0)

    def test_trecho_nao_narrado_e_reportado(self):
        cues = sa.parse_transcricao("00:00.000 --> 00:03.000\nPrimeira frase do roteiro aqui\n\n00:03.000 --> 00:06.000\nTerceira frase termina tudo\n")
        al = sa.alinhar(self.TEXTO, cues, min_lacuna=3)
        self.assertEqual(len(al.lacunas), 1)
        self.assertTrue(al.lacunas[0]["suspeita_nao_narrado"])
        idx = sa.localizar_ancora(al, "Segunda frase continua")
        t, confiavel = sa.tempo_confiavel(al, idx)
        self.assertFalse(confiavel)
        self.assertAlmostEqual(t, 3.0, places=1)

    def test_ancora_inexistente(self):
        cues = sa.parse_transcricao("00:00.000 --> 00:03.000\nPrimeira frase\n")
        al = sa.alinhar("Primeira frase.", cues)
        with self.assertRaises(sa.ErroRoteiro):
            sa.localizar_ancora(al, "não existe")

    def test_proporcional_cobre_toda_a_duracao(self):
        al = sa.alinhar_proporcional(self.TEXTO, 30.0)
        self.assertAlmostEqual(al.t_fim[-1], 30.0)
        self.assertTrue(all(a <= b for a, b in zip(al.t_ini, al.t_fim)))

    def test_dados_reais_cobertura(self):
        al = sa.alinhar(sa.extrair_narracao(ROTEIRO.read_text(encoding="utf-8")), sa.parse_transcricao(VTT.read_text(encoding="utf-8")))
        self.assertGreater(al.cobertura, 0.95)
        self.assertEqual(len(al.lacunas), 2)
        self.assertTrue(all(l["suspeita_nao_narrado"] for l in al.lacunas))


class TestLegendas(unittest.TestCase):
    def setUp(self):
        self.al = sa.alinhar(sa.extrair_narracao(ROTEIRO.read_text(encoding="utf-8")), sa.parse_transcricao(VTT.read_text(encoding="utf-8")))

    def test_srt_valido_sem_sobreposicao(self):
        leg = sg.gerar(self.al, 1753.65)
        self.assertGreater(len(leg), 350)
        self.assertEqual(sg.validar(leg, 1753.65), [])
        self.assertTrue(all(lg.texto.count("\n") <= 1 for lg in leg))
        self.assertTrue(all(lg.fim - lg.ini <= sg.MAX_DURACAO + 1.0 for lg in leg))

    def test_roundtrip_srt(self):
        import tempfile
        leg = sg.gerar(self.al, 1753.65)
        with tempfile.TemporaryDirectory() as d:
            arq = sg.escrever_srt(leg, Path(d) / "a.srt")
            volta = sg.ler_srt(arq)
        self.assertEqual(len(volta), len(leg))
        self.assertAlmostEqual(volta[10].ini, leg[10].ini, places=2)
        self.assertEqual(volta[10].texto, leg[10].texto)

    def test_texto_do_roteiro_nao_da_transcricao(self):
        leg = sg.gerar(self.al, 1753.65)
        todo = " ".join(l.texto for l in leg)
        self.assertIn("Zeus ou Odin", todo.replace("\n", " "))
        self.assertNotIn("Zeus-Udan", todo)


if __name__ == "__main__":
    unittest.main()
