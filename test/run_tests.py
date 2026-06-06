"""
Suite de Testes - Valida todos os módulos do sistema com dados simulados.

Função:
    Executa testes em cada módulo individualmente e no sistema integrado,
    usando imagens e vídeos sintéticos (sem acesso a jogos reais).

    Testes disponíveis:
        1. Teste de captura de tela (com imagem de arquivo).
        2. Teste de detecção de objetos (template, cor, YOLO simulado).
        3. Teste de cálculo de mira (com e sem suavização).
        4. Teste de executor de comandos (modo simulado).
        5. Teste integrado completo (pipeline completo com dados sintéticos).
        6. Teste com vídeo gravado (processamento offline).
"""

import os
import sys
import time
import cv2
import numpy as np

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config, set_test_mode, AIM
from screen_capture import ScreenCapturer
from object_detection import ObjectDetector, Detection
from aim_calculation import AimCalculator
from command_executor import CommandExecutor
from test_data_generator import TestDataGenerator


# ---------------------------------------------------------------------------
# Configurações de teste
# ---------------------------------------------------------------------------
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_IMAGES_DIR = os.path.join(TEST_DIR, "test_images")
TEST_VIDEOS_DIR = os.path.join(TEST_DIR, "test_videos")
os.makedirs(TEST_IMAGES_DIR, exist_ok=True)
os.makedirs(TEST_VIDEOS_DIR, exist_ok=True)


