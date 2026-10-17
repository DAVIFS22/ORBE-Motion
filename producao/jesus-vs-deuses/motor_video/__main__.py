"""Linha de comando: python -m motor_video <comando> [opções]."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from .config import Config, ErroProducao


def _caminho(p: str | None) -> Path | None:
    return Path(p).expanduser().resolve() if p else None


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="motor_video", description="Motor de produção de vídeo cinematográfico por código.")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("produzir", help="Executa o fluxo completo e valida o MP4 final.")
    p.add_argument("--narracao", help="Arquivo da narração (áudio ou vídeo). Se omitido, procura em --entrada.")
    p.add_argument("--roteiro", help="Roteiro (.txt). Se omitido, procura em --entrada.")
    p.add_argument("--transcricao", help="Transcrição com tempos (.vtt ou .srt).")
    p.add_argument("--entrada", help="Pasta para detecção automática de narração/roteiro/transcrição.")
    p.add_argument("--saida", help="Pasta do projeto (padrão: ao lado da narração).")
    p.add_argument("--musica", help="Pasta com músicas licenciadas (arquivos com o nome do clima: misterio, identidade...).")
    p.add_argument("--efeitos", help="Pasta com efeitos licenciados (impacto, whoosh, vento_suave...).")
    p.add_argument("--imagens", help="Pasta com imagens próprias nomeadas com o id da cena (ex.: c05-nazare_1.jpg).")
    p.add_argument("--storyboard", help="Storyboard alternativo em JSON.")
    p.add_argument("--fps", type=int, default=30, choices=[24, 30])
    p.add_argument("--crf", type=int, default=19, help="Qualidade x264 (menor = melhor; padrão 19).")
    p.add_argument("--preset", default="fast", help="Preset do x264 (ultrafast...veryslow; padrão fast).")
    p.add_argument("--encoder", default="auto", choices=["auto", "cpu", "gpu"],
                   help="auto/cpu: libx264 (estável). gpu: tenta NVENC/QSV/AMF/VideoToolbox e volta à CPU se falhar.")
    p.add_argument("--trabalhadores", type=int, help="Processos de renderização em paralelo (padrão: núcleos - 1).")
    p.add_argument("--offline", action="store_true", help="Não pesquisa imagens na internet.")
    p.add_argument("--legendas-queimadas", action="store_true", help="Grava as legendas na imagem (além do SRT).")
    p.add_argument("--sem-creditos-na-tela", action="store_true", help="Não mostra o crédito pequeno das imagens CC BY/BY-SA.")
    p.add_argument("--previa", type=float, metavar="SEGUNDOS", help="Renderiza só os primeiros N segundos.")
    p.add_argument("--loudness", type=float, default=-14.0, help="Loudness alvo do mix em LUFS (padrão -14).")
    p.add_argument("--manter-temporarios", action="store_true")
    p.add_argument("--interativo", action="store_true", help="Pergunta qual arquivo usar quando houver vários.")
    p.add_argument("--rapido", action="store_true", help="Amostragem bilinear (mais rápida, para testes).")
    p.add_argument("--validacao", action="store_true", help="Marca o resultado como validação (narração-guia, não real).")

    g = sub.add_parser("narracao-guia", help="Gera uma narração-guia SINTÉTICA (ruído) a partir do VTT, só para testes.")
    g.add_argument("--transcricao", required=True)
    g.add_argument("--saida", required=True)
    g.add_argument("--duracao", type=float, help="Duração em segundos (padrão: fim da transcrição + 1,5 s).")

    r = sub.add_parser("storyboard", help="Lista as cenas e os tempos resolvidos (sem baixar nem renderizar).")
    r.add_argument("--roteiro", required=True)
    r.add_argument("--transcricao", required=True)
    r.add_argument("--storyboard")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.comando == "narracao-guia":
            from . import narracao_guia
            from . import script_analyzer as sa
            cues = sa.parse_transcricao(Path(args.transcricao).read_text(encoding="utf-8-sig"))
            dur = args.duracao or cues[-1].fim + 1.5
            destino = narracao_guia.gerar(cues, dur, Path(args.saida))
            print(f"Narração-guia sintética (NÃO é narração) gravada em {destino} ({dur:.1f}s)")
            return 0
        if args.comando == "storyboard":
            from . import script_analyzer as sa, storyboard as sb, timeline_builder as tb
            texto = sa.extrair_narracao(Path(args.roteiro).read_text(encoding="utf-8"))
            cues = sa.parse_transcricao(Path(args.transcricao).read_text(encoding="utf-8-sig"))
            al = sa.alinhar(texto, cues)
            cenas, _ = sb.carregar(args.storyboard)
            avisos: list[str] = []
            for cp in tb.planejar_cenas(al, cenas, cues[-1].fim, 11.0, avisos):
                print(f"{cp.inicio:8.2f} – {cp.fim:8.2f}  {cp.cena.id:24s} {cp.planos_desejados} plano(s)  {cp.cena.descricao}")
            for a in avisos:
                print("AVISO:", a)
            return 0
        # produzir
        from . import producao
        narracao = _caminho(args.narracao)
        entrada = _caminho(args.entrada)
        if narracao is None and entrada is None:
            print("Informe --narracao (ou --entrada com uma pasta para detecção automática).", file=sys.stderr)
            return 1
        saida = _caminho(args.saida) or ((narracao.parent if narracao else entrada) / "jesus-contra-todos-os-deuses-producao")
        cfg = Config(
            saida=saida, narracao=narracao, roteiro=_caminho(args.roteiro), transcricao=_caminho(args.transcricao),
            pasta_musica=_caminho(args.musica), pasta_efeitos=_caminho(args.efeitos), pasta_imagens=_caminho(args.imagens),
            storyboard=_caminho(args.storyboard), fps=args.fps, crf=args.crf, preset=args.preset, encoder=args.encoder,
            offline=args.offline, legendas_queimadas=args.legendas_queimadas, limite_segundos=args.previa,
            loudness_alvo=args.loudness, manter_temporarios=args.manter_temporarios, creditos_na_tela=not args.sem_creditos_na_tela,
            interativo=args.interativo, rapido=args.rapido, validacao=args.validacao,
        )
        if args.trabalhadores:
            cfg.trabalhadores = max(1, args.trabalhadores)
        comando = "python -m motor_video " + " ".join(shlex.quote(a) for a in (argv if argv is not None else sys.argv[1:]))
        return producao.produzir(cfg, entrada, comando)
    except ErroProducao as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
