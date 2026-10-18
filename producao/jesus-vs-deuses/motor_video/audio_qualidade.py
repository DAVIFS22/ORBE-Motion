"""Análise objetiva de cada faixa de áudio (narração, música, efeitos, fundo e mixagem final).

Mede, por fluxo (sem carregar tudo na memória): loudness integrado e LRA (EBU R128), pico de amostra e true peak, RMS, clipping,
deslocamento DC, silêncios, equilíbrio espectral por bandas (com atenção aos subgraves), correlação estéreo e estalos. Para a mistura
mede também a **inteligibilidade da voz**: a razão (em dB) entre a narração e o fundo (música + efeitos já com ducking) na banda da fala
(300–3400 Hz), janela a janela, só onde há fala.

Importante: são MEDIÇÕES. Elas não substituem a escuta humana; os relatórios dizem explicitamente quando algo só foi medido.
"""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

import numpy as np

from . import audio_wav
from .config import ErroProducao, log

SR = 48000
BANDAS = (("sub (20–60 Hz)", 20, 60), ("grave (60–250 Hz)", 60, 250), ("médio-grave (250–500 Hz)", 250, 500), ("médio (0,5–2 kHz)", 500, 2000),
          ("presença (2–6 kHz)", 2000, 6000), ("ar (6–20 kHz)", 6000, 20000))
BANDA_VOZ = (300.0, 3400.0)


