# -*- coding: utf-8 -*-
"""语音播报：用 Windows 自带语音（pyttsx3 / SAPI5），签到成功时播报，离线可用。"""
import queue
import threading


class VoiceBroadcaster:
    """后台线程 + 队列串行播报，避免阻塞识别主流程；初始化失败时静默降级。"""

    def __init__(self):
        self._queue = queue.Queue()
        self._enabled = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        engine = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # 优先选用中文语音
            try:
                voices = engine.getProperty("voices")
                for v in voices:
                    name = (getattr(v, "name", "") or "").lower()
                    if any(k in name for k in ("chinese", "zh", "huihui", "yaoyao", "kangkang", "xiaoxiao")):
                        engine.setProperty("voice", v.id)
                        break
            except Exception:
                pass
            try:
                engine.setProperty("rate", 160)
            except Exception:
                pass
        except Exception:
            engine = None
            self._enabled = False

        while True:
            text = self._queue.get()
            if text is None:
                break
            if engine is None:
                continue
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass

    def speak(self, text: str) -> None:
        """把要播报的文字加入队列（成功时调用，如 speak(f"{name}签到成功")）。"""
        if self._enabled:
            try:
                self._queue.put(text)
            except Exception:
                pass

    def shutdown(self) -> None:
        try:
            self._queue.put(None)
        except Exception:
            pass
