"""Testes da evolução visual e sonora: tipografia cinética sincronizada, ritmo de montagem, stills 3D e ajustes de áudio."""
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from motor_video import audio_webaudio as aw
from motor_video import fundos3d
from motor_video import motion_bridge as mb
from motor_video import motion_conteudo as mc
from motor_video import script_analyzer as sa
from motor_video import storyboard as sb
from motor_video import timeline_builder as tb
from motor_video.storyboard import C, Secao
from motor_video.timeline_builder import Plano, Timeline


def _al(pares):
    """Alinhamento sintético: [(palavra, t_ini), ...]."""
    pal = [p for p, _ in pares]
    ts = [t for _, t in pares]
    return sa.Alinhamento(palavras=pal, normalizadas=[sa.normalizar(p) for p in pal], t_ini=ts, t_fim=[t + 0.3 for t in ts],
                          reconhecida=[True] * len(pal), frases=[], duracao_transcricao=ts[-1] + 1)


class TestFraseSincronizada(unittest.TestCase):
    def test_palavras_no_instante_dito_e_enfase(self):
        al = _al([("no", 10.0), ("princípio", 10.4), ("era", 10.9), ("o", 11.1), ("verbo", 11.3)])
        plano = SimpleNamespace(inicio=10.0, fim=14.0, duracao=4.0)
        linhas, achadas = mb.linhas_da_frase("No princípio | era o *Verbo*", plano, al)
        self.assertEqual(achadas, 5)
        self.assertEqual([[w["t"] for w in l] for l in linhas], [[0.0, 0.4], [0.9, 1.1, 1.3]])
        self.assertTrue(linhas[1][2]["enfase"])
        self.assertNotIn("enfase", linhas[0][0])

    def test_palavra_curta_nao_casa_com_ocorrencia_distante(self):
        # "o" aparece cedo no plano, mas a frase só começa 5 s depois: a palavra curta é posicionada junto da seguinte
        al = _al([("o", 10.2), ("mundo", 10.5), ("antigo", 11.0), ("o", 15.2), ("único", 15.5), ("deus", 15.9)])
        plano = SimpleNamespace(inicio=10.0, fim=18.0, duracao=8.0)
        linhas, _ = mb.linhas_da_frase("o único Deus", plano, al)
        ts = [w["t"] for w in linhas[0]]
        self.assertAlmostEqual(ts[0], 5.2, places=3)
        self.assertEqual(ts[1:], [5.5, 5.9])

    def test_palavra_de_conteudo_distante_ainda_e_sincronizada(self):
        al = _al([("se", 10.0), ("humilhou", 10.5), ("e", 11.0), ("foi", 11.4), ("obediente", 11.8), ("exaltado", 15.3)])
        plano = SimpleNamespace(inicio=10.0, fim=17.0, duracao=7.0)
        linhas, achadas = mb.linhas_da_frase("se humilhou | e foi *exaltado*", plano, al)
        self.assertEqual(achadas, 5)
        self.assertAlmostEqual(linhas[1][2]["t"], 5.3, places=3)

    def test_conteudos_de_frase_usam_poucas_palavras(self):
        for k, v in mc.CONTEUDO.items():
            if v["comp"] == "frase":
                self.assertLessEqual(len(v["params"]["texto"].replace("|", " ").split()), 9, k)
                self.assertTrue(v.get("fundo_do_plano"), k)


def _cena(id, secao="3-identidade", ancora="", **kw):
    return C(id, secao, ancora, "descrição", (), kw.pop("motivo", "luz_dourada"), kw.pop("cam", ("zoom_in",)), "neutro", kw.pop("ritmo", "normal"), **kw)


