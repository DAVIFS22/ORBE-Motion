"""Orquestração do fluxo completo: entrada -> análise -> imagens -> linha do tempo -> áudio -> render -> validação."""

from __future__ import annotations

import json
import shlex
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import VERSAO_MOTOR
from . import asset_manager as am
from . import audio_mixer, image_research, media_ingestion, procedural_art, project_report, quality_checker
from . import script_analyzer as sa
from . import storyboard as sb
from . import subtitle_generator as sg
from . import timeline_builder as tb
from . import video_renderer as vr
from .config import PASTAS, Config, ErroProducao, configurar_log, ffprobe_json, log, salvar_json


class _Etapas:
    def __init__(self):
        self.tempos: dict[str, float] = {}
        self._t = time.monotonic()
        self._nome = ""

    def inicio(self, nome: str):
        self.fim()
        self._nome, self._t = nome, time.monotonic()
        log().info("")
        log().info("== %s ==", nome)

    def fim(self):
        if self._nome:
            self.tempos[self._nome] = time.monotonic() - self._t
            self._nome = ""


def _ler_alinhamento(cfg: Config, entradas, avisos: list[str], duracao_audio: float):
    texto = sa.extrair_narracao(entradas.roteiro.read_text(encoding="utf-8"))
    if entradas.transcricao is None:
        avisos.append("Sem transcrição com tempos: os tempos das cenas foram ESTIMADOS proporcionalmente ao texto. "
                      "A sincronia imagem/fala será aproximada; forneça um VTT/SRT para sincronia real.")
        return sa.alinhar_proporcional(texto, duracao_audio), texto, None
    cues = sa.parse_transcricao(entradas.transcricao.read_text(encoding="utf-8-sig"))
    if cues[-1].fim > duracao_audio + 3.0:
        avisos.append(f"A transcrição termina em {cues[-1].fim:.1f}s, depois do fim da narração ({duracao_audio:.1f}s): "
                      "confira se ela pertence a esta gravação.")
    return sa.alinhar(texto, cues), texto, cues


def _pesquisar_imagens(cfg: Config, planejadas, gerenciador: am.GerenciadorAssets, entradas) -> tuple[dict, str]:
    """Obtém as imagens de cada cena. Devolve ({cena: [Asset]}, descrição do estado da rede)."""
    por_cena: dict[str, list[am.Asset]] = {}
    http = gerenciador.http
    estado_rede = ""
    online = http is not None and not cfg.offline
    if online:
        try:
            http.json("https://commons.wikimedia.org/w/api.php", {"action": "query", "meta": "siteinfo", "format": "json"})
        except (image_research.RedeIndisponivel, image_research.AcessoNegado, ErroProducao) as e:
            online = False
            estado_rede = (f"Sem acesso de rede às fontes de imagem (teste em commons.wikimedia.org falhou: {str(e)[:160]}). "
                           "Nenhuma imagem foi baixada.")
            log().warning(estado_rede)
    elif cfg.offline:
        estado_rede = "Modo offline (--offline): nenhuma imagem foi pesquisada."
    provedores = image_research.criar_provedores(http) if online else []

    locais: dict[str, list[Path]] = {}
    for caminho in entradas.imagens_usuario:
        locais.setdefault(caminho.stem.split("_")[0].split(" ")[0], []).append(caminho)

    total = len(planejadas)
    for i, cp in enumerate(planejadas, 1):
        c = cp.cena
        achadas: list[am.Asset] = []
        for arq in sorted(locais.get(c.id, [])):
            try:
                achadas.append(gerenciador.importar_local(arq, c.id))
            except am.ImagemInvalida as e:
                gerenciador.registrar_falha(c.id, None, f"imagem local {arq.name}: {e}")
        faltam = cp.planos_desejados - len(achadas)
        log().info("[%d/%d] %s: %d plano(s), %d imagem(ns) locais%s", i, total, c.id, cp.planos_desejados, len(achadas),
                   "" if provedores else " (sem pesquisa online)")
        if faltam > 0 and provedores and c.consultas:
            achadas += am.obter_imagens_para_cena(c.id, c.consultas, faltam, gerenciador, provedores,
                                                  permitir_mapa=c.mapa, titulos_commons=c.arquivos or None)
        elif faltam > 0:
            motivo = estado_rede or ("cena sem consultas de imagem" if not c.consultas else "pesquisa desativada")
            gerenciador.registrar_pendencia(c.id, f"{motivo}; faltam {faltam} de {cp.planos_desejados} imagem(ns)",
                                            [q["q"] for q in c.consultas])
        por_cena[c.id] = achadas
    gerenciador.salvar()
    return por_cena, estado_rede