def _bloco_f32(caminho: Path, segundos: float = 10.0):
    """Gera blocos float32 (N×2, 48 kHz) do arquivo, decodificados pelo FFmpeg em fluxo."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(caminho), "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = int(SR * segundos) * 8
    try:
        while True:
            b = p.stdout.read(n)
            if not b:
                break
            b = b[: len(b) // 8 * 8]
            if b:
                yield np.frombuffer(b, dtype=np.float32).reshape(-1, 2)
    finally:
        p.stdout.close()
        p.wait()


def _ebur128(caminho: Path) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(caminho), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    t = p.stderr
    def g(rx):
        m = re.search(rx, t)
        return float(m.group(1)) if m else None
    return {"lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"), "true_peak_dbtp": g(r"Peak:\s+(-?[\d.]+) dBFS")}


def _db(x: float) -> float:
    return round(20 * math.log10(max(x, 1e-9)), 2)


def analisar_faixa(caminho: Path, nome: str, papel: str, duracao_esperada: float | None = None, junções: list[float] | None = None,
                   limite_silencio_db: float = -60.0, min_silencio_s: float = 2.0, sub_max_db: float = -6.0) -> dict:
    """Análise completa de uma faixa. `junções`: instantes (s) de emendas (início de seções/efeitos) onde se procuram estalos."""
    val = audio_wav.validar_wav(caminho, duracao_esperada, bits=None)
    r = _ebur128(caminho)
    pico = 0.0
    soma2 = 0.0
    n_total = 0
    clip = 0
    dc = np.zeros(2)
    espec = np.zeros(len(BANDAS))
    corr_num = corr_a = corr_b = 0.0
    rms_seg: list[float] = []
    estalos: list[float] = []
    t_bloco = 0.0
    freq = np.fft.rfftfreq(SR, 1 / SR)
    masc = [(freq >= a) & (freq < b) for _, a, b in BANDAS]
    janela = np.hanning(SR)
    for blk in _bloco_f32(caminho):
        n = len(blk)
        pico = max(pico, float(np.abs(blk).max()))
        clip += int((np.abs(blk) >= 0.9995).sum())
        dc += blk.sum(axis=0)
        soma2 += float((blk.astype(np.float64) ** 2).sum())
        n_total += n
        L, R = blk[:, 0].astype(np.float64), blk[:, 1].astype(np.float64)
        corr_num += float((L * R).sum()); corr_a += float((L * L).sum()); corr_b += float((R * R).sum())
        mid = (L + R) / 2
        for i in range(0, n - SR + 1, SR):                                    # RMS por segundo + espectro médio (janelas de 1 s)
            seg = mid[i:i + SR]
            rms_seg.append(float(np.sqrt(np.mean(seg * seg))))
            P = np.abs(np.fft.rfft(seg * janela)) ** 2
            espec += np.array([P[m].sum() for m in masc])
        d2 = np.abs(np.diff(mid, 2))                                          # estalos: saltos isolados na 2ª diferença muito acima do entorno
        if len(d2) > 4096:
            k = 2048
            ref = np.convolve(d2, np.ones(k) / k, mode="same") + 1e-6
            cand = np.nonzero((d2 > np.maximum(0.06, 40 * ref)))[0]
            ult = -10**9
            for c in cand[:200]:
                if c - ult > 480:
                    estalos.append(round(t_bloco + c / SR, 3)); ult = c
        t_bloco += n / SR
    dur = n_total / SR
    tot = espec.sum() + 1e-18
    bandas = {b[0]: round(10 * math.log10(max(e / tot, 1e-12)), 1) for b, e in zip(BANDAS, espec)}
    # silêncios (RMS por segundo abaixo do limite, por pelo menos `min_silencio_s`)
    sil, ini = [], None
    for i, v in enumerate(rms_seg + [1.0]):
        baixo = 20 * math.log10(max(v, 1e-9)) < limite_silencio_db
        if baixo and ini is None:
            ini = i
        if not baixo and ini is not None:
            if i - ini >= min_silencio_s:
                sil.append({"ini_s": ini, "fim_s": i, "dur_s": i - ini})
            ini = None
    corr = corr_num / math.sqrt(corr_a * corr_b + 1e-18)
    sub_db = bandas[BANDAS[0][0]]
    problemas = list(val["problemas"])
    if clip:
        problemas.append(f"{clip} amostra(s) em clipping (|x| ≥ 0,9995)")
    if abs(dc[0] / max(n_total, 1)) > 0.002 or abs(dc[1] / max(n_total, 1)) > 0.002:
        problemas.append("deslocamento DC acima de 0,002")
    if sub_db > sub_max_db and papel in ("musica", "efeitos", "fundo"):
        problemas.append(f"subgraves (20–60 Hz) com {sub_db} dB da energia total (limite {sub_max_db} dB)")
    if r["true_peak_dbtp"] is not None and r["true_peak_dbtp"] > -1.0 and papel == "mix":
        problemas.append(f"true peak {r['true_peak_dbtp']} dBTP acima de -1,0")
    junc = _verificar_junções(caminho, junções or [])
    if junc["suspeitas"]:
        problemas.append(f"{len(junc['suspeitas'])} emenda(s) com salto suspeito (possível estalo)")
    return {"nome": nome, "papel": papel, "arquivo": str(caminho), "formato": val["info"], "duracao_s": round(dur, 3),
            "lufs_integrado": r["lufs"], "lra_lu": r["lra"], "true_peak_dbtp": r["true_peak_dbtp"], "pico_amostra_db": _db(pico), "rms_db": _db(math.sqrt(soma2 / max(1, 2 * n_total))),
            "amostras_em_clipping": clip, "dc_offset": [round(float(v / max(n_total, 1)), 6) for v in dc], "correlacao_estereo": round(corr, 3),
            "bandas_db_rel_total": bandas, "silencios": sil[:20], "estalos_suspeitos_s": estalos[:20], "n_estalos_suspeitos": len(estalos),
            "emendas": junc, "validacao_wav": {"ok": val["ok"], "problemas": val["problemas"]}, "problemas": problemas}


def _verificar_junções(caminho: Path, tempos: list[float], meia_janela: float = 0.05) -> dict:
    """Em cada emenda, compara o maior salto entre amostras vizinhas com o do entorno (±50 ms): salto >> entorno = estalo provável."""
    if not tempos:
        return {"verificadas": 0, "suspeitas": []}
    susp = []
    for t in tempos:
        ini = max(0.0, t - meia_janela)
        p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ini:.4f}", "-t", f"{2 * meia_janela:.4f}", "-i", str(caminho), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                           capture_output=True)
        x = np.frombuffer(p.stdout, np.float32).astype(np.float64)
        if len(x) < 200:
            continue
        d = np.abs(np.diff(x))
        c = int(min(len(d) - 1, (t - ini) * SR))
        lo, hi = max(0, c - 6), min(len(d), c + 6)
        salto = float(d[lo:hi].max())
        entorno = float(np.percentile(np.delete(d, np.arange(lo, hi)), 99)) + 1e-6
        if salto > max(0.02, 8 * entorno):
            susp.append({"t": round(t, 3), "salto": round(salto, 4), "entorno_p99": round(entorno, 4)})
    return {"verificadas": len(tempos), "suspeitas": susp}


def analisar_narracao(wav: Path, duracao_esperada: float | None = None) -> dict:
    """Etapa A: mede a narração original e decide se há algum problema TÉCNICO comprovado (clipping, DC, ruído grave, zumbido).
    Só se corrige o que for comprovado; a interpretação (conteúdo, ordem, duração, dinâmica) nunca é alterada."""
    a = analisar_faixa(wav, "narração original (decodificada)", "narracao", duracao_esperada, min_silencio_s=1.0, limite_silencio_db=-55.0)
    sub = a["bandas_db_rel_total"][BANDAS[0][0]]
    problemas = []
    if a["amostras_em_clipping"] > 0:
        problemas.append("clipping")
    if max(abs(v) for v in a["dc_offset"]) > 0.002:
        problemas.append("DC")
    if sub > -22:
        problemas.append("ruído grave (<60 Hz) elevado")
    a["diagnostico_tecnico"] = {"problemas_comprovados": problemas, "correcao_aplicada": None if not problemas else "passa-altas 40 Hz sugerido",
                                "observacao": "Nenhum problema técnico comprovado: a narração entra na mixagem sem processamento." if not problemas else "Há problema técnico comprovado."}
    return a


def _quadros_banda_voz(blk: np.ndarray, q: int) -> np.ndarray:
    """Energia média por quadro de `q` amostras do sinal mono filtrado na banda da fala (filtro por FFT do bloco inteiro)."""
    mid = (blk[:, 0].astype(np.float64) + blk[:, 1].astype(np.float64)) / 2
    X = np.fft.rfft(mid)
    f = np.fft.rfftfreq(len(mid), 1 / SR)
    X[(f < BANDA_VOZ[0]) | (f > BANDA_VOZ[1])] = 0
    y = np.fft.irfft(X, len(mid))
    n = len(y) // q
    return (y[: n * q].reshape(n, q) ** 2).mean(axis=1) + 1e-18


def inteligibilidade(narracao: Path, fundo: Path, duracao: float, limiar_voz_db: float = -50.0, piso_db: float = 14.0) -> dict:
    """Razão voz/fundo (dB) na banda da fala, em janelas de 1 s com FALA de fato (nível da voz até 10 dB abaixo da mediana das
    janelas com voz; caudas e respirações não contam). Dentro de cada janela só entram os quadros de 50 ms em que a voz soa
    (até 20 dB abaixo do quadro mais forte): o que toca numa pausa não mascara palavra nenhuma.
    `fundo` = música + efeitos já com ducking (sem a voz)."""
    q = SR // 20
    pares, tempos = [], []
    t = 0.0
    for bn, bf in zip(_bloco_f32(narracao, 10.0), _bloco_f32(fundo, 10.0)):
        n = min(len(bn), len(bf))
        en, ef = _quadros_banda_voz(bn[:n], q), _quadros_banda_voz(bf[:n], q)
        for i in range(0, len(en) - 19, 20):
            wn, wf = en[i:i + 20], ef[i:i + 20]
            dbn = 10 * np.log10(wn)
            sel = dbn >= max(limiar_voz_db, float(dbn.max()) - 20.0)
            if sel.sum() < 4:                                     # menos de 200 ms de fala na janela
                continue
            pares.append((10 * math.log10(float(wn[sel].mean())), 10 * math.log10(float(wf[sel].mean()))))
            tempos.append(t + i * q / SR)
        t += n / SR
    if not pares:
        return {"janelas_com_fala": 0, "aprovado": False, "observacao": "nenhuma janela com fala encontrada"}
    vn = np.array([p[0] for p in pares]); vf = np.array([p[1] for p in pares])
    fala = vn >= np.median(vn) - 10.0
    r = (vn - vf)[fala]
    ts = np.array(tempos)[fala]
    ruins = [(round(float(ts[i]), 1), round(float(r[i]), 1)) for i in np.argsort(r)[:8] if r[i] < piso_db]
    return {"janelas_com_fala": int(len(r)), "razao_db": {"p5": round(float(np.percentile(r, 5)), 1), "p25": round(float(np.percentile(r, 25)), 1),
            "mediana": round(float(np.median(r)), 1), "p95": round(float(np.percentile(r, 95)), 1)},
            "janelas_abaixo_do_piso": int((r < piso_db).sum()), "piso_db": piso_db, "piores": ruins,
            "aprovado": bool(np.percentile(r, 5) >= piso_db),
            "criterio": f"p5 da razão voz/fundo (300–3400 Hz, só nos quadros com fala) ≥ {piso_db} dB nas janelas com fala"}


def profundidade_ducking(fundo: Path, fundo_sem_voz_ref: Path | None = None) -> dict:
    """Variação do nível do fundo ao longo do tempo (indica bombeamento): desvio-padrão e nº de oscilações > 3 dB em ≤ 1,5 s."""
    niveis = []
    for blk in _bloco_f32(fundo, 10.0):
        mid = (blk[:, 0].astype(np.float64) + blk[:, 1].astype(np.float64)) / 2
        for i in range(0, len(mid) - SR // 2 + 1, SR // 2):
            seg = mid[i:i + SR // 2]
            niveis.append(20 * math.log10(max(float(np.sqrt(np.mean(seg * seg))), 1e-6)))
    v = np.array(niveis)
    if len(v) < 6:
        return {}
    suave = np.convolve(v, np.ones(3) / 3, mode="same")
    saltos = np.abs(np.diff(suave))
    oscil = int(((saltos[:-2] > 3.0) & (np.abs(suave[2:] - suave[:-2]) < 1.5)).sum())     # sobe e volta em ~1 s: assinatura de bombeamento
    return {"desvio_padrao_db": round(float(v.std()), 2), "oscilacoes_rapidas_acima_de_3db": oscil, "por_minuto": round(oscil / max(1e-9, len(v) * 0.5 / 60), 2)}


def cauda_final(caminho: Path, segundos: float = 16.0) -> dict:
    """Envelope (RMS a cada 0,5 s) dos últimos segundos: confirma decaimento natural, sem corte nem cauda truncada."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-sseof", f"-{segundos}", "-i", str(caminho), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(p.stdout, np.float32).astype(np.float64)
    if len(x) < SR:
        return {}
    passo = SR // 2
    env = [20 * math.log10(max(float(np.sqrt(np.mean(x[i:i + passo] ** 2))), 1e-7)) for i in range(0, len(x) - passo + 1, passo)]
    ultimo = env[-1]
    subidas = sum(1 for a, b in zip(env[-8:], env[-7:]) if b > a + 1.5)
    return {"rms_db_a_cada_0_5s": [round(v, 1) for v in env], "ultimo_meio_segundo_db": round(ultimo, 1),
            "decaimento_natural": bool(ultimo < -55 and subidas == 0), "criterio": "último 0,5 s abaixo de -55 dBFS e sem subidas > 1,5 dB nos 4 s finais"}


