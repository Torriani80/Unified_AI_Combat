"""
Aplicativo Windows - Interface Gráfica do Sistema de Macro com IA para Jogos de Tiro.

Funcionalidades:
    - Preview de vídeo em tempo real com bounding boxes e mira.
    - Painel de controle completo (modo, método, parâmetros).
    - Sliders e controles para ajuste fino de todos os parâmetros.
    - Botões Start/Stop/Pause.
    - Estatísticas ao vivo (FPS, detecções, tempo de execução).
    - Área de log para monitoramento.
    - Menu para carregar vídeos, configurar modo e acessar ajuda.

Uso:
    python app_main.py
"""

import os
import sys
import time
import json
import math
import random
import queue
import threading
import logging
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from dataclasses import asdict

# Garante que o diretório raiz está no path, mesmo executando de fora da pasta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

import cv2
import numpy as np

from config import config, set_test_mode, load_from_json, save_to_json
from config import SCREEN, DETECTION, AIM, RANDOM, CMD
from object_detection import ObjectDetector, Detection
from aim_calculation import AimCalculator
from command_executor import CommandExecutor
from test_data_generator import TestDataGenerator


# ---------------------------------------------------------------------------
# Configuração de logging (redirecionado para a interface)
# ---------------------------------------------------------------------------

