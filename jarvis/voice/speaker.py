import threading
from jarvis.utils.logger import log


class VoiceSpeaker:
    def __init__(self, engine: str = "edge"):
        self.engine = engine
        self._engine_obj = None
        self._init_engine()

    def _init_engine(self):
        if self.engine == "edge":
            try:
                import edge_tts
                self._tts = edge_tts
                self._use_edge = True
                log.info("TTS: using edge-tts")
                return
            except ImportError:
                log.warn("edge-tts not installed, falling back to pyttsx3")

        try:
            import pyttsx3
            self._engine_obj = pyttsx3.init()
            voices = self._engine_obj.getProperty("voices")
            pt_voices = [v for v in voices if "portuguese" in v.name.lower() or "brazil" in v.name.lower()]
            if pt_voices:
                self._engine_obj.setProperty("voice", pt_voices[0].id)
            self._engine_obj.setProperty("rate", 180)
            self._engine_obj.setProperty("volume", 0.9)
            self._use_edge = False
            log.info("TTS: using pyttsx3")
        except ImportError:
            log.warn("pyttsx3 not installed. TTS disabled.")
            self._use_edge = False
            self._engine_obj = None

    def say(self, text: str, async_mode: bool = True):
        if not text:
            return
        if async_mode:
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()
        else:
            self._speak(text)

    def _speak(self, text: str):
        try:
            if hasattr(self, '_use_edge') and self._use_edge:
                import asyncio
                voice = "pt-BR-FranciscaNeural"
                asyncio.run(self._tts.Communicate(text, voice).save(""))
            elif self._engine_obj:
                self._engine_obj.say(text)
                self._engine_obj.runAndWait()
        except Exception as e:
            log.error(f"TTS error: {e}")
