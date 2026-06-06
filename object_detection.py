"""
Módulo de Detecção de Objetos - Identifica inimigos, armas e alvos na tela.

Função:
    Oferece múltiplos métodos de detecção:
    1. Casamento de Template (template matching) - procura padrões visuais pré-definidos.
    2. Detecção por Cor (HSV) - segmenta alvos por faixas de cor.
    3. YOLO via ONNX Runtime - rede neural convolutional para detecção robusta.

    Cada método retorna uma lista padronizada de detecções contendo:
        - bounding box (x, y, w, h)
        - confidence (0.0 a 1.0)
        - class label (string)
        - centroide (cx, cy)

    O módulo é independente do resto do sistema e pode ser testado
    com imagens estáticas ou vídeos gravados.
"""

import os
import cv2
import numpy as np
import sys
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from config import DETECTION


# ---------------------------------------------------------------------------
# Estrutura de dados para uma detecção
# ---------------------------------------------------------------------------
@dataclass
class Detection:
    """
    Representa um objeto detectado em um frame.

    Atributos:
        bbox: Tupla (x, y, w, h) - bounding box em pixels.
        confidence: Pontuação de confiança (0.0 a 1.0).
        class_label: Nome da classe detectada (ex: "enemy", "weapon").
        centroid: Tupla (cx, cy) - centro do bounding box.
    """
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    class_label: str
    centroid: Tuple[float, float]

    @property
    def area(self) -> int:
        """Área do bounding box em pixels quadrados."""
        _, _, w, h = self.bbox
        return w * h


