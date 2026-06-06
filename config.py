"""
Módulo de Configurações - Centraliza todos os parâmetros ajustáveis do sistema.

Função:
    Armazena e gerencia configurações de captura, detecção, mira, execução
    e aleatoriedade. Permite alternar entre modo de teste (sem comandos reais)
    e modo ao vivo. Todas as constantes podem ser sobrescritas via dicionário
    ou arquivo JSON externo para facilitar ajustes sem modificar o código.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Dataclasses de configuração - cada grupo de parâmetros é encapsulado
# separadamente para organização modular.
# ---------------------------------------------------------------------------

@dataclass
class ScreenCaptureConfig:
    """
    Configurações da captura de tela.

    Atributos:
        region: Tupla (left, top, width, height) definindo a região a capturar.
                Se None, captura o monitor inteiro.
        target_fps: Taxa de quadros alvo para o loop principal.
        use_dxcam: Se True, tenta usar DXCam (mais rápido em DXGI).
                   Se False, usa MSS (compatível com qualquer tela).
        monitor_index: Índice do monitor a ser capturado (1 = Principal).
        resolution: Resolução da captura (ex: "1920x1080", "3840x2160").
    """
    region: Optional[Tuple[int, int, int, int]] = None
    target_fps: int = 144
    use_dxcam: bool = True
    monitor_index: int = 1
    resolution: str = "1920x1080"


@dataclass
class DetectionConfig:
    """
    Configurações do detector de objetos.

    Atributos:
        method: 'template' para casamento de template OpenCV,
                'yolo' para YOLO via ONNX,
                'color' para detecção por faixa de cor HSV.
        confidence_threshold: Confiança mínima (0.0 a 1.0) para aceitar detecção.
        model_path: Caminho para o arquivo do modelo ONNX (se method='yolo').
        class_names: Lista de nomes de classes que o modelo reconhece.
        template_dir: Diretório com templates de busca (se method='template').
        target_classes: Classes de interesse (ex: ['person', 'player']).
        hsv_ranges: Lista de faixas HSV para detecção por cor.
    """
    method: str = "yolo"
    confidence_threshold: float = 0.35
    model_path: Optional[str] = None
    class_names: list = field(default_factory=lambda: ["person", "player", "enemy"])
    template_dir: Optional[str] = None
    target_classes: list = field(default_factory=lambda: ["person", "enemy"])
    hsv_ranges: list = field(default_factory=lambda: [
        {"lower": [0, 100, 100], "upper": [8, 255, 255], "label": "enemy"},
        {"lower": [170, 100, 100], "upper": [180, 255, 255], "label": "enemy"},
        {"lower": [100, 50, 50], "upper": [130, 255, 255], "label": "ally"},
        {"lower": [0, 0, 200], "upper": [180, 30, 255], "label": "enemy"},
    ])


@dataclass
class AimConfig:
    """
    Configurações do cálculo e suavização da mira.
    """
    smoothing_factor: float = 0.30
    aim_offset_x: int = 0
    aim_offset_y: int = 35
    deadzone_radius: int = 5
    tracking_deadzone: int = 2
    prediction_enabled: bool = False
    prediction_frames: int = 5
    fov_radius: int = 250  # Raio do círculo de FOV (em pixels)
    aim_zone: int = 2       # 1=Cabeça, 2=Peito, 3=Cintura
    aim_gain: float = 0.4   # Fator proporcional (0.1=lento, 0.5=rápido)



@dataclass
class RandomizationConfig:
    """
    Configurações de aleatoriedade para simular comportamento humano.

    Atributos:
        mouse_delay_min: Delay mínimo após mover o mouse (segundos).
        mouse_delay_max: Delay máximo após mover o mouse (segundos).
        click_delay_min: Delay mínimo antes de clicar (segundos).
        click_delay_max: Delay máximo antes de clicar (segundos).
        position_noise_px: Desvio padrão do ruído Gaussiano adicionado
                           à posição alvo da mira (pixels).
        movement_noise_std: Desvio padrão para pequenas variações na trajetória.
        miss_chance: Probabilidade (0.0 a 1.0) de errar o tiro propositalmente.
        reaction_time_min: Tempo mínimo de "reação" antes de começar a mirar (s).
        reaction_time_max: Tempo máximo de "reação" antes de começar a mirar (s).
        movement_jitter: Amplitude de tremor simulando pulso instável (px).
    """
    mouse_delay_min: float = 0.04
    mouse_delay_max: float = 0.10
    click_delay_min: float = 0.02
    click_delay_max: float = 0.06
    position_noise_px: float = 2.0
    movement_noise_std: float = 1.0
    miss_chance: float = 0.03
    reaction_time_min: float = 0.05
    reaction_time_max: float = 0.15
    movement_jitter: float = 0.5


@dataclass
class CommandConfig:
    """
    Configurações da execução de comandos.

    Atributos:
        enabled: Se False, nenhum comando real de mouse/teclado é executado.
                 Útil para testes seguros.
        mouse_sensitivity_multiplier: Multiplicador para sensibilidade do mouse.
        trigger_key: Tecla usada para atirar (ex: 'left' para botão esquerdo).
        trigger_enabled: Se True, atira automaticamente ao mirar no alvo.
        aim_button: Botão para ativar a mira (ex: 'shift', 'right', None = sempre).
    """
    enabled: bool = True
    mouse_sensitivity_multiplier: float = 1.0
    trigger_key: str = "left"
    trigger_enabled: bool = True
    aim_button: Optional[str] = "shift"


@dataclass
class AppConfig:
    """
    Configuração geral que agrega todos os sub-módulos.

    Atributos:
        test_mode: Se True, usa dados simulados sem comandos reais.
        log_level: Nível de logging (DEBUG, INFO, WARNING, ERROR).
        save_debug_frames: Salva frames com anotações para depuração.
        debug_dir: Diretório para salvar frames de depuração.
    """
    test_mode: bool = True
    log_level: str = "INFO"
    save_debug_frames: bool = False
    debug_dir: str = "debug_frames"

    screen: ScreenCaptureConfig = field(default_factory=ScreenCaptureConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    aim: AimConfig = field(default_factory=AimConfig)
    randomization: RandomizationConfig = field(default_factory=RandomizationConfig)
    command: CommandConfig = field(default_factory=CommandConfig)


# ---------------------------------------------------------------------------
# Instância global padrão
# ---------------------------------------------------------------------------
config = AppConfig()

# ---------------------------------------------------------------------------
# Atalhos para acesso direto às subconfigurações
# ---------------------------------------------------------------------------
SCREEN = config.screen
DETECTION = config.detection
AIM = config.aim
RANDOM = config.randomization
CMD = config.command


def load_from_json(filepath: str) -> None:
    """
    Carrega configurações a partir de um arquivo JSON e atualiza a
    instância global `config`.

    O JSON deve ter a mesma estrutura das dataclasses acima.
    Chaves não fornecidas mantêm os valores padrão.

    Args:
        filepath: Caminho absoluto ou relativo para o arquivo JSON.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Atualiza recursivamente os campos das dataclasses
    _update_dataclass(config, data)