def produzir(cfg: Config, pasta_entrada: Path | None = None, comando: str = "") -> int:
    cfg.saida.mkdir(parents=True, exist_ok=True)
    _, arquivo_log = configurar_log(cfg.saida)
    etapas = _Etapas()
    avisos: list[str] = []
    try:
        log().info("Motor de vídeo %s | saída: %s | log: %s", VERSAO_MOTOR, cfg.saida, arquivo_log)

        etapas.inicio("1/9 Entrada e validação dos arquivos")
        entradas = media_ingestion.ingerir(cfg, pasta_entrada)
        media_ingestion.salvar_manifesto(cfg, entradas)
        duracao_audio = entradas.narracao_original.duracao
        duracao_video = duracao_audio + cfg.cauda_final_s

        etapas.inicio("2/9 Análise do roteiro e alinhamento com a transcrição")
        al, texto, cues = _ler_alinhamento(cfg, entradas, avisos, duracao_audio)
        log().info("%d palavras, %d frases, %.1f%% reconhecidas na transcrição, %d trecho(s) sem correspondência",
                   len(al.palavras), len(al.frases), al.cobertura * 100, len(al.lacunas))
        for lac in al.lacunas:
            log().warning("   sem correspondência em %.1fs: %d palavras: %s", lac["t_ini"], lac["palavras"], lac["texto"])
        pasta_rot = cfg.pasta(PASTAS["roteiro"])
        salvar_json(pasta_rot / "alinhamento.json", {
            "cobertura": al.cobertura, "lacunas": al.lacunas,
            "frases": [{"idx": f.idx, "texto": f.texto, "t_ini": round(al.t_ini[f.palavra_ini], 3),
                        "t_fim": round(al.t_fim[f.palavra_fim - 1], 3)} for f in al.frases]})

        etapas.inicio("3/9 Storyboard e planejamento das cenas")
        cenas, secoes = sb.carregar(cfg.storyboard)
        planejadas = tb.planejar_cenas(al, cenas, duracao_video, cfg.plano_alvo_s, avisos)
        log().info("%d cenas ancoradas no roteiro; %d planos desejados", len(planejadas), sum(c.planos_desejados for c in planejadas))

        etapas.inicio("4/9 Pesquisa e download de imagens")
        http = None if cfg.offline else image_research.ClienteHTTP()
        gerenciador = am.GerenciadorAssets(cfg.pasta(PASTAS["imagens"]), http)
        por_cena, estado_rede = _pesquisar_imagens(cfg, planejadas, gerenciador, entradas)
        n_img = sum(len(v) for v in por_cena.values())
        log().info("%d imagem(ns) válidas em %d cena(s); %d pendência(s)", n_img, sum(1 for v in por_cena.values() if v),
                   len(gerenciador.pendencias))

        etapas.inicio("5/9 Linha do tempo")
        _, pontos = procedural_art.mapa_esquematico()
        tl = tb.construir(al, planejadas, secoes, por_cena, duracao_audio, duracao_video, cfg.fps, cfg.creditos_na_tela, avisos, pontos)
        pasta_tl = cfg.pasta(PASTAS["timeline"])
        salvar_json(pasta_tl / "linha-do-tempo.json", tl.para_dict())
        log().info("%d planos cobrindo 0 – %.2f s", len(tl.planos), tl.duracao_video)

        etapas.inicio("6/9 Legendas")
        legendas = sg.gerar(al, duracao_audio, avisos)
        srt = sg.escrever_srt(legendas, cfg.pasta(PASTAS["legendas"]) / f"{cfg.nome_saida}.srt")
        log().info("%d legendas em %s", len(legendas), srt)
        srt_video = srt
        if cfg.limite_segundos:  # prévia: o MP4 só leva as legendas do trecho renderizado
            previa = [sg.Legenda(lg.ini, min(lg.fim, cfg.limite_segundos), lg.texto) for lg in legendas if lg.ini < cfg.limite_segundos - 0.2]
            srt_video = sg.escrever_srt(previa, cfg.pasta(PASTAS["legendas"]) / f"{cfg.nome_saida}-previa.srt")

        etapas.inicio("7/9 Áudio: trilha, efeitos e mixagem")
        narr = audio_mixer.medir_narracao(entradas.narracao_wav)
        pasta_audio = cfg.pasta(PASTAS["audio"])
        canais = int(ffprobe_json(entradas.narracao_wav)["streams"][0].get("channels", 2))
        dur_mix = min(tl.duracao_video, cfg.limite_segundos) if cfg.limite_segundos else tl.duracao_video
        stems = audio_mixer.construir_stems(tl, narr, pasta_audio, entradas.musicas, entradas.efeitos, cfg.limite_segundos)
        mix = pasta_audio / "mix-final-48k24.wav"
        info_mix = audio_mixer.mixar(entradas.narracao_wav, canais, stems["musica"], stems["efeitos"], dur_mix, narr, mix,
                                     cfg.loudness_alvo)

        etapas.inicio("8/9 Renderização do vídeo")
        pasta_temp = cfg.pasta(PASTAS["temp"])
        sufixo = "-previa" if cfg.limite_segundos else ""
        destino = cfg.pasta(PASTAS["export"]) / f"{cfg.nome_saida}{sufixo}.mp4"
        leg_tuplas = [(lg.ini, lg.fim, lg.texto) for lg in legendas]
        stats = vr.renderizar_video(cfg, tl, cfg.pasta(PASTAS["imagens"]), pasta_temp, srt_video, leg_tuplas, mix, destino)

        etapas.inicio("9/9 Validação do arquivo final")
        originais = media_ingestion.conferir_originais(entradas)
        res = quality_checker.verificar(destino, entradas.narracao_wav, narr, tl, cfg, cfg.pasta(PASTAS["imagens"]), srt_video, originais,
                                        pasta_temp / "procedural")
        etapas.fim()

        assets = [a.__dict__ for a in gerenciador.assets.values() if a.id in {x for p in tl.planos for x in [p.asset_id] if x}]
        ctx = {
            "versao": VERSAO_MOTOR, "gerado_em": datetime.now().isoformat(timespec="seconds"), "validacao": cfg.validacao,
            "cfg": cfg.para_dict(), "entradas": entradas.para_dict() | {"narracao_tratada": entradas.narracao_tratada},
            "alinhamento": {"cobertura": al.cobertura, "palavras": len(al.palavras), "lacunas": al.lacunas},
            "avisos": avisos,
            "timeline": {"cenas": len(planejadas), "planos": len(tl.planos),
                         "planos_com_imagem": sum(1 for p in tl.planos if p.asset_id),
                         "planos_gerados": sum(1 for p in tl.planos if not p.asset_id),
                         "transicoes": dict(Counter(p.transicao_entrada["tipo"] for p in tl.planos))},
            "assets": assets, "pendencias": gerenciador.pendencias, "falhas_download": gerenciador.falhas, "rede": estado_rede,
            "audio": {"narracao_rms_db": narr["rms_ativo_db"], "narracao_pico_db": narr["pico_db"], "fontes": stems["fontes"],
                      "mix_lufs": info_mix["entrada"]["input_i"], "alvo_lufs": info_mix["alvo_lufs"], "true_peak": info_mix["true_peak_max"]},
            "render": stats, "qc": res.para_dict(), "tempos": etapas.tempos, "comando": comando,
            "video": str(destino), "video_mb": destino.stat().st_size / 1e6 if destino.is_file() else 0,
            "duracao_video_s": min(tl.duracao_video, cfg.limite_segundos or tl.duracao_video),
            "srt": str(srt), "n_legendas": len(legendas), "timeline_json": str(pasta_tl / "linha-do-tempo.json"), "log": str(arquivo_log),
        }
        relatorio = project_report.gerar(ctx, cfg.pasta(PASTAS["relatorio"]))
        log().info("")
        log().info("Relatório: %s", relatorio)
        if res.ok:
            if not cfg.manter_temporarios:
                vr.limpar_temporarios(pasta_temp)
            log().info("PRODUÇÃO CONCLUÍDA E VALIDADA: %s", destino)
            return 0
        log().error("O vídeo foi gerado, mas NÃO passou em todas as verificações. Veja o relatório. Temporários mantidos.")
        return 2
    except vr.Cancelado as e:
        log().warning("%s", e)
        return 130
    except KeyboardInterrupt:
        log().warning("Cancelado pelo usuário (Ctrl+C). Os blocos já renderizados serão reaproveitados na próxima execução.")
        return 130
    except ErroProducao as e:
        log().error("ERRO: %s", e)
        return 1
    finally:
        etapas.fim()
