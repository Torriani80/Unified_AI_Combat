import os
import cv2
import numpy as np
from object_detection import ObjectDetector
from config import config

def test_yolo_load():
    print("Testing YOLO load...")
    try:
        detector = ObjectDetector(method="yolo")
        print(f"Detector method: {detector.method}")
        if detector.method != "yolo":
            print("FAILED: Detector fell back to template matching!")
            return False
        print("SUCCESS: YOLO loaded correctly.")

        # Test with a dummy frame (black image)
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = detector.detect(frame)
        print(f"Inference successful. Detections: {len(detections)}")
        return True
    except Exception as e:
        print(f"ERROR during YOLO test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if test_yolo_load():
        print("\nOverall Result: PASS")
    else:
        print("\nOverall Result: FAIL")
        exit(1)
