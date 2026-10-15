# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：onedir 免安装文件夹，内置人脸模型（完全离线可用）。"""
import os

from PyInstaller.utils.hooks import collect_all

# 收集 insightface / onnxruntime 的全部数据、动态库、隐藏导入
insightface_datas, insightface_bins, insightface_hidden = collect_all("insightface")
onnx_datas, onnx_bins, onnx_hidden = collect_all("onnxruntime")

# 内置人脸模型（把 ~/.insightface/models 打进包，作为 models/ 目录）
model_datas = []
home = os.path.expanduser("~")
model_dir = os.path.join(home, ".insightface", "models")
if os.path.isdir(model_dir):
    for root, dirs, files in os.walk(model_dir):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, model_dir)
            model_datas.append((src, os.path.join("models", rel)))
else:
    print("[警告] 未找到模型目录：%s" % model_dir)
    print("       请先联网运行一次程序（自动下载模型）后再打包。")

datas = [
    ("web/templates", "web/templates"),
    ("web/static", "web/static"),
] + model_datas + insightface_datas + onnx_datas

binaries = insightface_bins + onnx_bins
hiddenimports = insightface_hidden + onnx_hidden

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas",
        "PyQt5", "PySide2", "PySide6", "PyQt6",
        "IPython", "notebook", "jupyter", "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="启动签到",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # 保留控制台，方便查看启动日志
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="人脸签到系统",
)
