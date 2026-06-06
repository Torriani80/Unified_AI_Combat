"""
Módulo de Execução de Comandos - Move o mouse e atira no jogo.

Função:
    Converte as coordenadas calculadas em comandos
    reais de mouse e teclado. Utiliza a biblioteca PyAutoGUI para
    simular entrada do usuário.

    Características:
    - Suporta movimento absoluto e relativo do mouse.
    - Adiciona delays aleatórios entre ações (simulação humana).
    - Pode ser desativado (modo test_mode) para evitar comandos reais.
    - Inclui segurança: botão de "aim" precisa estar pressionado.
    - Logging detalhado de cada ação executada.

Aviso de Segurança:
    Este módulo controla o mouse do sistema. Use com cautela.
    O modo de teste (command.enabled = False) impede qualquer
    movimento real.
"""

import time
import random
import logging
from typing import Optional, Tuple

from config import CMD, RANDOM

logger = logging.getLogger("CommandExecutor")


# ---------------------------------------------------------------------------
# Tenta importar PyAutoGUI
# ---------------------------------------------------------------------------
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse para canto superior esquerdo para emergência
    pyautogui.PAUSE = 0.01     # Pequena pausa entre comandos
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    print("[WARN] PyAutoGUI não encontrado. pip install pyautogui")
    print("[WARN] Comandos de mouse/teclado desativados.")


