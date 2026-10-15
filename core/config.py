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
# 摄像头来源，支持三种写法：
#   "" 或 "0"   -> 本地摄像头（第一个设备，索引 0）
#   "1" / "2"    -> 指定第几个摄像头设备（DroidCam 虚拟摄像头通常是非 0 的某个索引，可用 list_cameras() 查看）
#   "http://192.168.1.100:8080/video" -> 手机 IP Webcam 的 MJPEG 局域网流
CAMERA_URL = ""

# ===== 识别参数 =====
SIMILARITY_THRESHOLD = 0.4   # 余弦相似度阈值（ArcFace 经验值 0.4），越高越严格
RECOGNIZE_INTERVAL = 0.4     # 识别节流间隔（秒），降低 CPU 占用
DEDUP_COOLDOWN = 10          # 重复/失败记录的节流间隔（秒）；成功记录每个签到批次只记一次

# ===== 底册扫描 =====
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}   # 支持的图片扩展名

# 示例底册目录（占位符，方便首次测试；真实使用时替换为真实的学校/年级/班级名即可）
EXAMPLE_PHOTOS_DIR = os.path.join(BASE_PHOTOS_DIR, "示例学校", "2024级", "(1)班")


def ensure_dirs() -> None:
    """确保运行所需目录存在。
    底册根目录、数据目录始终创建；示例三级目录仅在底册根目录下
    还没有任何学校目录时创建（首次使用占位符），之后用户自行改名、
    增删学校目录都不会被覆盖或重新生成。"""
    os.makedirs(BASE_PHOTOS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    has_school = any(p.is_dir() for p in Path(BASE_PHOTOS_DIR).iterdir())
    if not has_school:
        os.makedirs(EXAMPLE_PHOTOS_DIR, exist_ok=True)
