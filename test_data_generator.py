"""
Gerador de Dados de Teste - Cria imagens e vídeos sintéticos para testar o sistema.

Função:
    Gera cenários de jogo simulados com:
    - Fundo de ambiente (arenas, mapas simplificados).
    - Inimigos em diferentes posições, tamanhos e ângulos.
    - Elementos de HUD (mira, saúde, munição).
    - Movimento de alvos (para testar predição).
    - Variações de iluminação e cor.

    Os dados gerados permitem testar todos os módulos do sistema
    sem necessidade de acesso a um jogo real.
"""

import os
import cv2
import numpy as np
from typing import List, Tuple, Optional


class TestDataGenerator:
    """
    Gera imagens e vídeos sintéticos simulando cenas de jogos de tiro.

    Atributos:
        width / height: Dimensões da imagem/vídeo.
        output_dir: Diretório para salvar os arquivos gerados.
    """

    def __init__(self, width: int = 640, height: int = 480,
                 output_dir: str = "test_data"):
        self.width: int = width
        self.height: int = height
        self.output_dir: str = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # -----------------------------------------------------------------------
    # Geração de imagem única
    # -----------------------------------------------------------------------

    def generate_scene(self, num_enemies: int = 3,
                       include_hud: bool = True) -> np.ndarray:
        """
        Gera uma cena completa de jogo.

        Componentes:
            1. Fundo (gradiente ou textura de arena).
            2. Inimigos (figuras humanoides simplificadas).
            3. HUD (barra de vida, mira, munição).

        Args:
            num_enemies: Número de inimigos na cena.
            include_hud: Se True, adiciona elementos de HUD.

        Returns:
            Imagem BGR (numpy.ndarray).
        """
        frame = self._generate_background()
        self._add_enemies(frame, num_enemies)
        if include_hud:
            self._add_hud(frame)
        return frame

    def _generate_background(self) -> np.ndarray:
        """
        Cria um fundo de arena com gradiente e textura de chão.

        Returns:
            Imagem de fundo BGR.
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Gradiente do céu (azul escuro para claro)
        for y in range(self.height // 2):
            intensity = int(50 + (y / (self.height // 2)) * 100)
            frame[y, :] = (intensity, intensity, 150)

        # Chão (marrom/esverdeado)
        for y in range(self.height // 2, self.height):
            intensity = int(80 + ((y - self.height // 2) / (self.height // 2)) * 60)
            frame[y, :] = (30, intensity // 2, intensity // 3)

        # Adiciona ruído de textura
        noise = np.random.randint(0, 20, (self.height, self.width, 3), dtype=np.uint8)
        frame = cv2.addWeighted(frame, 0.9, noise, 0.1, 0)

        return frame

    def _add_enemies(self, frame: np.ndarray, count: int) -> None:
        """
        Desenha inimigos simplificados (figuras humanoides) na cena.

        Cada inimigo é composto por:
        - Círculo para cabeça
        - Retângulo para corpo
        - Linhas para braços/pernas

        Varia cor (vermelho/azul), tamanho e orientação para simular
        diferentes tipos de alvo.

        Args:
            frame: Imagem base para desenhar.
            count: Número de inimigos.
        """
        h, w = frame.shape[:2]
        colors = [(0, 0, 200), (200, 0, 0), (0, 150, 150), (150, 0, 150)]

        for i in range(count):
            x = np.random.randint(50, w - 50)
            y = np.random.randint(50, h - 100)
            scale = np.random.uniform(0.5, 1.5)
            color = colors[i % len(colors)]

            # Cabeça
            head_radius = int(12 * scale)
            cv2.circle(frame, (x, y - 20), head_radius, color, -1)
            cv2.circle(frame, (x, y - 20), head_radius, (255, 255, 255), 1)

            # Corpo
            body_h = int(40 * scale)
            body_w = int(20 * scale)
            cv2.rectangle(frame,
                         (x - body_w // 2, y),
                         (x + body_w // 2, y + body_h),
                         color, -1)
            cv2.rectangle(frame,
                         (x - body_w // 2, y),
                         (x + body_w // 2, y + body_h),
                         (255, 255, 255), 1)

            # Braços
            arm_len = int(25 * scale)
            cv2.line(frame, (x - body_w // 2, y + 5),
                     (x - body_w // 2 - arm_len, y + 15), color, 2)
            cv2.line(frame, (x + body_w // 2, y + 5),
                     (x + body_w // 2 + arm_len, y + 15), color, 2)

            # Pernas
            leg_len = int(20 * scale)
            cv2.line(frame, (x - 5, y + body_h),
                     (x - 8, y + body_h + leg_len), color, 2)
            cv2.line(frame, (x + 5, y + body_h),
                     (x + 8, y + body_h + leg_len), color, 2)

    def _add_hud(self, frame: np.ndarray) -> None:
        """
        Adiciona elementos de HUD (Heads-Up Display) simulados.

        Inclui:
        - Mira no centro da tela (crosshair).
        - Barra de vida no canto inferior esquerdo.
        - Indicador de munição no canto inferior direito.

        Args:
            frame: Imagem base para desenhar.
        """
        h, w = frame.shape[:2]

        # Mira (crosshair) no centro
        cx, cy = w // 2, h // 2
        crosshair_size = 15
        cv2.line(frame, (cx - crosshair_size, cy),
                 (cx + crosshair_size, cy), (0, 255, 0), 1)
        cv2.line(frame, (cx, cy - crosshair_size),
                 (cx, cy + crosshair_size), (0, 255, 0), 1)
        cv2.circle(frame, (cx, cy), 2, (0, 255, 0), 1)

        # Barra de vida
        bar_x, bar_y = 20, h - 40
        bar_w, bar_h = 150, 15
        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
        health_pct = 0.7
        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + int(bar_w * health_pct), bar_y + bar_h),
                     (0, 0, 200), -1)
        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + bar_w, bar_y + bar_h), (200, 200, 200), 1)

        # Texto de vida
        cv2.putText(frame, "HP", (bar_x, bar_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Munição
        ammo_x, ammo_y = w - 120, h - 40
        cv2.putText(frame, "30 / 90", (ammo_x, ammo_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # -----------------------------------------------------------------------
    # Geração de vídeo simulado
    # -----------------------------------------------------------------------

    def generate_video(self, output_path: str, num_frames: int = 300,
                       fps: int = 30, num_enemies: int = 3) -> str:
        """
        Gera um vídeo sintético simulando uma partida de jogo.

        Os inimigos se movem pela tela com trajetórias suaves
        (senoidais), permitindo testar:
        - Detecção frame a frame.
        - Predição de movimento.
        - Suavização da mira.

        Args:
            output_path: Caminho para salvar o vídeo (.mp4 ou .avi).
            num_frames: Número de quadros do vídeo.
            fps: Quadros por segundo.
            num_enemies: Número de inimigos animados.

        Returns:
            Caminho absoluto do vídeo gerado.
        """
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps,
                              (self.width, self.height))

        # Posições e velocidades iniciais dos inimigos
        color_map = [(0, 0, 200), (200, 0, 0), (0, 150, 150), (150, 0, 150)]
        enemies = []
        for _ in range(num_enemies):
            color_idx = np.random.randint(0, len(color_map))
            enemies.append({
                "x": np.random.randint(100, self.width - 100),
                "y": np.random.randint(100, self.height - 100),
                "phase_x": np.random.uniform(0, 2 * np.pi),
                "phase_y": np.random.uniform(0, 2 * np.pi),
                "amplitude_x": np.random.randint(30, 100),
                "amplitude_y": np.random.randint(20, 60),
                "speed": np.random.uniform(0.5, 2.0),
                "color": color_map[color_idx],
            })

        for frame_idx in range(num_frames):
            frame = self._generate_background()
            t = frame_idx / fps  # Tempo em segundos

            for enemy in enemies:
                # Movimento senoidal
                ex = int(enemy["x"] + enemy["amplitude_x"] *
                         np.sin(t * enemy["speed"] + enemy["phase_x"]))
                ey = int(enemy["y"] + enemy["amplitude_y"] *
                         np.cos(t * enemy["speed"] + enemy["phase_y"]))

                # Desenha inimigo
                self._draw_simple_enemy(frame, ex, ey, enemy["color"])

            self._add_hud(frame)
            out.write(frame)

        out.release()
        abs_path = os.path.abspath(output_path)
        print(f"[TEST] Vídeo gerado: {abs_path} ({num_frames} quadros, {fps} FPS)")
        return abs_path

    @staticmethod
    def _draw_simple_enemy(frame: np.ndarray, x: int, y: int,
                           color: Tuple[int, int, int]) -> None:
        """
        Desenha um inimigo simplificado em uma posição específica.

        Args:
            frame: Imagem base.
            x, y: Posição central do inimigo.
            color: Cor BGR.
        """
        cv2.circle(frame, (x, y - 12), 10, color, -1)
        cv2.rectangle(frame, (x - 10, y), (x + 10, y + 25), color, -1)
        cv2.line(frame, (x - 10, y + 5), (x - 25, y + 10), color, 2)
        cv2.line(frame, (x + 10, y + 5), (x + 25, y + 10), color, 2)

    # -----------------------------------------------------------------------
    # Geração em lote
    # -----------------------------------------------------------------------

    def generate_test_dataset(self, num_images: int = 10) -> List[str]:
        """
        Gera um conjunto de imagens de teste com variações.

        Cada imagem tem número e posição diferentes de inimigos,
        além de variações de iluminação.

        Args:
            num_images: Número de imagens a gerar.

        Returns:
            Lista de caminhos das imagens geradas.
        """
        paths = []
        for i in range(num_images):
            num_enemies = np.random.randint(1, 6)
            frame = self.generate_scene(num_enemies=num_enemies)
            path = os.path.join(self.output_dir, f"test_scene_{i:03d}.png")
            cv2.imwrite(path, frame)
            paths.append(path)
            print(f"[TEST] Imagem salva: {path} ({num_enemies} inimigos)")

        return paths


# ---------------------------------------------------------------------------
# Bloco de teste rápido
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    gen = TestDataGenerator(output_dir="test_data")
    print("Gerando dados de teste...")

    # Gera imagens
    images = gen.generate_test_dataset(num_images=5)
    print(f"Geradas {len(images)} imagens.")

    # Gera vídeo
    video_path = gen.generate_video("test_data/test_match.mp4",
                                     num_frames=150, fps=30, num_enemies=4)
    print(f"Vídeo gerado: {video_path}")

    # Mostra uma imagem de exemplo
    sample = gen.generate_scene(num_enemies=3)
    cv2.imshow("Cena de Teste", sample)
    cv2.waitKey(2000)
    cv2.destroyAllWindows()