def relatorio_audio(pasta: Path, narracao: dict, faixas: list[dict], info_mix: dict, grade: dict | None, mestre: dict | None, cauda: dict | None) -> dict:
    """Relatório de loudness, picos e qualidade por faixa (A narração, B música, C efeitos, D mixagem), em JSON e Markdown."""
    rel = {"narracao": narracao, "faixas": faixas, "mix": {k: info_mix.get(k) for k in ("entrada", "ganho_db", "alvo_lufs", "true_peak_max", "aviso", "final", "inteligibilidade")},
           "grade": [{"secao": s["id"], "bpm": s["bpm"], "medicao": s.get("medicao")} for s in (grade or {}).get("secoes", [])], "cauda_final_musica": cauda}
    if mestre:
        from collections import Counter
        rel["efeitos_por_tipo"] = dict(Counter(e["tipo"] for e in mestre["efeitos"]))
        rel["secoes_musicais"] = [{k: m[k] for k in ("secao", "clima", "ini", "fim", "bpm", "tonalidade_modo", "emocao", "cadencia_final")} for m in mestre["musica"]]
    from .config import salvar_json
    salvar_json(pasta / "relatorio-audio.json", rel)
    L = ["# Relatório de áudio (medições)", "",
         "> Todas as faixas abaixo foram **medidas por código** (EBU R128, picos, espectro, clareza da voz). Nenhuma foi ouvida por uma pessoa nesta "
         "produção: ouça a mixagem com fones antes de publicar.", "",
         "| Faixa | Papel | Duração | LUFS | LRA | True peak | Pico | Clipping | Subgraves | Problemas |", "|---|---|---|---|---|---|---|---|---|---|"]
    for f in [narracao] + faixas:
        sub = f["bandas_db_rel_total"].get(BANDAS[0][0])
        L.append(f"| {f['nome']} | {f['papel']} | {f['duracao_s']:.1f} s | {f['lufs_integrado']} | {f['lra_lu']} | {f['true_peak_dbtp']} dBTP | {f['pico_amostra_db']} dBFS | "
                 f"{f['amostras_em_clipping']} | {sub} dB | {'; '.join(f['problemas']) or '—'} |")
    d = narracao.get("diagnostico_tecnico", {})
    L += ["", f"**Narração (faixa A):** {d.get('observacao', '')} Silêncios ≥ 1 s (abaixo de -55 dBFS): {len(narracao.get('silencios', []))} (pausas do próprio arquivo).", ""]
    clar = info_mix.get("inteligibilidade") or {}
    if clar.get("razao_db"):
        r = clar["razao_db"]
        L += [f"**Clareza da voz (mixagem):** razão voz/fundo na banda 300–3400 Hz, em {clar['janelas_com_fala']} janelas de 1 s com fala: p5 {r['p5']} dB, "
              f"p25 {r['p25']} dB, mediana {r['mediana']} dB ({clar['criterio']}: {'aprovado' if clar['aprovado'] else 'NÃO aprovado'}). "
              f"Ajuste adaptativo do fundo: {clar.get('ajuste_adaptativo_db', 0)} dB.", ""]
    fin = (info_mix.get("final") or {})
    L += [f"**Mixagem final (faixa D):** {fin.get('lufs')} LUFS integrados (alvo {info_mix.get('alvo_lufs')}), true peak {fin.get('true_peak_dbtp')} dBTP "
          f"(teto {info_mix.get('true_peak_max')}), LRA {fin.get('lra')} LU. {info_mix.get('aviso') or ''}", ""]
    if cauda:
        L += [f"**Final da música:** último 0,5 s a {cauda.get('ultimo_meio_segundo_db')} dBFS → {'decaimento natural, sem corte' if cauda.get('decaimento_natural') else 'VERIFICAR: possível corte'}.", ""]
    if rel.get("grade"):
        L += ["**Grade de batidas (beats.json):**", ""]
        for g in rel["grade"]:
            m = g["medicao"] or {}
            L.append(f"- {g['secao']} ({g['bpm']:g} BPM): " + (f"{m.get('cobertura_pulsos', 0) * 100:.0f}% dos {m.get('pulsos_planejados')} pulsos detectados, desvio médio {m.get('desvio_medio_ms')} ms → "
                     f"{'confirmada' if m.get('confirmada') else 'não confirmada'}" if m.get("mensuravel") else "grade planejada (poucos pulsos percussivos para confirmar)"))
        L.append("")
    (pasta / "relatorio-audio.md").write_text("\n".join(L), encoding="utf-8")
    return rel
