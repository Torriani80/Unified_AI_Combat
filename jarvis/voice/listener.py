import threading
import queue
from jarvis.utils.logger import log


class VoiceListener:
    def __init__(self, wake_word: str = "jarvis", language: str = "pt-BR"):
        self.wake_word = wake_word.lower()
        self.language = language
        self._queue = queue.Queue()
        self._running = False
        self._thread = None
        self._recognizer = None

    def _try_imports(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._sr = sr
            return True
        except ImportError:
            log.warn("speech_recognition not installed. Voice disabled.")
            return False

    def start(self):
        if not self._try_imports():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Voice listener started")
        return True

    def stop(self):
        self._running = False

    def _listen_loop(self):
        with self._sr.Microphone() as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            while self._running:
                try:
                    audio = self._recognizer.listen(source, timeout=1, phrase_time_limit=10)
                    try:
                        text = self._recognizer.recognize_google(audio, language=self.language)
                        text = text.lower().strip()
                        if text:
                            if text.startswith(self.wake_word):
                                cmd = text[len(self.wake_word):].strip()
                                if cmd:
                                    self._queue.put(("command", cmd))
                                else:
                                    self._queue.put(("wake", ""))
                            else:
                                self._queue.put(("speech", text))
                    except:
                        pass
                except:
                    pass

    def get_command(self, timeout: float = 0.1):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def listen_once(self, timeout: float = 5.0) -> str:
        if not self._recognizer:
            return ""
        try:
            import speech_recognition as sr
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
                text = self._recognizer.recognize_google(audio, language=self.language)
                return text
        except:
            return ""
