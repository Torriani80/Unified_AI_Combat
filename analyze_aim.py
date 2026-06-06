"""
Analisador de Debug - Lê o aim_debug.csv e diagnostica problemas de mira.

Uso:
    python analyze_aim.py

Gera relatório com:
- Estabilidade da detecção (centroid jitter)
- Convergência da mira (offset diminuindo?)
- Oscilação (mudança de direção frequente?)
- Configuração ideal sugerida
"""

import csv
import math
import os
import sys
from pathlib import Path
from collections import defaultdict

def get_csv_path():
    if getattr(sys, 'frozen', False):
        return Path(os.environ.get('APPDATA', Path.home())) / "Unified_AI_Combat" / "aim_debug.csv"
    return Path(__file__).parent / "aim_debug.csv"

def load_data(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append({
                    "frame": int(row["frame"]),
                    "ts": float(row["ts"]),
                    "aiming": int(row["aiming"]),
                    "target_x": float(row["target_x"]),
                    "target_y": float(row["target_y"]),
                    "center_x": float(row["center_x"]),
                    "center_y": float(row["center_y"]),
                    "dist": float(row["dist"]),
                    "raw_dx": float(row["raw_dx"]),
                    "raw_dy": float(row["raw_dy"]),
                    "smooth_dx": float(row["smooth_dx"]),
                    "smooth_dy": float(row["smooth_dy"]),
                    "move_dx": float(row["move_dx"]),
                    "move_dy": float(row["move_dy"]),
                    "state": row["state"],
                    "enemies": int(row["enemies"]),
                    "box_h": float(row.get("box_h", 0)),
                })
            except (ValueError, KeyError):
                continue
    return rows

def analyze(rows):
    if not rows:
        print("Nenhum dado encontrado no CSV.")
        return

    aiming_rows = [r for r in rows if r["aiming"] == 1 and r["state"] in ("LOCKED", "DEADZONE")]
    locked_rows = [r for r in rows if r["state"] == "LOCKED"]

    print(f"=== ANÁLISE DE MIRA ===")
    print(f"Total de frames: {len(rows)}")
    print(f"Frames mirando: {len(aiming_rows)}")
    print(f"Frames LOCKED: {len(locked_rows)}")
    print()

    if not locked_rows:
        print("Nenhum frame LOCKED - mira não está detectando/alvo.")
        return

    # 1. Estabilidade da detecção (centroid jitter)
    avg_jitter = 0
    target_positions = [(r["target_x"], r["target_y"]) for r in locked_rows]
    if len(target_positions) > 1:
        centroid_jitters = []
        for i in range(1, len(target_positions)):
            dx = target_positions[i][0] - target_positions[i-1][0]
            dy = target_positions[i][1] - target_positions[i-1][1]
            centroid_jitters.append(math.hypot(dx, dy))
        avg_jitter = sum(centroid_jitters) / len(centroid_jitters)
        max_jitter = max(centroid_jitters)
        print(f"--- DETECÇÃO ---")
        print(f"Centroid jitter médio: {avg_jitter:.1f} px")
        print(f"Centroid jitter máximo: {max_jitter:.1f} px")
        if avg_jitter > 20:
            print("  ⚠️  DETECÇÃO INSTÁVEL - centroidoscilando muito")
        elif avg_jitter > 10:
            print("  ⚡ Detecção com jitter moderado")
        else:
            print("  ✓ Detecção estável")
        print()

    # 2. Distância do alvo ao centro (convergência)
    distances = [r["dist"] for r in locked_rows]
    avg_dist = sum(distances) / len(distances)
    first_10_dist = sum(distances[:10]) / min(10, len(distances))
    last_10_dist = sum(distances[-10:]) / min(10, len(distances))
    print(f"--- CONVERGÊNCIA ---")
    print(f"Distância média ao centro: {avg_dist:.1f} px")
    print(f"Distância primeiros 10 frames: {first_10_dist:.1f} px")
    print(f"Distância últimos 10 frames: {last_10_dist:.1f} px")
    if last_10_dist < first_10_dist * 0.7:
        print("  ✓ Mirando convergindo (distância diminuindo)")
    elif last_10_dist > first_10_dist * 1.3:
        print("  ⚠️  Mirando DIVERGINDO (distância aumentando!)")
    else:
        print("  ⚡ Mirando estável (sem convergência clara)")
    print()

    # 3. Oscilação (mudança de direção do movimento)
    move_dxs = [r["move_dx"] for r in locked_rows]
    direction_changes = 0
    for i in range(2, len(move_dxs)):
        if (move_dxs[i] > 0.5 and move_dxs[i-1] < -0.5) or \
           (move_dxs[i] < -0.5 and move_dxs[i-1] > 0.5):
            direction_changes += 1
    osc_rate = direction_changes / max(1, len(move_dxs) - 2) * 100

    print(f"--- OSCILAÇÃO ---")
    print(f"Mudanças de direção (X): {direction_changes} ({osc_rate:.1f}%)")
    if osc_rate > 30:
        print("  ⚠️  OSCILAÇÃO ALTA - mira oscilando!")
    elif osc_rate > 15:
        print("  ⚡ Oscilação moderada")
    else:
        print("  ✓ Pouca oscilação")
    print()

    # 4. Movimento médio
    move_mags = [math.hypot(r["move_dx"], r["move_dy"]) for r in locked_rows]
    avg_move = sum(move_mags) / len(move_mags)
    max_move = max(move_mags)
    print(f"--- MOVIMENTO ---")
    print(f"Movimento médio: {avg_move:.1f} px/frame")
    print(f"Movimento máximo: {max_move:.1f} px/frame")
    if avg_move < 1:
        print("  ⚠️  Mira travada (movimento muito pequeno)")
    elif avg_move > 30:
        print("  ⚠️  Movimento agressivo (pode overshoot)")
    else:
        print("  ✓ Movimento dentro do esperado")
    print()

    # 5. Sugestões
    print(f"--- SUGESTÕES ---")
    if avg_jitter > 15:
        print(f"- Aumentar deadzone_radius (atual: 5) para {int(avg_jitter * 0.5)}")
    if osc_rate > 20:
        print(f"- Reduzir aim_gain (atual: 0.4) para {max(0.1, 0.4 - osc_rate/200):.1f}")
    if last_10_dist > first_10_dist and avg_dist > 50:
        print(f"- Aumentar aim_gain (atual: 0.4) para {min(0.8, 0.4 + (last_10_dist - first_10_dist)/200):.1f}")
    if avg_move < 1 and len(locked_rows) > 20:
        print(f"- Reduzir deadzone_radius ou aumentar aim_gain")
    if not any([avg_jitter > 15, osc_rate > 20, last_10_dist > first_10_dist, avg_move < 1]):
        print("  ✓ Configuração atual parece OK")
    print()

    # 6. Log resumido para eu ler
    print(f"=== RESUMO PARA ANÁLISE ===")
    print(f"jitter={avg_jitter:.1f} osc={osc_rate:.1f}% dist_first={first_10_dist:.1f} dist_last={last_10_dist:.1f} move_avg={avg_move:.1f}")


if __name__ == "__main__":
    csv_path = get_csv_path()
    if not csv_path.exists():
        print(f"CSV não encontrado: {csv_path}")
        print("Execute o EXE primeiro com a mira ativa por alguns segundos.")
    else:
        rows = load_data(csv_path)
        analyze(rows)
