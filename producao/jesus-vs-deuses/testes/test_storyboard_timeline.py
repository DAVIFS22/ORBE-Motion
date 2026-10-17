import unittest
from pathlib import Path

from motor_video import script_analyzer as sa
from motor_video import storyboard as sb
from motor_video import timeline_builder as tb
from motor_video.asset_manager import Asset
from motor_video.config import ErroProducao

RAIZ = Path(__file__).resolve().parent.parent
ROTEIRO = RAIZ / "entrada" / "prompt_narracao_e_producao_jesus.txt"
VTT = RAIZ / "entrada" / "lv_0_20261017144122.vtt"


def _al():
    return sa.alinhar(sa.extrair_narracao(ROTEIRO.read_text(encoding="utf-8")), sa.parse_transcricao(VTT.read_text(encoding="utf-8")))


def _asset(i=1, w=1920, h=1080, lic="cc-by"):
    return Asset(id=f"a{i}", arquivo_original=f"o{i}.jpg", arquivo_trabalho=f"t{i}.jpg", fonte="commons", titulo=f"T{i}", autor="Autor",
                 licenca="CC BY 4.0", licenca_categoria=lic, licenca_url="", url_pagina="u", url_arquivo="u", natureza="n", largura=w,
                 altura=h, sha256=f"s{i}", phash="0" * 16)


class TestStoryboard(unittest.TestCase):
    def test_todas_as_ancoras_existem_no_roteiro_em_ordem(self):
        al = _al()
        cenas, _ = sb.carregar()
        pos = 0
        for c in cenas:
            pos = sa.localizar_ancora(al, c.ancora, pos) + 1
        self.assertGreater(len(cenas), 200)

    def test_3d_somente_pontual(self):
        cenas, _ = sb.carregar()
        com3d = [c for c in cenas if c.cena3d]
        p1 = [c for c in com3d if c.cena3d["prioridade"] == 1]
        self.assertLessEqual(len(com3d), 0.1 * len(cenas))       # o 3D é exceção, não regra
        self.assertEqual(len(p1), 6)
        self.assertTrue(all(c.cena3d["modo"] == "sempre" for c in p1))
        self.assertTrue(all(c.cena3d["modo"] == "sem_imagem" for c in com3d if c.cena3d["prioridade"] == 2))

    def test_validacao_rejeita_dados_invalidos(self):
        with self.assertRaises(ErroProducao):
            sb.C("x", "1-abertura", "texto", "d", motivo="inexistente").validar()
        with self.assertRaises(ErroProducao):
            sb.C("x", "1-abertura", "texto", "d", trans="wipe").validar()
        with self.assertRaises(ErroProducao):
            sb.C("x", "1-abertura", "texto", "d", c3d={"cena": "a", "prioridade": 9, "modo": "sempre"}).validar()

    def test_prefixos_de_consulta(self):
        self.assertEqual(sb._consulta("m:Christ")["fontes"], ["met"])
        self.assertEqual(sb._consulta("a:x")["fontes"], ["commons", "met", "aic"])
        self.assertEqual(sb._consulta("Karnak")["fontes"], ["commons"])


class TestTimeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.al = _al()
        cls.cenas, cls.secoes = sb.carregar()
        cls.T = 1753.65 + 2.5

    def _tl(self, assets=None, cfg3d=None, videos=None):
        av = []
        pl = tb.planejar_cenas(self.al, self.cenas, self.T, 11.0, av, cfg3d)
        tl = tb.construir(self.al, pl, self.secoes, assets or {}, 1753.65, self.T, 30, True, av, {}, cfg3d, videos)
        return pl, tl, av

    def test_cobre_toda_a_duracao_sem_lacunas(self):
        _, tl, _ = self._tl()
        self.assertAlmostEqual(tl.planos[0].inicio, 0.0)
        self.assertAlmostEqual(tl.planos[-1].fim, self.T)
        for a, b in zip(tl.planos, tl.planos[1:]):
            self.assertAlmostEqual(a.fim, b.inicio, places=6)
        self.assertGreaterEqual(tl.duracao_video, tl.duracao_audio)

    def test_cenas_curtas_e_zeradas_sao_tratadas_com_aviso(self):
        _, tl, av = self._tl()
        ids = {p.cena_id for p in tl.planos}
        self.assertNotIn("d02-egito-crencas", ids)     # trecho do roteiro sem tempo na transcrição
        self.assertNotIn("c07-curou", ids)             # 1,05 s: incorporada à cena anterior
        self.assertTrue(any("d02-egito-crencas" in a for a in av))

    def test_transicoes_cabem_nos_planos(self):
        _, tl, _ = self._tl()
        for i, p in enumerate(tl.planos[1:], 1):
            t = p.transicao_entrada
            if t["tipo"] != "corte":
                self.assertLessEqual(t["duracao"], 0.35 * min(p.duracao, tl.planos[i - 1].duracao) + 1e-6)

    def test_sem_blender_nao_ha_pedidos_3d(self):
        _, tl, _ = self._tl(cfg3d={"blender_ok": False, "prioridade": 2})
        self.assertEqual(tb.coletar_pedidos_3d(tl), [])

    def test_politica_de_prioridade_e_modo(self):
        _, tl1, _ = self._tl(cfg3d={"blender_ok": True, "prioridade": 1})
        ped1 = tb.coletar_pedidos_3d(tl1)
        self.assertTrue(ped1 and all(p.prioridade == 1 for p in ped1))
        _, tl2, _ = self._tl(cfg3d={"blender_ok": True, "prioridade": 2})
        ped2 = tb.coletar_pedidos_3d(tl2)
        self.assertGreater(len(ped2), len(ped1))
        _, tl0, _ = self._tl(cfg3d={"blender_ok": True, "prioridade": 0})
        self.assertEqual(tb.coletar_pedidos_3d(tl0), [])

    def test_p2_so_quando_nao_ha_imagem_real(self):
        cfg = {"blender_ok": True, "prioridade": 2}
        _, tl, _ = self._tl(assets={"d03-osiris": [_asset(1)]}, cfg3d=cfg)
        ids = [p.plano_id for p in tb.coletar_pedidos_3d(tl)]
        self.assertNotIn("d03-osiris#1", ids)          # há imagem real: o 3D não substitui
        self.assertIn("d04-anubis#1", ids)             # sem imagem: o 3D entra como alternativa

    def test_p1_reserva_o_plano_e_imagens_vao_para_os_seguintes(self):
        cfg = {"blender_ok": True, "prioridade": 1}
        pl, tl, _ = self._tl(assets={"b02-grecia": [_asset(1), _asset(2)]}, cfg3d=cfg)
        cp = next(c for c in pl if c.cena.id == "b02-grecia")
        self.assertTrue(cp.reserva_3d)
        planos = [p for p in tl.planos if p.cena_id == "b02-grecia"]
        self.assertIsNotNone(planos[0].cena3d)
        if len(planos) > 1:
            self.assertEqual(planos[1].asset_id, "a1")

    def test_duracao_do_clipe_inclui_metade_das_transicoes(self):
        _, tl, _ = self._tl(cfg3d={"blender_ok": True, "prioridade": 1})
        for ped in tb.coletar_pedidos_3d(tl):
            pl = next(p for p in tl.planos if p.id == ped.plano_id)
            self.assertGreaterEqual(ped.duracao, pl.duracao)
            self.assertLessEqual(ped.duracao, pl.duracao + 2.5)

    def test_aplicar_clipe_troca_o_fundo_e_rotula(self):
        _, tl, _ = self._tl(cfg3d={"blender_ok": True, "prioridade": 1})
        ped = tb.coletar_pedidos_3d(tl)
        ped[0].status, ped[0].clipe = "renderizado", "/tmp/x.mp4"
        tb.aplicar_clipes_3d(tl, ped, 30)
        pl = next(p for p in tl.planos if p.id == ped[0].plano_id)
        self.assertEqual(pl.fundo["tipo"], "video")
        self.assertTrue(any(o["tipo"] == "rotulo" and "não é registro histórico" in o["texto"] for o in pl.overlays))
        self.assertIn("reconstrução", pl.fonte["natureza"])
        # um pedido que falhou mantém a alternativa visual
        outro = next(p for p in tl.planos if p.cena3d and p.id != pl.id)
        antes = dict(outro.fundo)
        tb.aplicar_clipes_3d(tl, [], 30)
        self.assertEqual(outro.fundo, antes)

    def test_filmagem_so_entra_se_for_mais_longa_que_o_plano(self):
        v_curta = _asset(9)
        v_curta.tipo, v_curta.duracao, v_curta.arquivo_trabalho = "video", 2.0, "originais/v.webm"
        _, tl, _ = self._tl(videos={"a05-natureza": v_curta})
        self.assertNotEqual(next(p for p in tl.planos if p.cena_id == "a05-natureza").fundo["tipo"], "video")
        v_longa = _asset(10)
        v_longa.tipo, v_longa.duracao, v_longa.arquivo_trabalho = "video", 60.0, "originais/v2.webm"
        _, tl, _ = self._tl(videos={"a05-natureza": v_longa})
        self.assertEqual(next(p for p in tl.planos if p.cena_id == "a05-natureza").fundo["tipo"], "video")

    def test_validar_detecta_lacuna(self):
        _, tl, _ = self._tl()
        tl.planos[3].inicio += 0.5
        with self.assertRaises(ErroProducao):
            tb.validar(tl)

    def test_eventos_de_audio_sincronizados_e_variados(self):
        _, tl, _ = self._tl()
        tipos = {e["tipo"] for e in tl.eventos_audio}
        self.assertTrue({"impacto", "whoosh", "nota", "silencio", "pergaminho"} <= tipos)
        # silêncio após a morte (Jo 19) e antes de "Eu sou a ressurreição e a vida"
        silencios = {e["cena"] for e in tl.eventos_audio if e["tipo"] == "silencio"}
        self.assertTrue({"h08-morre", "g11-ressurreicao-vida"} <= silencios)
        # nada de whoosh automático nas seções contidas (morte e crucificação)
        for e in tl.eventos_audio:
            if e["tipo"] == "whoosh" and e.get("auto"):
                self.assertFalse(e["cena"].startswith(("g", "h")))


if __name__ == "__main__":
    unittest.main()