def _update_dataclass(obj, data: dict) -> None:
    """
    Percorre recursivamente os campos de uma dataclass e atualiza
    valores conforme o dicionário `data`.

    Args:
        obj: Instância da dataclass a ser atualizada.
        data: Dicionário com os novos valores.
    """
    for key, value in data.items():
        if hasattr(obj, key):
            field_value = getattr(obj, key)
            if hasattr(field_value, "__dataclass_fields__") and isinstance(value, dict):
                _update_dataclass(field_value, value)
            else:
                setattr(obj, key, value)


def save_to_json(filepath: str) -> None:
    """
    Salva a configuração atual em um arquivo JSON.

    Args:
        filepath: Caminho para salvar o arquivo.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)


def set_test_mode(test_mode: bool = True) -> None:
    """
    Alterna rapidamente entre modo de teste e modo ao vivo.

    No modo de teste:
        - Command.execution.enabled = False
        - Screen.region = (0, 0, 640, 480) (resolução reduzida)
        - Nenhum movimento real de mouse/teclado ocorre.

    Args:
        test_mode: True ativa modo de teste, False desativa.
    """
    config.test_mode = test_mode
    config.command.enabled = not test_mode
    if test_mode:
        config.screen.region = (0, 0, 640, 480)
        print("[CONFIG] Modo de teste ATIVADO - nenhum comando real será executado.")
    else:
        config.screen.region = None
        print("[CONFIG] Modo ao vivo ATIVADO - comandos reais serão executados.")
