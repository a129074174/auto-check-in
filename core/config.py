# -*- coding: utf-8 -*-
"""全局配置：所有可调参数集中在这里，现场可按需修改。"""
import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    """获取程序根目录（兼容 PyInstaller 打包后的运行场景）。"""
    if getattr(sys, "frozen", False):
        # 打包后：返回可执行文件所在目录
        return Path(sys.executable).resolve().parent
    # 源码运行：返回项目根目录（core 的上一级）
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()

# ===== 目录 =====
BASE_PHOTOS_DIR = str(BASE_DIR / "base_photos")                # 底册根目录：学校/年级/班级 三级结构
DATA_DIR = str(BASE_DIR / "data")                              # 运行期产物目录（特征缓存、结果、摄像头配置）
GALLERY_CACHE_FILE = os.path.join(DATA_DIR, "gallery_cache.npz")   # 人脸特征缓存文件
CAMERA_CONFIG_FILE = os.path.join(DATA_DIR, "camera_config.json")  # 摄像头地址配置文件

# ===== 摄像头 =====
CAMERA_URL = ""   # 手机 IP Webcam 视频流，如 http://192.168.1.100:8080/video；留空或填 0 用本地摄像头

# ===== 识别参数 =====
SIMILARITY_THRESHOLD = 0.4   # 余弦相似度阈值（ArcFace 经验值 0.4），越高越严格
RECOGNIZE_INTERVAL = 0.4     # 识别节流间隔（秒），降低 CPU 占用
DEDUP_COOLDOWN = 10          # 去重冷却时间（秒），同一学生此时间内不重复记录

# ===== 底册扫描 =====
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}   # 支持的图片扩展名


def ensure_dirs() -> None:
    """确保运行所需目录存在（底册目录、数据目录）。"""
    os.makedirs(BASE_PHOTOS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
