#!/usr/bin/env python3
"""Imprime os capítulos do YouTube a partir da linha do tempo do motor_video (troca de seção = capítulo).

Regras do YouTube: o primeiro em 00:00, pelo menos 3, cada um com 10 s ou mais (capítulos curtos são fundidos ao seguinte).
Mostra o começo da narração de cada um para você escrever os títulos.
Uso:  python3 capitulos_youtube.py SAIDA/04-linha-do-tempo/linha-do-tempo.json
"""
import json, sys

planos = json.load(open(sys.argv[1]))["planos"]
caps, ant = [], None
for p in planos:
    if p["secao"] != ant:
        caps.append([p["inicio"], p["secao"], p.get("narracao", "")]); ant = p["secao"]
caps[0][0] = 0.0
fundidos = []
for i, c in enumerate(caps):
    prox = caps[i + 1][0] if i + 1 < len(caps) else float("inf")
    if prox - c[0] < 10 and i + 1 < len(caps):
        caps[i + 1][0] = c[0]; caps[i + 1][2] = c[2] + " " + caps[i + 1][2]; continue
    fundidos.append(c)
for t, sec, narr in fundidos:
    print(f"{int(t // 60):02d}:{int(t % 60):02d}  [{sec}]  {narr[:90]}")