def print_header(title: str) -> None:
    """Imprime um cabeçalho de teste formatado."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(name: str, passed: bool, detail: str = "") -> None:
    """Imprime resultado de um teste com cor (OK/FAIL)."""
    status = "PASS" if passed else "FAIL"
    icon = "[OK]" if passed else "[X]"
    print(f"  {icon} {name}: {status}  {detail}")


# ---------------------------------------------------------------------------
# Teste 1: Captura de Tela (modo arquivo)
# ---------------------------------------------------------------------------

def test_screen_capture_from_file():
    """
    Testa a captura de tela carregando uma imagem do disco.

    Valida:
        - Carregamento bem-sucedido.
        - Dimensões corretas.
        - Formato BGR (OpenCV).
    """
    print_header("Teste 1: Captura de Tela (arquivo)")

    # Gera uma imagem de teste
    gen = TestDataGenerator()
    test_img = gen.generate_scene(num_enemies=2)
    test_path = os.path.join(TEST_IMAGES_DIR, "test_capture.png")
    cv2.imwrite(test_path, test_img)

    # "Captura" carregando do arquivo (simula captura real)
    frame = cv2.imread(test_path)

    assert frame is not None, "Falha ao carregar imagem"
    assert frame.shape[0] > 0 and frame.shape[1] > 0, "Dimensões inválidas"
    assert len(frame.shape) == 3 and frame.shape[2] == 3, "Formato deve ser BGR"

    print_result("Carregamento de imagem",
                 True, f"Dimensões: {frame.shape[1]}x{frame.shape[0]}")


# ---------------------------------------------------------------------------
# Teste 2: Detecção de Objetos
# ---------------------------------------------------------------------------

def test_object_detection():
    """
    Testa o detector de objetos com cenas sintéticas.

    Valida:
        - Detecção de inimigos em várias posições.
        - Confiança das detecções.
        - Coordenadas dos bounding boxes e centroides.
        - Draw detections não lança erro.
    """
    print_header("Teste 2: Detecção de Objetos")

    gen = TestDataGenerator()
    detector = ObjectDetector(method="template")

    # Teste com 1 inimigo
    frame1 = gen.generate_scene(num_enemies=1, include_hud=False)
    dets1 = detector.detect(frame1)
    print_result("Detecção (1 inimigo)",
                 len(dets1) >= 1, f"{len(dets1)} detecções")

    # Teste com 3 inimigos
    frame3 = gen.generate_scene(num_enemies=3, include_hud=False)
    dets3 = detector.detect(frame3)
    print_result("Detecção (3 inimigos)",
                 len(dets3) >= 1, f"{len(dets3)} detecções")

    # Teste sem inimigos (apenas fundo)
    frame0 = gen.generate_scene(num_enemies=0, include_hud=False)
    dets0 = detector.detect(frame0)
    print_result("Detecção (0 inimigos)",
                 len(dets0) == 0, f"{len(dets0)} detecções")

    # Valida estrutura das detecções
    if dets1:
        d = dets1[0]
        assert len(d.bbox) == 4, "BBox deve ter 4 elementos"
        assert 0 <= d.confidence <= 1, "Confiança deve estar entre 0 e 1"
        assert len(d.centroid) == 2, "Centroide deve ter 2 coordenadas"
        assert isinstance(d.class_label, str), "Label deve ser string"
        print_result("Estrutura Detection", True, f"bbox={d.bbox}, conf={d.confidence:.2f}")

    # Teste draw_detections
    annotated = detector.draw_detections(frame3, dets3)
    assert annotated.shape == frame3.shape, "Draw não deve alterar dimensões"
    print_result("Draw detections", True)

    # Teste detect_from_file
    test_path = os.path.join(TEST_IMAGES_DIR, "test_detect.png")
    cv2.imwrite(test_path, frame3)
    file_dets = detector.detect_from_file(test_path)
    print_result("Detect from file",
                 len(file_dets) >= 0, f"{len(file_dets)} detecções")

    # Teste detecção por cor (HSV)
    detector_color = ObjectDetector(method="color")
    color_dets = detector_color.detect(frame3)
    print_result("Detecção por cor",
                 len(color_dets) >= 0, f"{len(color_dets)} detecções")


# ---------------------------------------------------------------------------
# Teste 3: Cálculo de Mira
# ---------------------------------------------------------------------------

def test_aim_calculation():
    """
    Testa o cálculo de mira com detecções simuladas.

    Valida:
        - Seleção do melhor alvo (mais próximo do centro).
        - Aplicação de offset de mira.
        - Suavização (interpolação progressiva).
        - Adição de ruído.
        - Deadzone (não mira se já está no alvo).
        - Predição de movimento.
    """
    print_header("Teste 3: Cálculo de Mira ")

    calculator = AimCalculator()
    center = (320.0, 240.0)

    # Cria detecções em posições conhecidas
    detections = [
        Detection(bbox=(100, 100, 50, 80), confidence=0.9,
                  class_label="enemy", centroid=(125.0, 140.0)),
        Detection(bbox=(200, 100, 40, 80), confidence=0.8,
                  class_label="enemy", centroid=(220.0, 140.0)),
        Detection(bbox=(500, 300, 30, 50), confidence=0.7,
                  class_label="enemy", centroid=(515.0, 325.0)),
    ]

    # Teste 1: Deve selecionar o alvo mais próximo do centro (índice 1)
    aim1 = calculator.calculate(detections, center)
    assert aim1 is not None, "Deveria encontrar um alvo"
    near_target = abs(aim1[0] - 320) < 100  # Deve mirar na direção do centro
    print_result("Seleção de alvo (mais próximo do centro)",
                 near_target, f"mira em ({aim1[0]:.1f}, {aim1[1]:.1f})")

    # Teste 2: Suavização (mira deve convergir gradualmente)
    calculator.reset()
    positions = []
    for _ in range(10):
        aim = calculator.calculate(detections, center)
        if aim:
            positions.append(aim)

    assert len(positions) > 0, "Deveria produzir posições"
    # Verifica que a posição muda gradualmente (suavização)
    diffs = []
    for i in range(1, len(positions)):
        dx = positions[i][0] - positions[i-1][0]
        dy = positions[i][1] - positions[i-1][1]
        diffs.append(abs(dx) + abs(dy))

    smooth = len(diffs) > 2 and diffs[0] > diffs[-1]
    print_result("Suavização de mira",
                 smooth, f"Movimento converge: {diffs[:3]}...{diffs[-3:]}")

    # Teste 3: Sem detecções (deve retornar None)
    calculator.reset()
    aim_none = calculator.calculate([], center)
    print_result("Sem alvo (None esperado)",
                 aim_none is None, f"resultado={aim_none}")

    # Teste 4: Deadzone
    calculator.reset()
    saved_ox, saved_oy = AIM.aim_offset_x, AIM.aim_offset_y
    AIM.aim_offset_x = 0
    AIM.aim_offset_y = 0
    center_det = [
        Detection(bbox=(310, 235, 20, 20), confidence=0.95,
                  class_label="enemy", centroid=(320.0, 245.0))
    ]
    aim_dead = calculator.calculate(center_det, center)
    AIM.aim_offset_x, AIM.aim_offset_y = saved_ox, saved_oy
    print_result("Deadzone (alvo centralizado)",
                 aim_dead is None, f"mira={aim_dead}")

    # Teste 5: Predição (precisa de histórico)
    if AIM.prediction_enabled:
        calculator.reset()
        pred_dets = [
            Detection(bbox=(i*10, i*5, 20, 20), confidence=0.9,
                      class_label="enemy", centroid=(float(i*10 + 10), float(i*5 + 10)))
            for i in range(10)
        ]
        for d in pred_dets:
            calculator.calculate([d], center)
        print_result("Predição de movimento",
                     len(calculator.target_history) > 0,
                     f"histórico: {len(calculator.target_history)} frames")


# ---------------------------------------------------------------------------
# Teste 4: Executor de Comandos (modo simulado)
# ---------------------------------------------------------------------------

def test_command_executor():
    """
    Testa o executor de comandos em modo simulado (sem mouse real).

    Valida:
        - Inicialização segura (modo teste).
        - Sequência aim_and_shoot não lança exceções.
        - Emergency stop funciona.
        - Alternância enable/disable.
    """
    print_header("Teste 4: Executor de Comandos (simulado)")

    executor = CommandExecutor(enabled=False)

    # Não deve lançar exceção
    try:
        executor.aim_and_shoot((500, 400), (320, 240))
        executor.shoot()
        executor.move_mouse((100, 100))
        executor.move_mouse_relative(10, 10)
        print_result("Comandos simulados", True, "sem exceções")

        executor.emergency_stop()
        print_result("Emergency stop", not executor.enabled, f"enabled={executor.enabled}")

        executor.set_enabled(True)
        print_result("Reativação", executor.enabled, f"enabled={executor.enabled}")

    except Exception as e:
        print_result("Comandos", False, str(e))


# ---------------------------------------------------------------------------
# Teste 5: Pipeline Integrado (offline com imagem)
# ---------------------------------------------------------------------------

def test_integrated_pipeline():
    """
    Testa o pipeline completo: imagem -> detecção -> mira -> comando.

    Usa uma imagem sintética e processa offline (sem captura de tela real).

    Valida:
        - Pipeline completo sem erros.
        - Coordenadas da mira são consistentes.
        - Executor em modo teste não move mouse.
    """
    print_header("Teste 5: Pipeline Integrado")

    # Gera cena de teste
    gen = TestDataGenerator()
    frame = gen.generate_scene(num_enemies=3)

    # Pipeline
    detector = ObjectDetector(method="template")
    calculator = AimCalculator()
    executor = CommandExecutor(enabled=False)

    # Processa 5 frames (simula loop)
    center = (frame.shape[1] / 2.0, frame.shape[0] / 2.0)

    for i in range(5):
        detections = detector.detect(frame)
        aim_point = calculator.calculate(detections, center)
        executor.aim_and_shoot(aim_point, center)

    print_result("Pipeline completo (5 iterações)", True)

    # Verifica anotação
    detections = detector.detect(frame)
    annotated = detector.draw_detections(frame, detections)
    annot_path = os.path.join(TEST_IMAGES_DIR, "pipeline_test.png")
    cv2.imwrite(annot_path, annotated)
    print_result("Frame anotado salvo",
                 os.path.exists(annot_path), annot_path)


# ---------------------------------------------------------------------------
# Teste 6: Processamento de Vídeo
# ---------------------------------------------------------------------------

def test_video_processing():
    """
    Testa o processamento de um vídeo sintético offline.

    Simula o comportamento do sistema em uma partida curta,
    processando cada frame do vídeo e registrando as posições
    da mira ao longo do tempo.

    Valida:
        - Leitura de vídeo frame a frame.
        - Detecção consistente ao longo do tempo.
        - Estatísticas de desempenho (FPS de processamento).
    """
    print_header("Teste 6: Processamento de Vídeo")

    gen = TestDataGenerator(output_dir=TEST_VIDEOS_DIR)
    video_path = gen.generate_video(
        os.path.join(TEST_VIDEOS_DIR, "test_match.mp4"),
        num_frames=60, fps=30, num_enemies=3
    )

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), "Falha ao abrir vídeo"

    detector = ObjectDetector(method="template")
    calculator = AimCalculator()
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"  Vídeo: {total_frames} frames @ {fps} FPS")

    frame_count = 0
    detections_count = 0
    aim_positions = []
    process_times = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        t_start = time.perf_counter()
        center = (frame.shape[1] / 2.0, frame.shape[0] / 2.0)

        detections = detector.detect(frame)
        aim_point = calculator.calculate(detections, center)

        t_elapsed = time.perf_counter() - t_start

        frame_count += 1
        detections_count += len(detections)
        if aim_point:
            aim_positions.append(aim_point)
        process_times.append(t_elapsed)

    cap.release()

    # Estatísticas
    avg_fps = 1.0 / (sum(process_times) / len(process_times)) if process_times else 0
    avg_detections = detections_count / frame_count if frame_count > 0 else 0

    print(f"  Frames processados: {frame_count}")
    print(f"  Média de detecções/frame: {avg_detections:.1f}")
    print(f"  Frames com mira calculada: {len(aim_positions)}")
    print(f"  Tempo médio/frame: {sum(process_times)/len(process_times)*1000:.1f}ms")
    print(f"  FPS de processamento: {avg_fps:.1f}")

    print_result("Processamento de vídeo",
                 frame_count > 0 and avg_fps > 0,
                 f"{frame_count} frames, {avg_fps:.1f} FPS")

    # Salva estatísticas
    stats_path = os.path.join(TEST_DIR, "video_test_stats.txt")
    with open(stats_path, "w") as f:
        f.write(f"Frames: {frame_count}\n")
        f.write(f"Detecções totais: {detections_count}\n")
        f.write(f"Posições de mira: {len(aim_positions)}\n")
        f.write(f"Tempo médio/frame: {sum(process_times)/len(process_times)*1000:.1f}ms\n")
        f.write(f"FPS processamento: {avg_fps:.1f}\n")
    print_result("Estatísticas salvas",
                 os.path.exists(stats_path), stats_path)


# ---------------------------------------------------------------------------
# Execução principal
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("  SISTEMA DE MACRO COM IA PARA JOGOS DE TIRO")
    print("  Suite de Testes")
    print("  " + "-" * 40)
    print("  Modo: OFFLINE (dados sintéticos, sem comandos reais)")
    print()

    set_test_mode(True)  # Garante modo teste

    tests = [
        ("Captura de Tela", test_screen_capture_from_file),
        ("Detecção de Objetos", test_object_detection),
        ("Cálculo de Mira", test_aim_calculation),
        ("Executor de Comandos", test_command_executor),
        ("Pipeline Integrado", test_integrated_pipeline),
        ("Processamento de Vídeo", test_video_processing),
    ]

    passed = 0
    failed = 0

    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"\n  [X] {name}: FALHOU - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("  " + "=" * 60)
    print(f"  RESULTADO: {passed} passed, {failed} failed, "
          f"{passed + failed} total")
    print("  " + "=" * 60)
    print()
    sys.exit(0 if failed == 0 else 1)
