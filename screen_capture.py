"""
Módulo de Captura de Tela - Responsável por obter frames do jogo em tempo real.

Função:
    Fornece uma interface unificada para capturar a tela (ou uma região)
    utilizando diferentes backends: MSS (Multi-Monitor Screenshot) como padrão,
    ou DXCam para maior performance em sistemas Windows com DirectX.

    Inclui um limitador de taxa de quadros (FPS) para controlar a frequência
    de captura e evitar sobrecarga da CPU/GPU.

Uso típico:
    capturer = ScreenCapturer()
    frame = capturer.get_frame()  # numpy array (H, W, 3) em BGR (OpenCV)
"""

import time
from typing import Optional, Tuple
import cv2
import numpy as np
from config import SCREEN


# ---------------------------------------------------------------------------
# Tenta importar MSS (leve e multi-plataforma)
# ---------------------------------------------------------------------------
try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    print("[WARN] MSS não encontrado. Instale com: pip install mss")

# ---------------------------------------------------------------------------
# Tenta importar DXCam (mais rápido, apenas Windows)
# ---------------------------------------------------------------------------
try:
    import dxcam
    HAS_DXCAM = True
except ImportError:
    HAS_DXCAM = False


class ScreenCapturer:
    """
    Captura frames do monitor (ou de uma região específica) e os retorna
    como arrays numpy no formato BGR (padrão OpenCV).

    Atributos:
        region: Região de captura (left, top, width, height) ou None para fullscreen.
        target_interval: Intervalo mínimo entre capturas (1 / target_fps).
        last_capture_time: Timestamp da última captura (para limitar FPS).
        _mss_sct: Instância interna do MSS.
        _dxcam_camera: Instância interna do DXCam.
    """

    def __init__(self, region: Optional[Tuple[int, int, int, int]] = None,
                 target_fps: int = 60):
        """
        Inicializa o capturador com a região e FPS desejados.

        Args:
            region: Tupla (left, top, width, height).
                    None captura o monitor inteiro.
            target_fps: Taxa de quadros alvo.
        """
        self.region: Optional[Tuple[int, int, int, int]] = region or SCREEN.region
        self.target_fps: int = target_fps or SCREEN.target_fps
        self.target_interval: float = 1.0 / self.target_fps
        self.last_capture_time: float = 0.0

        # Backends internos
        self._mss_sct = None
        self._dxcam_camera = None
        self._dxcam_consecutive_failures = 0

        # Inicializa o backend mais apropriado
        self._init_backend()

    def _init_backend(self) -> None:
        """
        Escolhe e inicializa o backend de captura.
        """
        # Limpa backends anteriores
        if self._dxcam_camera:
            try: self._dxcam_camera.release()
            except: pass
            self._dxcam_camera = None
        if self._mss_sct:
            self._mss_sct.close()
            self._mss_sct = None

        # Tenta DXCam primeiro (captura jogos DirectX)
        if HAS_DXCAM:
            try:
                # DXCam permite especificar o monitor no create()
                self._dxcam_camera = dxcam.create(device_idx=SCREEN.monitor_index - 1)
                test_frame = self._dxcam_camera.grab()
                if test_frame is not None:
                    print(f"[SCREEN] DXCam ativo no Monitor {SCREEN.monitor_index} (FPS alvo: {self.target_fps})")
                    return
                else:
                    self._dxcam_camera.release()
                    self._dxcam_camera = None
            except Exception as e:
                print(f"[WARN] DXCam falhou: {e}")
                self._dxcam_camera = None

        if HAS_MSS:
            self._mss_sct = mss.mss()
            monitor_info = self._get_monitor_info()
            print(f"[SCREEN] MSS inicializado no Monitor {SCREEN.monitor_index} - {monitor_info}")
        else:
            raise RuntimeError("Nenhum backend de captura disponível. Instale MSS: pip install mss")


    def _get_monitor_info(self) -> str:
        """
        Retorna uma string descritiva do monitor principal para logging.

        Returns:
            Descrição do monitor (ex: "1920x1080 @ 60Hz").
        """
        if self._mss_sct:
            monitor = self._mss_sct.monitors[1]  # Monitor principal
            w = monitor["width"]
            h = monitor["height"]
            return f"{w}x{h}"
        return "desconhecido"

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Captura um frame da tela/região, respeitando o limite de FPS.

        Se o intervalo mínimo desde a última captura não tiver decorrido,
        retorna None (para que o loop principal possa aguardar).

        Returns:
            numpy.ndarray no formato BGR (H, W, 3) ou None se o FPS
            limitar a captura.
        """
        now = time.perf_counter()
        elapsed = now - self.last_capture_time

        if elapsed < self.target_interval:
            return None  # Ainda não é hora de capturar

        self.last_capture_time = now

        if self._dxcam_camera:
            return self._capture_dxcam()
        elif self._mss_sct:
            return self._capture_mss()
        return None

    def _capture_mss(self) -> Optional[np.ndarray]:
        """
        Captura um frame usando MSS.
        """
        try:
            if self.region:
                left, top, w, h = self.region
                monitor = {"left": left, "top": top, "width": w, "height": h}
            else:
                # Usa o monitor selecionado nas configs
                idx = SCREEN.monitor_index if SCREEN.monitor_index < len(self._mss_sct.monitors) else 1
                monitor = self._mss_sct.monitors[idx]


            screenshot = self._mss_sct.grab(monitor)
            # MSS retorna BGRA -> converte para BGR
            frame = np.array(screenshot, dtype=np.uint8)
            frame = frame[:, :, :3]
            return frame

        except Exception as e:
            print(f"[ERRO] Falha na captura MSS: {e}")
            return None

    def _capture_dxcam(self) -> Optional[np.ndarray]:
        """
        Captura um frame usando DXCam.

        DXCam retorna pixels em RGB ou BGR dependendo da configuração.
        Garantimos a saída em BGR (OpenCV).

        Returns:
            Frame BGR como numpy.ndarray ou None em caso de erro.
        """
        try:
            if self.region:
                left, top, w, h = self.region
                frame = self._dxcam_camera.grab(region=(left, top, left + w, top + h))
            else:
                frame = self._dxcam_camera.grab()

            # Normaliza retornos inesperados do backend (ex.: int em vez de array)
            if frame is None:
                self._dxcam_consecutive_failures += 1
                if self._dxcam_consecutive_failures >= 30:
                    print("[DXCam] Muitas falhas consecutivas, reiniciando backend...")
                    self._init_backend()
                    self._dxcam_consecutive_failures = 0
                return None

            if not isinstance(frame, np.ndarray):
                print(f"[WARN] DXCam retornou tipo inesperado: {type(frame)}")
                self._dxcam_consecutive_failures += 1
                if self._dxcam_consecutive_failures >= 30:
                    print("[DXCam] Resetando backend por retorno inválido...")
                    self._init_backend()
                    self._dxcam_consecutive_failures = 0
                return None

            self._dxcam_consecutive_failures = 0
            # DXCam retorna RGB por padrão; convertemos para BGR
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame
        except Exception as e:
            print(f"[ERRO] Falha na captura DXCam: {e}")
            self._dxcam_consecutive_failures += 1
            if self._dxcam_consecutive_failures >= 30:
                print("[DXCam] Resetando backend apos excecao...")
                self._init_backend()
                self._dxcam_consecutive_failures = 0
            return None

    def get_frame_rate(self) -> float:
        """
        Calcula a taxa de captura real baseada no intervalo configurado.

        Returns:
            FPS real aproximado.
        """
        if self.target_interval > 0:
            return 1.0 / self.target_interval
        return 0.0

    def release(self) -> None:
        """
        Libera recursos dos backends de captura.

        Deve ser chamado ao encerrar o sistema para evitar vazamento
        de recursos (especialmente DXCam que usa GPU).
        """
        if self._dxcam_camera:
            try:
                self._dxcam_camera.release()
                print("[SCREEN] DXCam liberado.")
            except Exception:
                pass
        if self._mss_sct:
            self._mss_sct.close()
            print("[SCREEN] MSS liberado.")

    def __enter__(self):
        """Permite uso com 'with' para gerenciamento automático de recursos."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Libera recursos ao sair do bloco 'with'."""
        self.release()


# ---------------------------------------------------------------------------
# Bloco de teste rápido - executado apenas se o módulo for chamado diretamente
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Teste: captura 10 frames e exibe informações
    capturer = ScreenCapturer(target_fps=30)
    print("Testando captura de tela... Pressione Ctrl+C para interromper.")

    try:
        for i in range(10):
            frame = capturer.get_frame()
            if frame is not None:
                print(f"Frame {i+1}: {frame.shape} - dtype={frame.dtype}")
            else:
                print(f"Frame {i+1}: limite de FPS (aguardando)")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nTeste interrompido.")
    finally:
        capturer.release()