class ObjectDetector:
    """
    Detector de objetos multi-método.

    Modos de operação:
        - 'template': Casamento de template OpenCV (rápido, precisa de imagens de referência).
        - 'color': Segmentação por faixa de cor HSV (leve, bom para HUDs coloridos).
        - 'yolo': YOLO via ONNX (preciso, requer modelo treinado).

    Args:
        method: Método de detecção ('template', 'color', 'yolo').
    """

    def __init__(self, method: str = "template"):
        self.method: str = method or DETECTION.method
        self.templates: Dict[str, np.ndarray] = {}
        self._yolo_session = None
        self._yolo_classes: List[str] = []

        if self.method == "template":
            self._load_templates()
        elif self.method == "yolo":
            self._init_yolo()
        elif self.method == "color":
            print("[DETECT] Detecção por cor HSV selecionada.")
        else:
            raise ValueError(f"Método de detecção desconhecido: {method}")

    # -----------------------------------------------------------------------
    # Métodos públicos
    # -----------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Executa a detecção no frame fornecido.

        Args:
            frame: Imagem BGR (numpy.ndarray) shape (H, W, 3).

        Returns:
            Lista de objetos Detection encontrados, ordenados por confiança
            (maior primeiro). Lista vazia se nada for detectado.
        """
        if frame is None or frame.size == 0:
            return []

        if self.method == "template":
            return self._detect_template(frame)
        elif self.method == "color":
            return self._detect_color(frame)
        elif self.method == "yolo":
            return self._detect_yolo(frame)
        return []

    def detect_from_file(self, image_path: str) -> List[Detection]:
        """
        Carrega uma imagem do disco e executa a detecção.

        Útil para testes com imagens gravadas do jogo.

        Args:
            image_path: Caminho para o arquivo de imagem.

        Returns:
            Lista de detecções na imagem.
        """
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"[ERRO] Não foi possível carregar: {image_path}")
            return []
        return self.detect(frame)

    def draw_detections(self, frame: np.ndarray,
                        detections: List[Detection]) -> np.ndarray:
        """
        Desenha bounding boxes e labels das detecções no frame.
        Útil para depuração visual.

        Args:
            frame: Imagem original (BGR).
            detections: Lista de detecções a desenhar.

        Returns:
            Cópia do frame com anotações desenhadas.
        """
        annotated = frame.copy()
        for det in detections:
            x, y, w, h = det.bbox
            # Caixa verde para inimigo, azul para outros
            color = (0, 255, 0) if det.class_label == "enemy" else (255, 0, 0)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            # Label com confiança
            label = f"{det.class_label} {det.confidence:.2f}"
            cv2.putText(annotated, label, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            # Centroide
            cx, cy = det.centroid
            cv2.circle(annotated, (int(cx), int(cy)), 4, (0, 0, 255), -1)
        return annotated

    # -----------------------------------------------------------------------
    # Métodos internos - Casamento de Template
    # -----------------------------------------------------------------------

    def _load_templates(self) -> None:
        """
        Carrega imagens de template do diretório configurado.

        Cada arquivo .png ou .jpg no diretório de templates é carregado.
        O nome do arquivo (sem extensão) vira o class_label.
        """
        template_dir = DETECTION.template_dir
        if not template_dir or not os.path.isdir(template_dir):
            print("[DETECT] Nenhum diretório de templates configurado.")
            print("[DETECT] Use templates padrão sintéticos (internos).")
            self._generate_default_templates()
            return

        for fname in os.listdir(template_dir):
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                path = os.path.join(template_dir, fname)
                template = cv2.imread(path, cv2.IMREAD_COLOR)
                if template is not None:
                    label = os.path.splitext(fname)[0]
                    self.templates[label] = template
                    print(f"[DETECT] Template carregado: {label} ({template.shape})")

        if not self.templates:
            print("[DETECT] Nenhum template válido encontrado. Usando sintéticos.")
            self._generate_default_templates()

    def _generate_default_templates(self) -> None:
        """
        Gera templates sintéticos simples para teste.

        Cria padrões geométricos (círculos, cruzes) que simulam
        elementos visuais de jogos de tiro (miras, inimigos simplificados).
        """
        # Template "enemy" - um círculo vermelho
        enemy_tmpl = np.zeros((40, 40, 3), dtype=np.uint8)
        cv2.circle(enemy_tmpl, (20, 20), 15, (0, 0, 200), -1)
        cv2.circle(enemy_tmpl, (20, 20), 8, (255, 255, 255), -1)
        self.templates["enemy"] = enemy_tmpl

        # Template "crosshair" - uma mira simples
        cross_tmpl = np.zeros((30, 30, 3), dtype=np.uint8)
        cv2.line(cross_tmpl, (15, 0), (15, 30), (0, 255, 0), 2)
        cv2.line(cross_tmpl, (0, 15), (30, 15), (0, 255, 0), 2)
        self.templates["crosshair"] = cross_tmpl

        print(f"[DETECT] {len(self.templates)} templates sintéticos gerados.")

    def _detect_template(self, frame: np.ndarray) -> List[Detection]:
        """
        Executa casamento de template multi-escala.

        Para cada template, percorre múltiplas escalas (0.5x a 1.5x)
        e usa correspondência por correlação normalizada (TM_CCOEFF_NORMED).

        Returns:
            Lista de detecções com confiança acima do threshold.
        """
        detections: List[Detection] = []
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h_frame, w_frame = gray_frame.shape

        for label, template in self.templates.items():
            gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            h_tmpl, w_tmpl = gray_tmpl.shape

            # Multi-escala
            for scale in np.linspace(0.5, 1.5, 5):
                scaled_w = int(w_tmpl * scale)
                scaled_h = int(h_tmpl * scale)
                if scaled_w < 10 or scaled_h < 10:
                    continue
                if scaled_w > w_frame or scaled_h > h_frame:
                    continue

                resized = cv2.resize(gray_tmpl, (scaled_w, scaled_h))
                result = cv2.matchTemplate(gray_frame, resized, cv2.TM_CCOEFF_NORMED)

                locations = np.where(result >= DETECTION.confidence_threshold)
                for pt in zip(*locations[::-1]):
                    x, y = pt[0], pt[1]
                    w, h = scaled_w, scaled_h
                    centroid = (x + w / 2.0, y + h / 2.0)
                    confidence = float(result[y, x])
                    detections.append(Detection(
                        bbox=(x, y, w, h),
                        confidence=confidence,
                        class_label=label,
                        centroid=centroid
                    ))

        # Remove detecções duplicadas via supressão não-máxima (NMS)
        return self._nms(detections)

    # -----------------------------------------------------------------------
    # Métodos internos - Detecção por Cor (HSV)
    # -----------------------------------------------------------------------

    def _detect_color(self, frame: np.ndarray) -> List[Detection]:
        """
        Detecta objetos por segmentação de cor no espaço HSV.

        Para cada faixa HSV configurada, cria uma máscara binária,
        encontra contornos e retorna os bounding boxes.

        Útil para jogos onde inimigos têm cores distintas (ex: vermelho/azul).

        Returns:
            Lista de detecções por cor.
        """
        detections: List[Detection] = []
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for hsv_range in DETECTION.hsv_ranges:
            lower = np.array(hsv_range["lower"], dtype=np.uint8)
            upper = np.array(hsv_range["upper"], dtype=np.uint8)
            label = hsv_range.get("label", "target")

            mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.erode(mask, None, iterations=1)
            mask = cv2.dilate(mask, None, iterations=2)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 50:  # Filtra ruído muito pequeno
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                centroid = (x + w / 2.0, y + h / 2.0)
                # Confiança baseada na solidez do contorno
                hull = cv2.convexHull(cnt)
                hull_area = cv2.contourArea(hull)
                solidity = area / hull_area if hull_area > 0 else 0
                confidence = min(1.0, solidity * 1.2)

                detections.append(Detection(
                    bbox=(x, y, w, h),
                    confidence=confidence,
                    class_label=label,
                    centroid=centroid
                ))

        return self._nms(detections)

    # -----------------------------------------------------------------------
    # Métodos internos - YOLO via ONNX
    # -----------------------------------------------------------------------

    def _init_yolo(self) -> None:
        """
        Inicializa o modelo YOLO usando ONNX Runtime.

        Carrega o modelo do caminho configurado. Se não houver caminho,
        procura por 'yolov8n.onnx' no diretório atual ou ao lado do executável.
        Se não encontrar, avisa e volta para template matching.
        """
        model_path = DETECTION.model_path
        if not model_path or not os.path.exists(model_path):
            search_dirs = [
                os.path.dirname(__file__),
                os.getcwd(),
                os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd(),
            ]
            model_path = None
            for d in search_dirs:
                candidate = os.path.join(d, "yolov8n.onnx")
                if os.path.exists(candidate):
                    model_path = candidate
                    break
            if not model_path:
                print(f"[WARN] Modelo YOLO não encontrado.")
                print("[WARN] Voltando para detecção por template.")
                self.method = "template"
                self._load_templates()
                return

        try:
            import importlib
            ort = importlib.import_module('onnxruntime')
            self._yolo_session = ort.InferenceSession(
                model_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
            )
            self._yolo_classes = DETECTION.class_names
            print(f"[DETECT] YOLO carregado: {model_path}")
        except ImportError:
            print("[WARN] ONNX Runtime não instalado. pip install onnxruntime")
            self.method = "template"
            self._load_templates()
        except Exception as e:
            print(f"[WARN] Erro ao carregar YOLO: {e}. Usando template.")
            self.method = "template"
            self._load_templates()

    def _detect_yolo(self, frame: np.ndarray) -> List[Detection]:
        """
        Executa inferência com YOLO via ONNX Runtime.

        Usa 320x320 para inferência mais rápida em CPU (~30-50ms).
        O frame é redimensionado com letterbox para manter aspect ratio.

        Returns:
            Lista de detecções YOLO.
        """
        if self._yolo_session is None:
            return []

        try:
            h_orig, w_orig = frame.shape[:2]
            # Usa 320 para inferência mais rápida em CPU
            target_size = 320
            w_in, h_in = target_size, target_size

            # Letterbox resize
            scale = min(w_in / w_orig, h_in / h_orig)
            nw, nh = int(w_orig * scale), int(h_orig * scale)
            dw, dh = (w_in - nw) // 2, (h_in - nh) // 2

            resized = cv2.resize(frame, (nw, nh))
            padded = np.full((h_in, w_in, 3), 114, dtype=np.uint8)
            padded[dh:dh+nh, dw:dw+nw] = resized

            # Normaliza
            blob = np.transpose(padded.astype(np.float32) / 255.0, (2, 0, 1))
            blob = np.expand_dims(blob, axis=0)

            # Inferência
            outputs = self._yolo_session.run(None,
                {self._yolo_session.get_inputs()[0].name: blob})
            output = outputs[0][0]  # (84, 8400)

            detections: List[Detection] = []

            for i in range(output.shape[1]):
                det = output[:, i]
                cx, cy, w, h = det[:4]
                scores = det[4:]
                class_id = np.argmax(scores)
                confidence = float(scores[class_id])

                if confidence < DETECTION.confidence_threshold:
                    continue

                # Filtra apenas pessoa (classe 0 no COCO)
                if class_id != 0:
                    continue

                # Remove padding e escala
                cx = (cx - dw) / scale
                cy = (cy - dh) / scale
                w = w / scale
                h = h / scale

                if w <= 0 or h <= 0:
                    continue

                x = int(cx - w / 2)
                y = int(cy - h / 2)

                detections.append(Detection(
                    bbox=(x, y, int(w), int(h)),
                    confidence=confidence,
                    class_label="enemy",
                    centroid=(cx, cy)
                ))

            return self._nms(detections, iou_threshold=0.5)

        except Exception as e:
            print(f"[ERRO] Falha na inferência YOLO: {e}")
            return []

    # -----------------------------------------------------------------------
    # Utilitários
    # -----------------------------------------------------------------------

    @staticmethod
    def _nms(detections: List[Detection],
             iou_threshold: float = 0.4) -> List[Detection]:
        """
        Supressão Não-Máxima (Non-Maximum Suppression).

        Remove detecções duplicadas que se sobrepõem acima do limiar IoU.
        Mantém apenas a detecção com maior confiança entre as sobrepostas.

        Args:
            detections: Lista de detecções.
            iou_threshold: Limiar de Intersection over Union.

        Returns:
            Lista filtrada de detecções.
        """
        if not detections:
            return []

        # Converte para formato OpenCV
        boxes = np.array([[d.bbox[0], d.bbox[1],
                          d.bbox[0] + d.bbox[2], d.bbox[1] + d.bbox[3]]
                         for d in detections], dtype=np.float32)
        scores = np.array([d.confidence for d in detections], dtype=np.float32)

        indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(),
                                   DETECTION.confidence_threshold, iou_threshold)

        if len(indices) == 0:
            return []

        indices = indices.flatten() if len(indices.shape) > 1 else indices
        return [detections[i] for i in indices]

    def get_center_of_screen(self, frame: np.ndarray) -> Tuple[float, float]:
        """
        Retorna o centro do frame (ponto central da tela/região).

        Args:
            frame: Imagem atual.

        Returns:
            Tupla (cx, cy) com o centro em pixels.
        """
        h, w = frame.shape[:2]
        return (w / 2.0, h / 2.0)

    # -----------------------------------------------------------------------
    # Métodos de calibração e debug
    # -----------------------------------------------------------------------

    def get_hsv_mask(self, frame: np.ndarray) -> np.ndarray:
        """
        Gera uma máscara HSV combinada de todas as faixas configuradas.
        Útil para debug visual - mostra exatamente o que está sendo detectado.

        Args:
            frame: Imagem BGR.

        Returns:
            Máscara binária (branco = detectado, preto = não detectado).
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        combined = np.zeros(frame.shape[:2], dtype=np.uint8)

        for hsv_range in DETECTION.hsv_ranges:
            lower = np.array(hsv_range["lower"], dtype=np.uint8)
            upper = np.array(hsv_range["upper"], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            combined = cv2.bitwise_or(combined, mask)

        return combined

    def get_debug_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Gera um frame de debug com 3 painéis:
        - Original + detecções
        - Máscara HSV
        - Contornos

        Args:
            frame: Imagem original BGR.

        Returns:
            Frame concatenado para visualização.
        """
        h, w = frame.shape[:2]
        small_w = w // 2
        small_h = h // 2

        # Painel 1: Original com detecções
        detections = self.detect(frame)
        panel1 = self.draw_detections(frame, detections)
        panel1 = cv2.resize(panel1, (small_w, small_h))

        # Painel 2: Máscara HSV
        mask = self.get_hsv_mask(frame)
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        panel2 = cv2.resize(mask_bgr, (small_w, small_h))

        # Painel 3: Contornos na máscara
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        panel3 = np.zeros((small_h, small_w, 3), dtype=np.uint8)
        cv2.drawContours(panel3, contours, -1, (0, 255, 0), 1)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 50:
                x, y, cw, ch = cv2.boundingRect(cnt)
                cv2.rectangle(panel3, (x * small_w // w, y * small_h // h),
                             ((x + cw) * small_w // w, (y + ch) * small_h // h),
                             (0, 0, 255), 1)

        # Painel 4: Detecção por movimento/contraste (edges)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        panel4 = cv2.resize(edges_bgr, (small_w, small_h))

        # Monta grid 2x2
        top = np.hstack([panel1, panel2])
        bottom = np.hstack([panel3, panel4])
        debug = np.vstack([top, bottom])

        return debug

    def calibrate_from_roi(self, frame: np.ndarray, x: int, y: int, w: int = 10, h: int = 10):
        """
        Amostra a cor de uma região da tela e atualiza as faixas HSV
        para detectar aquela cor específica.

        Útil para calibração: o usuário clica em um inimigo na tela
        e o sistema ajusta os ranges HSV automaticamente.

        Args:
            frame: Imagem BGR atual.
            x, y: Centro da região de amostra.
            w, h: Largura e altura da região.
        """
        h_frame, w_frame = frame.shape[:2]
        x1 = max(0, x - w // 2)
        y1 = max(0, y - h // 2)
        x2 = min(w_frame, x + w // 2)
        y2 = min(h_frame, y + h // 2)

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return

        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h_mean = int(np.mean(hsv_roi[:, :, 0]))
        s_mean = int(np.mean(hsv_roi[:, :, 1]))
        v_mean = int(np.mean(hsv_roi[:, :, 2]))
        h_std = int(np.std(hsv_roi[:, :, 0]))
        s_std = int(np.std(hsv_roi[:, :, 1]))
        v_std = int(np.std(hsv_roi[:, :, 2]))

        # Cria range dinâmico com margem
        margin_h = max(10, h_std * 2)
        margin_s = max(40, s_std * 2)
        margin_v = max(40, v_std * 2)

        lower_h = max(0, h_mean - margin_h)
        upper_h = min(180, h_mean + margin_h)
        lower_s = max(0, s_mean - margin_s)
        upper_s = min(255, s_mean + margin_s)
        lower_v = max(0, v_mean - margin_v)
        upper_v = min(255, v_mean + margin_v)

        new_range = {
            "lower": [lower_h, lower_s, lower_v],
            "upper": [upper_h, upper_s, upper_v],
            "label": "calibrated_enemy"
        }

        # Adiciona ou substitui o primeiro range
        if DETECTION.hsv_ranges and DETECTION.hsv_ranges[0].get("label") == "calibrated_enemy":
            DETECTION.hsv_ranges[0] = new_range
        else:
            DETECTION.hsv_ranges.insert(0, new_range)

        print(f"[CALIBRADO] HSV médio: ({h_mean}, {s_mean}, {v_mean}) "
              f"| Range: H[{lower_h}-{upper_h}] S[{lower_s}-{upper_s}] V[{lower_v}-{upper_v}]")


# ---------------------------------------------------------------------------
# Bloco de teste rápido
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    detector = ObjectDetector(method="template")
    print("Testando detector...")

    # Cria uma imagem de teste sintética
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(test_img, (200, 200), 30, (0, 0, 200), -1)  # "inimigo" vermelho
    cv2.circle(test_img, (400, 300), 20, (0, 200, 0), -1)  # outro objeto

    dets = detector.detect(test_img)
    print(f"Detecções encontradas: {len(dets)}")
    for d in dets:
        print(f"  - {d.class_label}: {d.bbox} conf={d.confidence:.2f}")

    annotated = detector.draw_detections(test_img, dets)
    cv2.imshow("Teste Detecção", annotated)
    cv2.waitKey(2000)
    cv2.destroyAllWindows()