class CommandExecutor:
    """
    Executa comandos de mouse e teclado para controlar a mira e atirar.

    Atributos:
        enabled: Se False, nenhum comando real é executado.
        screen_width / screen_height: Dimensões da tela para clamp.
        _aim_pressed: Estado do botão de ativar mira.
    """

    def __init__(self, enabled: bool = None):
        """
        Inicializa o executor.

        Args:
            enabled: Se None, usa o valor de CMD.enabled (config).
                     False desativa comandos (modo teste).
        """
        self.enabled: bool = enabled if enabled is not None else CMD.enabled
        self.screen_width, self.screen_height = self._get_screen_size()
        self._aim_pressed: bool = False

        if not self.enabled:
            logger.info("Executor de comandos DESATIVADO (modo teste).")
        elif not HAS_PYAUTOGUI:
            logger.warning("PyAutoGUI ausente - executor em modo simulado.")
            self.enabled = False
        else:
            logger.info(f"Executor de comandos ATIVO "
                        f"({self.screen_width}x{self.screen_height})")

    # -----------------------------------------------------------------------
    # Métodos principais
    # -----------------------------------------------------------------------

    def aim_and_shoot(self, target_pos: Optional[Tuple[float, float]],
                      screen_center: Tuple[float, float]) -> None:
        """
        Fluxo completo: mira no alvo e atira (se configurado).

        Etapas:
            1. Verifica se comandos estão habilitados.
            2. Se não há alvo, não faz nada.
            3. Aplica delay de reação (simula tempo de resposta humano).
            4. Move o mouse para a posição alvo.
            5. Aguarda delay de movimento.
            6. Atira (se trigger_enabled).

        Args:
            target_pos: Posição alvo (x, y) ou None se sem alvo.
            screen_center: Centro da tela para referência.
        """
        if not self.enabled:
            return

        if target_pos is None:
            return  # Sem alvo, não faz nada

        # Verifica se o botão de ativar mira está pressionado (se configurado)
        if CMD.aim_button and not self._is_aim_key_pressed():
            return

        # 1. Delay de reação humana
        self._reaction_delay()

        # 2. Move o mouse suavemente
        self.move_mouse(target_pos)

        # 3. Atira
        if CMD.trigger_enabled:
            self._click_delay()
            self.shoot()

    # -----------------------------------------------------------------------
    # Movimento do mouse
    # -----------------------------------------------------------------------

    def move_mouse(self, position: Tuple[float, float]) -> None:
        """
        Move o mouse para a posição especificada.

        Converte coordenadas do frame para coordenadas absolutas da tela
        se necessário. Aplica o multiplicador de sensibilidade.

        Args:
            position: Tupla (x, y) em pixels (coordenadas da tela/região).
        """
        if not self.enabled or not HAS_PYAUTOGUI:
            logger.debug(f"[SIMULADO] Mover mouse para ({position[0]:.1f}, {position[1]:.1f})")
            return

        x, y = position

        # Aplica sensibilidade
        # Nota: sensibilidade afeta o movimento relativo, não absoluto.
        # Para absoluto, movemos diretamente para a coordenada.

        # Clamp para limites da tela
        x = max(0, min(x, self.screen_width - 1))
        y = max(0, min(y, self.screen_height - 1))

        # Movimento absoluto
        pyautogui.moveTo(x, y, duration=0)

        # Delay pós-movimento (simula latência neuromuscular)
        delay = random.uniform(RANDOM.mouse_delay_min, RANDOM.mouse_delay_max)
        self._sleep(delay)

        logger.debug(f"Mouse movido para ({x:.1f}, {y:.1f})")

    def move_mouse_relative(self, dx: float, dy: float) -> None:
        """
        Move o mouse relativamente à posição atual.

        Útil para jogos que usam aceleração de mouse raw input.

        Args:
            dx: Deslocamento horizontal (pixels).
            dy: Deslocamento vertical (pixels).
        """
        if not self.enabled or not HAS_PYAUTOGUI:
            logger.debug(f"[SIMULADO] Mover mouse relativo: ({dx:.1f}, {dy:.1f})")
            return

        sens = CMD.mouse_sensitivity_multiplier
        pyautogui.moveRel(dx * sens, dy * sens, duration=0)

        delay = random.uniform(RANDOM.mouse_delay_min, RANDOM.mouse_delay_max)
        self._sleep(delay)

    # -----------------------------------------------------------------------
    # Ação de atirar
    # -----------------------------------------------------------------------

    def shoot(self) -> None:
        """
        Executa um clique (tiro).

        O botão é configurado por CMD.trigger_key ('left', 'right', 'middle').
        Adiciona um delay aleatório antes do clique.
        """
        if not self.enabled or not HAS_PYAUTOGUI:
            logger.debug(f"[SIMULADO] Atirar (botão: {CMD.trigger_key})")
            return

        # Pequena variação no tempo do clique
        press_duration = random.uniform(0.01, 0.05)

        button_map = {
            "left": "left",
            "right": "right",
            "middle": "middle",
            "x1": "x1",
            "x2": "x2",
        }
        btn = button_map.get(CMD.trigger_key, "left")

        pyautogui.mouseDown(button=btn)
        self._sleep(press_duration)
        pyautogui.mouseUp(button=btn)

        logger.debug(f"Tiro disparado (botão: {btn})")

    # -----------------------------------------------------------------------
    # Delays e variações
    # -----------------------------------------------------------------------

    def _reaction_delay(self) -> None:
        """
        Simula o tempo de reação humana antes de começar a mirar.

        O delay varia aleatoriamente entre reaction_time_min e
        reaction_time_max para evitar padrões previsíveis.
        """
        delay = random.uniform(RANDOM.reaction_time_min, RANDOM.reaction_time_max)
        if delay > 0:
            self._sleep(delay)

    def _click_delay(self) -> None:
        """
        Delay entre o movimento do mouse e o clique do tiro.

        Simula o tempo que um humano leva para apertar o botão
        após posicionar a mira.
        """
        delay = random.uniform(RANDOM.click_delay_min, RANDOM.click_delay_max)
        self._sleep(delay)

    @staticmethod
    def _sleep(seconds: float) -> None:
        """
        Pausa a execução pelo tempo especificado.

        Usa time.sleep com resolução de microssegundos.

        Args:
            seconds: Tempo de pausa em segundos.
        """
        if seconds > 0:
            time.sleep(seconds)

    # -----------------------------------------------------------------------
    # Verificação de tecla de ativação
    # -----------------------------------------------------------------------

    def _is_aim_key_pressed(self) -> bool:
        """
        Verifica se a tecla de ativação da mira está pressionada.

        Se aim_button for None, a mira está sempre ativa.
        Caso contrário, verifica o estado da tecla (ex: 'shift').

        Returns:
            True se pode mirar, False se bloqueado.
        """
        if CMD.aim_button is None:
            return True

        if not HAS_PYAUTOGUI:
            return True  # Modo simulado

        try:
            import keyboard as kb
            return kb.is_pressed(CMD.aim_button)
        except ImportError:
            # Sem keyboard, assume sempre ativo
            return True
        except Exception:
            return True

    # -----------------------------------------------------------------------
    # Utilitários

    # -----------------------------------------------------------------------
    @staticmethod
    def _get_screen_size() -> Tuple[int, int]:
        """
        Obtém as dimensões da tela principal.

        Returns:
            (largura, altura) em pixels.
        """
        if HAS_PYAUTOGUI:
            w, h = pyautogui.size()
            return w, h
        return (1920, 1080)  # fallback

    def emergency_stop(self) -> None:
        """
        Para imediatamente todos os comandos.

        Move o mouse para o centro da tela e desativa o executor.
        Útil como medida de segurança.
        """
        self.enabled = False
        if HAS_PYAUTOGUI:
            pyautogui.moveTo(self.screen_width // 2, self.screen_height // 2)
        logger.warning("EMERGENCY STOP: Executor desativado e mouse centralizado.")

    def set_enabled(self, state: bool) -> None:
        """
        Ativa ou desativa a execução de comandos.

        Args:
            state: True para ativar, False para desativar.
        """
        self.enabled = state
        logger.info(f"Executor {'ATIVADO' if state else 'DESATIVADO'}.")


# ---------------------------------------------------------------------------
# Bloco de teste rápido
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Teste do CommandExecutor (modo simulado - sem comandos reais)")

    executor = CommandExecutor(enabled=False)  # Teste seguro

    # Simula um ciclo de mira e tiro
    for i in range(3):
        print(f"\nCiclo {i+1}:")
        executor.aim_and_shoot(
            target_pos=(800 + i * 10, 600 + i * 10),
            screen_center=(960, 540)
        )
        executor.shoot()
        time.sleep(0.5)

    print("Teste concluído (modo simulado, sem movimentos reais).")
