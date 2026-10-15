# -*- coding: utf-8 -*-
"""语音播报：用 Windows 自带语音（pyttsx3 / SAPI5），签到成功时播报，离线可用。"""
import queue
import threading

# 串行播报锁：避免多段语音重叠、多个 SAPI 引擎同时发声。
_tts_lock = threading.Lock()


def _speak_once(text: str) -> None:
    """完成一次播报。每次重新初始化引擎，规避 pyttsx3 复用同一引擎时
    runAndWait 播完不返回、后续播报全部卡死的已知问题。"""
    import pyttsx3
    engine = None
    try:
        engine = pyttsx3.init()
        # 优先选用中文语音
        try:
            for v in engine.getProperty("voices"):
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
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass


class VoiceBroadcaster:
    """后台线程 + 队列串行播报，避免阻塞识别主流程；初始化失败时静默降级。"""

    def __init__(self):
        self._queue = queue.Queue()
        self._enabled = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                break
            # 每条播报用独立线程执行：某条卡住也不会阻塞后续播报
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    @staticmethod
    def _speak(text: str) -> None:
        with _tts_lock:
            _speak_once(text)

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
