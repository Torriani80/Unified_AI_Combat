import subprocess
from jarvis.utils.logger import log


class ScreenController:
    def __init__(self):
        self._pyautogui = None

    def _ensure_import(self):
        if self._pyautogui is None:
            try:
                import pyautogui
                pyautogui.FAILSAFE = True
                self._pyautogui = pyautogui
            except ImportError:
                log.warn("pyautogui not installed. Screen control disabled.")

    def click(self, x: int, y: int):
        self._ensure_import()
        if self._pyautogui:
            self._pyautogui.click(x, y)

    def type_text(self, text: str, interval: float = 0.05):
        self._ensure_import()
        if self._pyautogui:
            self._pyautogui.write(text, interval=interval)

    def press_key(self, key: str):
        self._ensure_import()
        if self._pyautogui:
            self._pyautogui.press(key)

    def screenshot(self, path: str = None):
        self._ensure_import()
        if self._pyautogui:
            return self._pyautogui.screenshot(path)

    def locate_on_screen(self, image: str, confidence: float = 0.8):
        self._ensure_import()
        if self._pyautogui:
            try:
                return self._pyautogui.locateOnScreen(image, confidence=confidence)
            except:
                return None

    def open_website(self, url: str):
        try:
            import webbrowser
            webbrowser.open(url)
            log.info(f"Opened URL: {url}")
        except Exception as e:
            log.error(f"Failed to open URL: {e}")

    def run_command(self, cmd: str):
        try:
            subprocess.Popen(cmd, shell=True)
            log.info(f"Running: {cmd}")
        except Exception as e:
            log.error(f"Command failed: {e}")
