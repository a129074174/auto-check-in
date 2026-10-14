# -*- coding: utf-8 -*-
"""摄像头采集封装：优先读取手机 IP Webcam 局域网流，回退本地 USB 摄像头。"""
from urllib.parse import urlparse

import cv2


class CameraError(Exception):
    """摄像头打开失败时抛出，message 为面向用户的中文提示。"""


def normalize_source(url):
    """把用户输入的摄像头地址规整为 cv2.VideoCapture 可用的形式。
    - 空串 / "0"           -> 0（本地摄像头）
    - "192.168.1.100:8080" -> "http://192.168.1.100:8080/video"
    - "http://...:8080"    -> "http://...:8080/video"（IP Webcam 的 MJPEG 流）
    """
    s = (url or "").strip()
    if not s or s == "0":
        return 0
    if s.isdigit():
        return int(s)
    if not s.startswith(("http://", "https://")):
        s = "http://" + s
    p = urlparse(s)
    if not p.path or p.path == "/":
        s = s.rstrip("/") + "/video"
    return s


class Camera:
    def __init__(self):
        self._cap = None
        self.is_remote = False

    def open(self, url: str = "") -> None:
        """打开摄像头。url 为空或 '0' 时使用本地摄像头。"""
        self.release()
        source = normalize_source(url)
        self.is_remote = isinstance(source, str)

        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            self._cap.release()
            self._cap = None
            if self.is_remote:
                raise CameraError(
                    "无法连接手机摄像头，请检查：\n"
                    "  1. 手机与电脑是否连接同一 WiFi；\n"
                    "  2. 手机 IP Webcam App 是否已点「Start server」启动；\n"
                    "  3. 摄像头地址是否正确（形如 http://192.168.x.x:8080/video）。"
                )
            raise CameraError("未检测到本地摄像头，请检查摄像头是否已连接、是否被其他程序占用。")

    def read_frame(self):
        """读取一帧，失败返回 None。"""
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