class TestRitmoDeMontagem(unittest.TestCase):
    def _construir(self, cenas, dur, al, cfgmo=None):
        secoes = {s: Secao(s, "identidade", ["vento_suave"]) for s in ("1-abertura", "3-identidade", "4-amor")}
        pl = tb.planejar_cenas(al, cenas, dur, 11.0, [], {"blender_ok": False, "prioridade": 0}, cfgmo)
        return tb.construir(al, pl, secoes, {}, dur, dur, 30, True, [], None, {"blender_ok": False, "prioridade": 0}, {}, cfgmo)

    def test_planos_curtos_cortes_secos_e_reenquadramento(self):
        pal = [(f"w{i}", i * 0.5) for i in range(40)]
        al = _al(pal)
        cenas = [_cena("a", ancora="w0"), _cena("b", ancora="w20")]
        tl = self._construir(cenas, 20.0, al)
        self.assertGreaterEqual(len(tl.planos), 4)                                     # 10 s por cena -> ~2 planos de 5 s cada
        dentro = [p for p in tl.planos if p.cena_id == "a"]
        self.assertTrue(all(p.transicao_entrada["tipo"] == "corte" for p in dentro[1:]))
        self.assertEqual(dentro[1].camera["preset"], "fechado")                         # o 2º plano reenquadra o mesmo cenário
        self.assertEqual(dentro[0].fundo, dentro[1].fundo)
        self.assertEqual(tl.planos[len(dentro)].transicao_entrada["tipo"], "corte")    # mesma seção, ritmo normal: corte na fala

    def test_mudanca_de_secao_usa_fusao(self):
        al = _al([(f"w{i}", i * 0.5) for i in range(40)])
        tl = self._construir([_cena("a", ancora="w0"), _cena("b", secao="4-amor", ancora="w20")], 20.0, al)
        p = next(p for p in tl.planos if p.cena_id == "b")
        self.assertEqual(p.transicao_entrada["tipo"], "dissolve")

    def test_preset_nao_repete_o_anterior(self):
        hist = ["zoom_in", "fechado", "zoom_in"]
        self.assertNotEqual(tb._escolher_preset(("zoom_in",), 0, hist, None), "zoom_in")


class TestStills3D(unittest.TestCase):
    def test_escolha_gira_entre_variacoes_e_so_na_parte_de_jesus(self):
        cont = {}
        a = [fundos3d.escolher("5-morte", "luz_dourada", cont) for _ in range(6)]
        self.assertEqual(len(set(a)), 6)                                               # seis planos, seis quadros diferentes
        self.assertTrue(all(x in fundos3d.STILLS for x in a))
        self.assertIsNone(fundos3d.escolher("1-abertura", "ceu_estrelado", cont))       # a abertura mantém o cenário próprio
        self.assertIsNone(fundos3d.escolher("5-morte", "mapa_inexistente", cont))

    def test_todo_still_e_rotulado_como_reconstrucao(self):
        for sid, s in fundos3d.STILLS.items():
            self.assertRegex(s.descricao.lower(), r"art[ií]stic", sid)
            self.assertTrue(0 < s.f <= 1, sid)

    def test_sem_motor_volta_ao_cenario_original(self):
        alt = {"tipo": "motivo", "motivo": "luz_dourada", "semente": 3}
        p = Plano(id="x#1", cena_id="x", secao="5-morte", inicio=0, fim=4, narracao="", descricao="", fundo={"tipo": "still3d", "still": "tumulo_saida_0", "alternativa": alt},
                  camera={"preset": "deriva"}, cor="neutro", transicao_entrada={"tipo": "corte", "duracao": 0}, overlays=[], fonte={})
        tl = Timeline(4, 4, 30, [p], [], [])
        info = fundos3d.aplicar(tl, None, Path("/nao/usado"), Path("/nao/usado"))
        self.assertEqual(p.fundo, alt)
        self.assertIn("aviso", info)


class TestAudioAcomodacao(unittest.TestCase):
    def test_efeito_leve_vai_para_a_pausa_ou_e_atenuado(self):
        hz = 20.0
        ativo = np.zeros(400, bool)
        ativo[0:100] = True; ativo[120:400] = True                                       # pausa de 1 s em 5,0–6,0 s
        narr = {"atividade": ativo, "resolucao_hz": hz}
        ev = [{"t": 5.5, "tipo": "whoosh", "dur": 1.0}, {"t": 12.0, "tipo": "whoosh", "dur": 1.0}, {"t": 12.0, "tipo": "impacto", "dur": 3.2}]
        aw._acomodar_a_fala(ev, narr)
        self.assertLess(ev[0]["t"], 5.5)                                                  # deslocado para dentro da pausa
        self.assertGreaterEqual(ev[0]["t"], 5.5 - 0.35)
        self.assertIn("deslocado", ev[0]["ajuste"])
        self.assertEqual(ev[1]["ganhoDb"], -6.0)                                          # sem pausa por perto: atenuado
        self.assertNotIn("ajuste", ev[2])                                                 # impacto (momento narrativo) não é mexido


if __name__ == "__main__":
    unittest.main()