class QueueHandler(logging.Handler):
    """Handler de logging que envia mensagens para uma fila (lida pela GUI)."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


def setup_logging_gui(log_queue: queue.Queue) -> None:
    handler = QueueHandler(log_queue)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(name)-18s | %(message)s", datefmt="%H:%M:%S"
    ))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# Worker Thread - Executa o pipeline em background
# ---------------------------------------------------------------------------

class PipelineWorker(threading.Thread):
    """
    Thread separada que executa o pipeline de captura, detecção, mira e comando.

    Comunica-se com a GUI através de filas:
        - frame_queue: frames anotados para preview.
        - status_queue: dicionários com estatísticas (FPS, detecções, etc.).
        - log_queue: mensagens de log.

    Sinais de controle via eventos threading:
        - stop_event: sinaliza parada.
        - pause_event: sinaliza pausa.
    """

    def __init__(self, frame_queue: queue.Queue, status_queue: queue.Queue,
                 log_queue: queue.Queue):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.status_queue = status_queue
        self.log_queue = log_queue

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Começa "rodando" (não pausado)

        # Parâmetros compartilhados (lidos pela thread, alterados pela GUI)
        self.lock = threading.Lock()
        self.params = {
            "mode": "test",
            "video_path": None,
            "method": "template",
            "target_fps": 30,
            "smoothing": 0.35,
            "deadzone": 5,
            "noise_px": 3.0,
            "miss_chance": 0.05,
            "trigger_enabled": True,
            "aim_offset_y": -10,
            "delay_min": 0.05,
            "delay_max": 0.15,
            "reaction_min": 0.1,
            "reaction_max": 0.3,
            "debug_view": False,
        }

        # Módulos do pipeline (inicializados na thread)
        self.detector: Optional[ObjectDetector] = None
        self.calculator: Optional[AimCalculator] = None
        self.executor: Optional[CommandExecutor] = None
        self.gen: Optional[TestDataGenerator] = None
        self.video_cap: Optional[cv2.VideoCapture] = None

        self.logger = logging.getLogger("Pipeline")

    def update_params(self, **kwargs):
        """Atualiza parâmetros de forma thread-safe."""
        with self.lock:
            self.params.update(kwargs)

    def run(self):
        """Loop principal do pipeline (executado na thread)."""
        self.logger.info("Pipeline iniciado.")
        self._init_modules()

        frame_count = 0
        fps_timer = time.perf_counter()
        fps_display = 0.0
        total_detections = 0

        while not self.stop_event.is_set():
            # Pausa
            self.pause_event.wait()

            with self.lock:
                params = dict(self.params)

            # Limita FPS
            target_interval = 1.0 / max(params["target_fps"], 1)
            t_start = time.perf_counter()

            # Obtém frame
            frame = self._get_frame(params)
            if frame is None:
                if params["mode"] == "video":
                    self.logger.info("Fim do vídeo. Repetindo...")
                    self._restart_video(params)
                    continue
                # Em modo teste, gera um novo frame
                frame = self._generate_test_frame(params)
                if frame is None:
                    time.sleep(0.01)
                    continue

            frame_count += 1
            h, w = frame.shape[:2]
            center = (w / 2.0, h / 2.0)

            # Atualiza módulos com parâmetros em tempo real
            self._apply_params(params)

            # Detecta objetos
            detections = self.detector.detect(frame) if self.detector else []
            total_detections += len(detections)

            # Calcula mira
            aim_point = self.calculator.calculate(detections, center) if self.calculator else None

            # Executa comando (thread-safe)
            if self.executor:
                self.executor.aim_and_shoot(aim_point, center)

            # Anota o frame para preview
            debug_view = params.get("debug_view", False)

            if debug_view and self.detector:
                preview = self.detector.get_debug_frame(frame)
            else:
                annotated = frame.copy()
                if self.detector:
                    annotated = self.detector.draw_detections(annotated, detections)
                if aim_point:
                    cv2.circle(annotated, (int(aim_point[0]), int(aim_point[1])),
                               5, (0, 255, 255), -1)
                    cv2.line(annotated,
                             (int(center[0]), int(center[1])),
                             (int(aim_point[0]), int(aim_point[1])),
                             (0, 255, 255), 1)
                preview = self._resize_frame(annotated, 640)

            # Envia frame para GUI
            self.frame_queue.put(preview)

            # Atualiza FPS
            now = time.perf_counter()
            if now - fps_timer >= 1.0:
                fps_display = frame_count / (now - fps_timer)
                frame_count = 0
                fps_timer = now

            # Envia status
            status = {
                "fps": fps_display,
                "detections": len(detections),
                "total_detections": total_detections,
                "aim": aim_point,
                "mode": params["mode"],
                "frame_size": (w, h),
            }
            self.status_queue.put(status)

            # Respeita o FPS alvo
            elapsed = time.perf_counter() - t_start
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._cleanup()
        self.logger.info("Pipeline encerrado.")

    def _init_modules(self):
        """Inicializa os módulos do pipeline."""
        with self.lock:
            method = self.params.get("method", "template")
        self.detector = ObjectDetector(method=method)
        self.calculator = AimCalculator()
        self.executor = CommandExecutor(enabled=False)
        self.gen = TestDataGenerator(width=640, height=480)
        self.logger.info(f"Módulos inicializados (método: {method}).")

    def _apply_params(self, params: dict):
        """Aplica parâmetros alterados pela GUI nos módulos."""
        if self.calculator:
            self.calculator.smoothing_factor = params["smoothing"]
        AIM.deadzone_radius = params["deadzone"]
        RANDOM.position_noise_px = params["noise_px"]
        RANDOM.miss_chance = params["miss_chance"]
        AIM.aim_offset_y = params["aim_offset_y"]
        RANDOM.mouse_delay_min = params["delay_min"]
        RANDOM.mouse_delay_max = params["delay_max"]
        RANDOM.reaction_time_min = params["reaction_min"]
        RANDOM.reaction_time_max = params["reaction_max"]
        CMD.trigger_enabled = params["trigger_enabled"]

        if self.executor:
            self.executor.enabled = (params["mode"] == "live")

    def _get_frame(self, params: dict) -> Optional[np.ndarray]:
        """Obtém frame da fonte ativa."""
        mode = params["mode"]

        if mode == "video" and self.video_cap:
            ret, frame = self.video_cap.read()
            if ret:
                return frame
            return None

        if mode == "live":
            return self._capture_live()

        return None  # Modo teste gera na chamada separada

    def _capture_live(self) -> Optional[np.ndarray]:
        """Captura tela ao vivo usando DXCam (prioridade) ou MSS."""
        # Tenta DXCam (melhor para jogos DirectX)
        try:
            import dxcam
            if not hasattr(self, '_dx_camera') or self._dx_camera is None:
                self._dx_camera = dxcam.create()
            frame = self._dx_camera.grab()
            if frame is not None:
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as e:
            pass

        # Fallback: MSS (funciona em qualquer tela)
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                return np.array(img)[:, :, :3]
        except Exception as e:
            self.logger.warning(f"Captura ao vivo falhou: {e}")
            return None

    def _generate_test_frame(self, params: dict) -> np.ndarray:
        """Gera um frame sintético para modo teste."""
        if not self.gen:
            self.gen = TestDataGenerator(width=640, height=480)
        t = time.time() * 0.5
        frame = self.gen.generate_scene(num_enemies=3)
        # Inimigo com movimento senoidal
        self.gen._draw_simple_enemy(
            frame,
            x=int(100 + 200 * np.sin(t)),
            y=int(150 + 100 * np.cos(t * 0.7)),
            color=(0, 0, 200)
        )
        return frame

    def _restart_video(self, params: dict):
        """Reinicia o vídeo do início."""
        if self.video_cap:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _resize_frame(self, frame: np.ndarray, max_width: int) -> np.ndarray:
        """Redimensiona frame mantendo aspect ratio."""
        h, w = frame.shape[:2]
        if w > max_width:
            ratio = max_width / w
            new_w = max_width
            new_h = int(h * ratio)
            return cv2.resize(frame, (new_w, new_h))
        return frame

    def start_video(self, path: str):
        """Abre um arquivo de vídeo."""
        if self.video_cap:
            self.video_cap.release()
        self.video_cap = cv2.VideoCapture(path)
        self.logger.info(f"Vídeo carregado: {path}")
        self.update_params(mode="video", video_path=path)

    def stop(self):
        """Sinaliza parada da thread."""
        self.stop_event.set()
        self.pause_event.set()

    def pause(self):
        """Alterna pausa."""
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.logger.info("Pipeline pausado.")
        else:
            self.pause_event.set()
            self.logger.info("Pipeline continuando.")

    def _cleanup(self):
        """Libera recursos."""
        if self.video_cap:
            self.video_cap.release()
        if hasattr(self, '_dx_camera') and self._dx_camera is not None:
            try:
                self._dx_camera.release()
            except:
                pass
            self._dx_camera = None
        if hasattr(self, 'detector') and self.detector:
            pass


# ---------------------------------------------------------------------------
# Aplicação Principal (tkinter)
# ---------------------------------------------------------------------------

class MacroApp:
    """
    Janela principal do aplicativo.

    Layout:
        - Menu superior (File, Mode, Help)
        - Frame principal dividido:
            - Esquerda: Preview de vídeo (Canvas).
            - Direita: Painel de controle com abas.
        - Frame inferior: Área de log.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Macro - Shooting System")
        self.root.geometry("1200x720")
        self.root.minsize(960, 600)

        # Tenta definir ícone (se existir)
        try:
            self.root.iconbitmap(default=os.path.join(
                os.path.dirname(__file__), "app", "icon.ico"))
        except Exception:
            pass

        # Filas de comunicação com a pipeline
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self.status_queue: queue.Queue = queue.Queue(maxsize=10)
        self.log_queue: queue.Queue = queue.Queue(maxsize=100)

        # Configura logging para a GUI
        setup_logging_gui(self.log_queue)
        self.logger = logging.getLogger("App")

        # Worker thread
        self.worker: Optional[PipelineWorker] = None

        # Estado
        self.running = False
        self.current_image: Optional[ImageTk.PhotoImage] = None

        # Constrói interface
        self._build_menu()
        self._build_layout()
        self._build_controls()
        self._build_status_bar()

        # Inicia verificação periódica das filas
        self._poll_queues()

        self.logger.info("Aplicativo iniciado. Configure e clique em Start.")

    # -----------------------------------------------------------------------
    # Menu
    # -----------------------------------------------------------------------

    def _build_menu(self):
        """Constrói a barra de menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Abrir Vídeo...", command=self._open_video,
                              accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Carregar Config...", command=self._load_config)
        file_menu.add_command(label="Salvar Config...", command=self._save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self._quit, accelerator="Ctrl+Q")

        # Mode
        mode_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Mode", menu=mode_menu)
        self._mode_var = tk.StringVar(value="test")
        mode_menu.add_radiobutton(label="Teste (dados sintéticos)",
                                  variable=self._mode_var, value="test",
                                  command=lambda: self._set_mode("test"))
        mode_menu.add_radiobutton(label="Ao Vivo (captura tela real)",
                                  variable=self._mode_var, value="live",
                                  command=lambda: self._set_mode("live"))
        mode_menu.add_radiobutton(label="Vídeo Gravado",
                                  variable=self._mode_var, value="video",
                                  command=lambda: self._set_mode("video"))
        mode_menu.add_separator()
        mode_menu.add_command(label="Parar Emergência", command=self._emergency_stop,
                              accelerator="F4")

        # Help
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Sobre", command=self._show_about)
        help_menu.add_command(label="Atalhos", command=self._show_shortcuts)

        # Atalhos de teclado
        self.root.bind("<Control-o>", lambda e: self._open_video())
        self.root.bind("<Control-q>", lambda e: self._quit())
        self.root.bind("<F4>", lambda e: self._emergency_stop())
        self.root.bind("<space>", lambda e: self._toggle_start_stop())

    # -----------------------------------------------------------------------
    # Layout principal
    # -----------------------------------------------------------------------

    def _build_layout(self):
        """Constrói o layout principal com panes."""
        # Frame principal com padding
        main_frame = ttk.Frame(self.root, padding="4")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # PanedWindow para divisão horizontal
        self.pane = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        # Frame esquerdo: preview de vídeo
        preview_frame = ttk.LabelFrame(self.pane, text="Preview", padding="4")
        self.pane.add(preview_frame, weight=3)

        self.canvas = tk.Canvas(preview_frame, bg="#1a1a1a",
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Clique no preview calibra a cor na posição clicada
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Placeholder text no canvas
        self.canvas.create_text(320, 240, text="Clique Start para iniciar",
                                fill="#666666", font=("Segoe UI", 14),
                                tags="placeholder")

        # Frame direito: controles
        self.control_frame = ttk.LabelFrame(self.pane, text="Controls", padding="4")
        self.pane.add(self.control_frame, weight=1)

        # Frame inferior: log
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="2")
        log_frame.pack(fill=tk.X, pady=(4, 0))

        self.log_text = tk.Text(log_frame, height=6, width=80,
                                bg="#1e1e1e", fg="#d4d4d4",
                                font=("Consolas", 9), wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.tag_config("info", foreground="#d4d4d4")
        self.log_text.tag_config("warn", foreground="#ffaa00")
        self.log_text.tag_config("error", foreground="#ff4444")

    # -----------------------------------------------------------------------
    # Painel de controle
    # -----------------------------------------------------------------------

    def _build_controls(self):
        """Constrói os controles de parâmetros no painel direito."""
        cf = ttk.Frame(self.control_frame)
        cf.pack(fill=tk.BOTH, expand=True)

        row = 0

        # --- Modo ---
        ttk.Label(cf, text="Modo:", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        mode_frame = ttk.Frame(cf)
        mode_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        for i, (text, mode) in enumerate([("Teste", "test"), ("Ao Vivo", "live"),
                                          ("Vídeo", "video")]):
            rb = ttk.Radiobutton(mode_frame, text=text, variable=self._mode_var,
                                 value=mode, command=lambda m=mode: self._set_mode(m))
            rb.grid(row=0, column=i, padx=(0, 8))
        row += 1

        # --- Detecção ---
        ttk.Label(cf, text="Detecção:", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(4, 2))
        row += 1

        ttk.Label(cf, text="Método:").grid(row=row, column=0, sticky=tk.W)
        self.method_combo = ttk.Combobox(cf, values=["template", "color", "yolo"],
                                         state="readonly", width=12)
        self.method_combo.set("template")
        self.method_combo.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.method_combo.bind("<<ComboboxSelected>>",
                               lambda e: self._update_params(method=self.method_combo.get()))
        row += 1

        # --- Performance ---
        ttk.Label(cf, text="Performance:", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(8, 2))
        row += 1

        ttk.Label(cf, text="FPS alvo:").grid(row=row, column=0, sticky=tk.W)
        self.fps_scale = ttk.Scale(cf, from_=10, to=120, orient=tk.HORIZONTAL,
                                   value=30, length=120)
        self.fps_scale.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.fps_label = ttk.Label(cf, text="30")
        self.fps_label.grid(row=row, column=2, padx=(4, 0))
        self.fps_scale.configure(command=lambda v: (
            self.fps_label.configure(text=str(int(float(v)))),
            self._update_params(target_fps=int(float(v)))
        ))
        row += 1

        # --- Mira ---
        ttk.Label(cf, text="Mira:", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(8, 2))
        row += 1

        ttk.Label(cf, text="Suavização:").grid(row=row, column=0, sticky=tk.W)
        self.smooth_scale = ttk.Scale(cf, from_=0.0, to=0.9, orient=tk.HORIZONTAL,
                                      value=0.35, length=120)
        self.smooth_scale.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.smooth_label = ttk.Label(cf, text="0.35")
        self.smooth_label.grid(row=row, column=2, padx=(4, 0))
        self.smooth_scale.configure(command=lambda v: (
            self.smooth_label.configure(text=f"{float(v):.2f}"),
            self._update_params(smoothing=float(v))
        ))
        row += 1

        ttk.Label(cf, text="Deadzone (px):").grid(row=row, column=0, sticky=tk.W)
        self.deadzone_spin = ttk.Spinbox(cf, from_=0, to=50, width=5)
        self.deadzone_spin.set(5)
        self.deadzone_spin.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.deadzone_spin.bind("<KeyRelease>",
                                lambda e: self._update_params(deadzone=int(self.deadzone_spin.get() or 0)))
        row += 1

        ttk.Label(cf, text="Offset Y (px):").grid(row=row, column=0, sticky=tk.W)
        self.offset_spin = ttk.Spinbox(cf, from_=-50, to=50, width=5)
        self.offset_spin.set(-10)
        self.offset_spin.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.offset_spin.bind("<KeyRelease>",
                               lambda e: self._update_params(aim_offset_y=int(self.offset_spin.get() or 0)))
        row += 1

        # --- Aleatoriedade ---
        ttk.Label(cf, text="Simulação Humana:", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(8, 2))
        row += 1

        ttk.Label(cf, text="Ruído (px):").grid(row=row, column=0, sticky=tk.W)
        self.noise_scale = ttk.Scale(cf, from_=0, to=20, orient=tk.HORIZONTAL,
                                     value=3, length=120)
        self.noise_scale.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.noise_label = ttk.Label(cf, text="3")
        self.noise_label.grid(row=row, column=2, padx=(4, 0))
        self.noise_scale.configure(command=lambda v: (
            self.noise_label.configure(text=str(int(float(v)))),
            self._update_params(noise_px=float(v))
        ))
        row += 1

        ttk.Label(cf, text="Delay min (s):").grid(row=row, column=0, sticky=tk.W)
        self.delay_min_spin = ttk.Spinbox(cf, from_=0.0, to=0.5, increment=0.01, width=5)
        self.delay_min_spin.set(0.05)
        self.delay_min_spin.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.delay_min_spin.bind("<KeyRelease>", self._update_delays)
        row += 1

        ttk.Label(cf, text="Delay max (s):").grid(row=row, column=0, sticky=tk.W)
        self.delay_max_spin = ttk.Spinbox(cf, from_=0.0, to=0.5, increment=0.01, width=5)
        self.delay_max_spin.set(0.15)
        self.delay_max_spin.grid(row=row, column=1, sticky=tk.W, padx=(4, 0))
        self.delay_max_spin.bind("<KeyRelease>", self._update_delays)
        row += 1

        self.trigger_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cf, text="Auto-fire (atirar automático)",
                        variable=self.trigger_var,
                        command=lambda: self._update_params(
                            trigger_enabled=self.trigger_var.get())).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        row += 1

        # --- Debug / Calibração ---
        ttk.Separator(cf, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=8)
        row += 1

        ttk.Label(cf, text="Debug:", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cf, text="Visão HSV (mostra máscara de cores)",
                        variable=self.debug_var,
                        command=self._toggle_debug).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
        row += 1

        calib_frame = ttk.Frame(cf)
        calib_frame.grid(row=row, column=0, columnspan=3, pady=(0, 4))
        self.calib_btn = ttk.Button(calib_frame, text="🎯 Calibrar Cor (centro da tela)",
                                    command=self._calibrate_color)
        self.calib_btn.pack(fill=tk.X)
        ttk.Label(calib_frame, text="Clique na preview para calibrar",
                  font=("Segoe UI", 7), foreground="gray").pack()
        row += 1

        # --- Botões ---
        ttk.Separator(cf, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=8)
        row += 1

        btn_frame = ttk.Frame(cf)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=4)

        self.start_btn = ttk.Button(btn_frame, text="▶ Start",
                                    command=self._toggle_start_stop, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.pause_btn = ttk.Button(btn_frame, text="⏸ Pause",
                                    command=self._toggle_pause, width=10,
                                    state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.stop_btn = ttk.Button(btn_frame, text="⏹ Stop",
                                   command=self._emergency_stop, width=8)
        self.stop_btn.pack(side=tk.LEFT)

    # -----------------------------------------------------------------------
    # Barra de status
    # -----------------------------------------------------------------------

    def _build_status_bar(self):
        """Constrói a barra de status inferior."""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(self.status_bar, text="Pronto",
                                      relief=tk.SUNKEN, anchor=tk.W,
                                      padding=(8, 2))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.fps_status = ttk.Label(self.status_bar, text="FPS: 0",
                                    relief=tk.SUNKEN, padding=(8, 2), width=10)
        self.fps_status.pack(side=tk.RIGHT)

        self.det_status = ttk.Label(self.status_bar, text="Detecções: 0",
                                    relief=tk.SUNKEN, padding=(8, 2), width=15)
        self.det_status.pack(side=tk.RIGHT)

        self.time_status = ttk.Label(self.status_bar, text="00:00",
                                     relief=tk.SUNKEN, padding=(8, 2), width=8)
        self.time_status.pack(side=tk.RIGHT)

        self.mode_status = ttk.Label(self.status_bar, text="Modo: Teste",
                                     relief=tk.SUNKEN, padding=(8, 2), width=14)
        self.mode_status.pack(side=tk.RIGHT)

    # -----------------------------------------------------------------------
    # Ações
    # -----------------------------------------------------------------------

    def _toggle_start_stop(self):
        """Inicia ou para a pipeline."""
        if self.running:
            self._stop_pipeline()
        else:
            self._start_pipeline()

    def _start_pipeline(self):
        """Inicia a pipeline em uma thread separada."""
        if self.running:
            return

        self.running = True
        self.start_btn.configure(text="■ Stop")

        # Cria e inicia worker
        self.worker = PipelineWorker(
            self.frame_queue, self.status_queue, self.log_queue
        )

        # Aplica parâmetros atuais
        mode = self._mode_var.get()
        self.worker.update_params(
            mode=mode,
            method=self.method_combo.get(),
            target_fps=int(self.fps_scale.get()),
            smoothing=float(self.smooth_scale.get()),
            deadzone=int(self.deadzone_spin.get() or 0),
            noise_px=float(self.noise_scale.get()),
            aim_offset_y=int(self.offset_spin.get() or 0),
            trigger_enabled=self.trigger_var.get(),
            delay_min=float(self.delay_min_spin.get() or 0.05),
            delay_max=float(self.delay_max_spin.get() or 0.15),
        )

        # Se modo vídeo, abre arquivo
        if mode == "video":
            path = getattr(self, "_video_path", None)
            if path and os.path.exists(path):
                self.worker.start_video(path)
            else:
                self._open_video(start_if_selected=True)
                if not getattr(self, "_video_path", None):
                    self._stop_pipeline()
                    return

        self.worker.start()
        self.pause_btn.configure(state=tk.NORMAL, text="⏸ Pause")
        self.canvas.delete("placeholder")
        self.status_label.configure(text="Executando...")
        self._start_time = time.time()

        mode_names = {"test": "Teste", "live": "Ao Vivo", "video": "Vídeo"}
        self.mode_status.configure(text=f"Modo: {mode_names.get(mode, mode)}")
        self.logger.info(f"Pipeline iniciada (modo: {mode_names.get(mode, mode)}).")

    def _stop_pipeline(self):
        """Para a pipeline."""
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.worker.join(timeout=2.0)
        self.running = False
        self.start_btn.configure(text="▶ Start")
        self.pause_btn.configure(state=tk.DISABLED, text="⏸ Pause")
        self.status_label.configure(text="Parado")
        self.logger.info("Pipeline parada.")

    def _toggle_pause(self):
        """Alterna pausa da pipeline."""
        if self.worker:
            self.worker.pause()
            is_paused = not self.worker.pause_event.is_set()
            self.pause_btn.configure(text="▶ Resume" if is_paused else "⏸ Pause")
            self.status_label.configure(text="Pausado" if is_paused else "Executando...")

    def _emergency_stop(self):
        """Parada de emergência."""
        self.logger.warning("PARADA DE EMERGÊNCIA!")
        self._stop_pipeline()

    def _set_mode(self, mode: str):
        """Altera o modo de operação."""
        self._mode_var.set(mode)
        if mode == "video":
            self._open_video()

    def _toggle_debug(self):
        """Alterna visão de debug (HSV mask)."""
        is_debug = self.debug_var.get()
        self._update_params(debug_view=is_debug)
        if is_debug:
            self.canvas.itemconfig("hint", text="Visão HSV - branco = cores detectadas")
        else:
            self.canvas.itemconfig("hint", text="")

    def _calibrate_color(self):
        """
        Calibra a detecção de cor com base no centro da tela.
        Amostra a cor do centro do frame atual e ajusta os ranges HSV.
        """
        if not self.worker or not self.worker.is_alive():
            self.logger.warning("Pipeline não está rodando. Inicie primeiro.")
            return
        if not hasattr(self, '_last_raw_frame') or self._last_raw_frame is None:
            self.logger.warning("Nenhum frame disponível para calibração.")
            return

        frame = self._last_raw_frame
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2

        try:
            self.worker.detector.calibrate_from_roi(frame, cx, cy)
            self.logger.info("Calibração concluída! Cor do centro da tela ajustada.")
        except Exception as e:
            self.logger.error(f"Erro na calibração: {e}")

    def _on_canvas_click(self, event):
        """
        Calibra a detecção na posição onde o usuário clicou na preview.
        Útil para clicar em um inimigo na tela e ajustar as cores.
        """
        if not self.running or not self.worker or not self.worker.is_alive():
            return
        if not hasattr(self, '_last_raw_frame') or self._last_raw_frame is None:
            return

        # Converte coordenadas do clique para coordenadas do frame
        frame = self._last_raw_frame
        h_frame, w_frame = frame.shape[:2]
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w == 0 or canvas_h == 0:
            return

        # Proporção do frame no canvas
        scale_x = w_frame / canvas_w
        scale_y = h_frame / canvas_h
        fx = int(event.x * scale_x)
        fy = int(event.y * scale_y)
        fx = max(0, min(fx, w_frame - 1))
        fy = max(0, min(fy, h_frame - 1))

        try:
            self.worker.detector.calibrate_from_roi(frame, fx, fy)
            self.logger.info(f"Calibrado na posição ({fx}, {fy}) - cor ajustada!")
            self.debug_var.set(True)
            self._toggle_debug()
        except Exception as e:
            self.logger.error(f"Erro na calibração por clique: {e}")

    def _open_video(self, start_if_selected: bool = False):
        """Abre diálogo para selecionar arquivo de vídeo."""
        path = filedialog.askopenfilename(
            title="Selecionar Vídeo",
            filetypes=[("Vídeos", "*.mp4 *.avi *.mov *.mkv"),
                       ("Todos", "*.*")]
        )
        if path:
            self._video_path = path
            self._mode_var.set("video")
            self.mode_status.configure(text=f"Vídeo: {os.path.basename(path)}")
            self.logger.info(f"Vídeo selecionado: {path}")
            if start_if_selected and self.running:
                if self.worker:
                    self.worker.start_video(path)
        elif start_if_selected:
            self.logger.warning("Nenhum vídeo selecionado.")

    def _load_config(self):
        """Carrega configuração de arquivo JSON."""
        path = filedialog.askopenfilename(
            title="Carregar Configuração",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")]
        )
        if path:
            try:
                load_from_json(path)
                self.logger.info(f"Configuração carregada: {path}")
                self._sync_ui_from_config()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao carregar config: {e}")

    def _save_config(self):
        """Salva configuração em arquivo JSON."""
        path = filedialog.asksaveasfilename(
            title="Salvar Configuração",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if path:
            try:
                self._sync_config_from_ui()
                save_to_json(path)
                self.logger.info(f"Configuração salva: {path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao salvar config: {e}")

    def _sync_ui_from_config(self):
        """Sincroniza controles da UI com a configuração atual."""
        self.method_combo.set(DETECTION.method)
        self.fps_scale.set(SCREEN.target_fps)
        self.fps_label.configure(text=str(SCREEN.target_fps))
        self.smooth_scale.set(AIM.smoothing_factor)
        self.smooth_label.configure(text=f"{AIM.smoothing_factor:.2f}")
        self.deadzone_spin.set(AIM.deadzone_radius)
        self.offset_spin.set(AIM.aim_offset_y)
        self.noise_scale.set(RANDOM.position_noise_px)
        self.noise_label.configure(text=str(int(RANDOM.position_noise_px)))
        self.trigger_var.set(CMD.trigger_enabled)
        self._mode_var.set("test" if config.test_mode else "live")

    def _sync_config_from_ui(self):
        """Sincroniza configuração com valores atuais da UI."""
        config.test_mode = (self._mode_var.get() != "live")
        DETECTION.method = self.method_combo.get()
        SCREEN.target_fps = int(self.fps_scale.get())
        AIM.smoothing_factor = float(self.smooth_scale.get())
        AIM.deadzone_radius = int(self.deadzone_spin.get() or 0)
        AIM.aim_offset_y = int(self.offset_spin.get() or 0)
        RANDOM.position_noise_px = float(self.noise_scale.get())
        CMD.trigger_enabled = self.trigger_var.get()
        RANDOM.mouse_delay_min = float(self.delay_min_spin.get() or 0.05)
        RANDOM.mouse_delay_max = float(self.delay_max_spin.get() or 0.15)

    def _update_params(self, **kwargs):
        """Atualiza parâmetros do worker em tempo real."""
        if self.worker and self.worker.is_alive():
            self.worker.update_params(**kwargs)

    def _update_delays(self, event=None):
        """Atualiza delays no worker."""
        try:
            dmin = float(self.delay_min_spin.get() or 0.05)
            dmax = float(self.delay_max_spin.get() or 0.15)
            if dmin <= dmax:
                self._update_params(delay_min=dmin, delay_max=dmax)
            else:
                self.delay_min_spin.set(min(dmin, dmax))
                self.delay_max_spin.set(max(dmin, dmax))
        except ValueError:
            pass

    # -----------------------------------------------------------------------
# Polling das filas
# -----------------------------------------------------------------------

    def _poll_queues(self):
        """
        Verifica periodicamente as filas de comunicação com a pipeline.

        Este método é chamado a cada ~30ms via root.after().
        """
        # Processa frames
        try:
            while True:
                frame_data = self.frame_queue.get_nowait()
                self._display_frame(frame_data)
        except queue.Empty:
            pass

        # Processa status
        try:
            while True:
                status = self.status_queue.get_nowait()
                self._update_status(status)
        except queue.Empty:
            pass

        # Processa logs
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass

        # Verifica se worker morreu
        if self.running and self.worker and not self.worker.is_alive():
            self.logger.warning("Pipeline encerrada inesperadamente.")
            self._stop_pipeline()

        self.root.after(30, self._poll_queues)

    def _display_frame(self, frame: np.ndarray):
        """Converte frame OpenCV para tkinter e exibe no canvas."""
        if frame is None or frame.size == 0:
            return

        # Armazena frame original para calibração (mantém BGR)
        self._last_raw_frame = frame.copy()

        # Converte BGR -> RGB para exibição
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        self.current_image = ImageTk.PhotoImage(img)

        # Atualiza canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_image, tags="frame")
        self.canvas.create_text(10, 10, anchor=tk.NW, text="",
                                fill="#ffaa00", font=("Segoe UI", 10),
                                tags="hint")
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def _update_status(self, status: dict):
        """Atualiza indicadores de status na interface."""
        fps = status.get("fps", 0)
        dets = status.get("detections", 0)
        aim = status.get("aim")

        self.fps_status.configure(text=f"FPS: {fps:.1f}")
        self.det_status.configure(text=f"Detecções: {dets}")

        # Tempo de execução
        if hasattr(self, "_start_time"):
            elapsed = time.time() - self._start_time
            self.time_status.configure(
                text=time.strftime("%M:%S", time.gmtime(elapsed))
            )

        # Status
        if aim:
            self.status_label.configure(
                text=f"Alvo: ({aim[0]:.0f}, {aim[1]:.0f})")
        else:
            self.status_label.configure(text="Buscando alvo...")

    def _append_log(self, msg: str):
        """Adiciona mensagem ao log."""
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

        # Limita tamanho do log
        if self.log_text.index("end-1c").split(".")[0] > "500":
            self.log_text.delete("1.0", "2.0")

    # -----------------------------------------------------------------------
    # Diálogos
    # -----------------------------------------------------------------------

    @staticmethod
    def _show_about():
        """Mostra diálogo Sobre."""
        messagebox.showinfo(
            "Sobre",
            "AI Macro - Shooting System v1.0\n\n"
            "Sistema de macro com IA para jogos de tiro.\n"
            "Utiliza visão computacional para detectar alvos\n"
            "e auxiliar na mira.\n\n"
            "Modo teste: processa imagens sintéticas.\n"
            "Modo ao vivo: captura tela real e controla mouse.\n\n"
            "AVISO: Uso em jogos online pode violar termos de serviço."
        )

    @staticmethod
    def _show_shortcuts():
        """Mostra diálogo de atalhos."""
        messagebox.showinfo(
            "Atalhos",
            "Ctrl+O   - Abrir vídeo\n"
            "Ctrl+Q   - Sair\n"
            "F4       - Parada de emergência\n"
            "Espaço   - Start/Stop"
        )

    def _quit(self):
        """Encerra o aplicativo."""
        self._emergency_stop()
        self.root.destroy()

    # -----------------------------------------------------------------------
# Inicialização
# -----------------------------------------------------------------------

    def run(self):
        """Inicia o loop principal da interface."""
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    """Inicializa e executa o aplicativo."""
    app = MacroApp()
    app.run()


if __name__ == "__main__":
    main()
