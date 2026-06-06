"""
Sistema de Macro com IA para Jogos de Tiro - Ponto de Entrada Principal.

Função:
    Orquestra todos os módulos do sistema em um loop de tempo real:
    1. Captura frame da tela (ou carrega de arquivo em modo teste).
    2. Detecta objetos (inimigos, alvos) no frame.
    3. Calcula a posição ideal da mira.
    4. Executa comandos de mouse para mirar e atirar.
    5. Adiciona delays e variações aleatórias (comportamento humano).

    Pode operar em dois modos:
        - Modo teste (padrão): processa imagens/vídeos sintéticos, sem comandos reais.
        - Modo ao vivo: captura tela real e controla mouse (use com cautela!).

Uso:
    python main.py              # Modo teste (recomendado para iniciar)
    python main.py --live        # Modo ao vivo (cuidado!)
    python main.py --config config.json
    python main.py --video path/to/video.mp4  # Processa vídeo gravado
"""

import os
import sys
import time
import argparse
import logging
from typing import Optional

import cv2
import numpy as np

from config import config, set_test_mode, load_from_json
from screen_capture import ScreenCapturer
from object_detection import ObjectDetector
from aim_calculation import AimCalculator
from command_executor import CommandExecutor
from test_data_generator import TestDataGenerator


# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
def setup_logging(level: str = "INFO") -> None:
    """
    Configura o sistema de logging com formato timestampado.

    Args:
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-18s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Gerenciador principal do sistema
# ---------------------------------------------------------------------------

class MacroSystem:
    """
    Classe principal que orquestra o pipeline completo.

    Gerencia o ciclo de vida: inicialização, loop principal e
    desligamento seguro de todos os módulos.

    Atributos:
        capturer: Capturador de tela (ou None em modo arquivo).
        detector: Detector de objetos.
        calculator: Calculador de mira.
        executor: Executor de comandos.
        running: Flag de controle do loop principal.
        frame_count: Contador de frames processados.
        use_video: Se True, processa vídeo de arquivo.
        video_cap: VideoCapture para vídeo de arquivo.
        save_output: Se True, salva vídeo de saída com anotações.
    """

    def __init__(self, test_mode: bool = True,
                 video_path: Optional[str] = None,
                 save_output: bool = False):
        """
        Inicializa todos os módulos do sistema.

        Args:
            test_mode: Se True, usa dados sintéticos sem comandos reais.
            video_path: Caminho opcional para vídeo gravado.
            save_output: Se True, salva vídeo com anotações.
        """
        setup_logging(config.log_level)
        self.logger = logging.getLogger("MacroSystem")

        set_test_mode(test_mode)
        self.logger.info(f"Inicializando sistema (modo={'teste' if test_mode else 'ao vivo'})")

        # Estado do sistema
        self.running: bool = False
        self.paused: bool = False
        self.frame_count: int = 0
        self.fps_counter: float = 0.0
        self._fps_timer: float = time.perf_counter()
        self.save_output: bool = save_output

        # Inicializa módulos
        if video_path:
            self._init_from_video(video_path)
        elif test_mode:
            self._init_test_mode()
        else:
            self._init_live_mode()

        # Módulos comuns a todos os modos
        self.detector: ObjectDetector = ObjectDetector(method=config.detection.method)
        self.calculator: AimCalculator = AimCalculator()
        self.executor: CommandExecutor = CommandExecutor(enabled=not test_mode)

        # Para salvar vídeo de saída (opcional)
        self._output_writer: Optional[cv2.VideoWriter] = None

        self.logger.info("Sistema inicializado com sucesso.")

    def _init_from_video(self, video_path: str) -> None:
        """
        Prepara o sistema para processar um vídeo gravado.

        Args:
            video_path: Caminho do arquivo de vídeo.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

        self.video_cap = cv2.VideoCapture(video_path)
        self.use_video = True
        self.capturer = None
        self.logger.info(f"Modo vídeo: {video_path}")

    def _init_test_mode(self) -> None:
        """
        Prepara o sistema para modo teste com dados sintéticos.

        Cena gerada ciclicamente para simular um jogo.
        """
        self.gen = TestDataGenerator()
        self.use_video = False
        self.capturer = None
        self.logger.info("Modo teste: dados sintéticos.")

    def _init_live_mode(self) -> None:
        """
        Prepara o sistema para captura de tela em tempo real.

        Inicializa o ScreenCapturer com a região e FPS configurados.
        """
        self.capturer = ScreenCapturer(
            region=config.screen.region,
            target_fps=config.screen.target_fps
        )
        self.use_video = False
        self.logger.info("Modo ao vivo: captura de tela real.")

    # -----------------------------------------------------------------------
    # Loop principal

    # -----------------------------------------------------------------------

    def _update_fps(self) -> None:
        """
        Atualiza o contador de FPS a cada segundo.
        """
        now = time.perf_counter()
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self.fps_counter = self.frame_count / elapsed
            self.frame_count = 0
            self._fps_timer = now

    def _check_exit_key(self) -> bool:
        """
        Verifica teclas de controle mesmo quando pausado.

        Returns:
            True se o usuário solicitou saída.
        """
        key = cv2.waitKey(1) & 0xFF
        return self._handle_key(key)

    def _handle_key(self, key: int) -> bool:
        """
        Processa teclas de controle.

        Teclas:
            ESC ou 'q': Sai do sistema.
            'p': Pausa/continua.
            'r': Reseta o calculador de mira.
            'h': Mostra ajuda no terminal.

        Args:
            key: Código da tecla pressionada.

        Returns:
            True se o sistema deve encerrar.
        """
        if key == 27 or key == ord("q"):  # ESC ou 'q'
            self.logger.info("Tecla de saída pressionada.")
            self.running = False
            return True
        elif key == ord("p"):
            self.paused = not self.paused
            self.logger.info(f"{'Pausado' if self.paused else 'Continuando'}")
        elif key == ord("r"):
            self.calculator.reset()
            self.logger.info("Calculador de mira resetado.")
        elif key == ord("h"):
            self._print_help()
        return False

    @staticmethod
    def _print_help() -> None:
        """
        Exibe ajuda de teclas no terminal.
        """
        print()
        print("  Controles:")
        print("    ESC / q  - Sair")
        print("    p        - Pausar/Continuar")
        print("    r        - Resetar mira")
        print("    h        - Mostrar esta ajuda")
        print()

    def _init_output_writer(self) -> None:
        """
        Inicializa o writer de vídeo para salvar o output anotado.
        """
        output_path = f"macro_output_{int(time.time())}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._output_writer = cv2.VideoWriter(
            output_path, fourcc,
            config.screen.target_fps,
            (config.screen.region[2] if config.screen.region else 1920,
             config.screen.region[3] if config.screen.region else 1080)
        )
        self.logger.info(f"Salvando vídeo de saída: {output_path}")

    # -----------------------------------------------------------------------
    # Loop principal
    # -----------------------------------------------------------------------

    def run(self) -> None:
        self.running = True
        self.logger.info("Iniciando loop principal.")

        try:
            while self.running:
                if self.paused:
                    if self._check_exit_key():
                        break
                    time.sleep(0.01)
                    continue

                self._check_exit_key()
                t_frame = time.perf_counter()

                if self.use_video and self.video_cap:
                    ret, frame = self.video_cap.read()
                    if not ret:
                        self.logger.info("Fim do vídeo.")
                        break
                elif self.capturer:
                    frame = self.capturer.get_frame()
                else:
                    frame = self.gen.generate_scene(num_enemies=3)
                    t = time.time() * 0.5
                    self.gen._draw_simple_enemy(frame,
                        x=int(100 + 200 * np.sin(t)),
                        y=int(150 + 100 * np.cos(t * 0.7)))

                if frame is None:
                    self._sleep(1.0 / config.screen.target_fps)
                    continue

                self.frame_count += 1
                h, w = frame.shape[:2]
                center = (w / 2.0, h / 2.0)

                detections = self.detector.detect(frame)
                aim_point = self.calculator.calculate(detections, center)
                self.executor.aim_and_shoot(aim_point, center)

                annotated = self.detector.draw_detections(frame, detections)
                if aim_point:
                    cv2.circle(annotated, (int(aim_point[0]), int(aim_point[1])),
                               5, (0, 255, 255), -1)
                    cv2.line(annotated, (int(center[0]), int(center[1])),
                             (int(aim_point[0]), int(aim_point[1])),
                             (0, 255, 255), 1)

                if self._output_writer:
                    self._output_writer.write(annotated)

                cv2.imshow("AI Macro", annotated)
                self._update_fps()

                elapsed = time.perf_counter() - t_frame
                sleep_time = (1.0 / config.screen.target_fps) - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Interrompido pelo usuário.")
        finally:
            self.shutdown()

    @staticmethod
    def _sleep(seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    # -----------------------------------------------------------------------
    # Desligamento
    # -----------------------------------------------------------------------

    def shutdown(self) -> None:
        """
        Desliga todos os módulos e libera recursos.

        Chamado automaticamente ao sair do loop principal.
        """
        self.logger.info("Desligando sistema...")
        self.running = False

        if self.capturer:
            self.capturer.release()

        if self.use_video and hasattr(self, "video_cap"):
            self.video_cap.release()

        if self._output_writer:
            self._output_writer.release()

        cv2.destroyAllWindows()
        self.logger.info("Sistema desligado com segurança.")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """
    Analisa argumentos da linha de comando.

    Returns:
        Namespace com os argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Sistema de Macro com IA para Jogos de Tiro",
        epilog="Exemplo: python main.py --test --video test_match.mp4 --save"
    )
    parser.add_argument("--live", action="store_true",
                        help="Modo ao vivo (captura tela real e controla mouse)")
    parser.add_argument("--test", action="store_true", default=True,
                        help="Modo teste com dados sintéticos (padrão)")
    parser.add_argument("--video", type=str, default=None,
                        help="Processar vídeo gravado (.mp4, .avi)")
    parser.add_argument("--config", type=str, default=None,
                        help="Carregar configurações de arquivo JSON")
    parser.add_argument("--save", action="store_true",
                        help="Salvar vídeo de saída com anotações")
    parser.add_argument("--method", type=str, default=None,
                        choices=["template", "color", "yolo"],
                        help="Método de detecção")
    parser.add_argument("--fps", type=int, default=None,
                        help="FPS alvo para captura/processamento")
    parser.add_argument("--log", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Nível de logging")

    return parser.parse_args()


def main() -> None:
    """
    Função principal.

    Interpreta argumentos da linha de comando, carrega configurações
    e inicia o sistema.
    """
    args = parse_args()

    # Carrega configuração de arquivo (se especificado)
    if args.config:
        try:
            load_from_json(args.config)
            print(f"Configuração carregada: {args.config}")
        except Exception as e:
            print(f"Erro ao carregar config: {e}")

    # Sobrescreve configurações por argumentos CLI
    if args.fps:
        config.screen.target_fps = args.fps
    if args.method:
        config.detection.method = args.method
    if args.log:
        config.log_level = args.log

    # Determina modo
    test_mode = not args.live and args.video is None

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   AI MACRO - Shooting System             ║")
    print("  ║   Sistema de Macro com IA para Jogos     ║")
    print("  ╚══════════════════════════════════════════╝")
    print(f"  Modo: {'TESTE' if test_mode else 'AO VIVO'}")
    if args.video:
        print(f"  Vídeo: {args.video}")
    print()

    # Inicializa e executa
    system = MacroSystem(
        test_mode=test_mode,
        video_path=args.video,
        save_output=args.save
    )
    system.run()


if __name__ == "__main__":
    main()
