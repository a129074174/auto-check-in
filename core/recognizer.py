# -*- coding: utf-8 -*-
"""人脸检测与特征提取封装（基于 insightface / ArcFace 模型）。"""
import sys
import threading

from .config import DET_SIZE


def _model_root():
    """打包后返回解包目录（模型已内置），源码运行返回 None（用默认 ~/.insightface）。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", None)
    return None


class Recognizer:
    """封装 insightface 的人脸检测与 512 维特征提取，线程安全。"""

    def __init__(self, model_name="buffalo_l", det_size=None, providers=None):
        if det_size is None:
            det_size = DET_SIZE
        self._lock = threading.Lock()
        if providers is None:
            providers = ["CPUExecutionProvider"]

        try:
            from insightface.app import FaceAnalysis
        except ImportError as e:
            raise RuntimeError(
                "缺少 insightface 依赖，请先双击「安装环境.bat」完成安装。"
            ) from e

        # 首次运行会联网下载模型（约 300MB，保存在用户目录下），请保持网络畅通；
        # 打包后模型已内置，可完全离线使用。
        root = _model_root()
        if root:
            self.app = FaceAnalysis(name=model_name, root=root, providers=providers)
        else:
            self.app = FaceAnalysis(name=model_name, providers=providers)
        self.app.prepare(ctx_id=-1, det_size=det_size)

    def detect_faces(self, image_bgr):
        """检测图像中的所有人脸，返回人脸对象列表（每项含 bbox、embedding 等属性）。"""
        with self._lock:
            return self.app.get(image_bgr)

    @staticmethod
    def largest_face(faces):
        """从多张人脸中取出面积最大的一张（底册照片一般只有一张脸）。"""
        if not faces:
            return None

        def _area(f):
            b = f.bbox
            return (b[2] - b[0]) * (b[3] - b[1])

        return max(faces, key=_area)
