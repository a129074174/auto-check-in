# -*- coding: utf-8 -*-
"""第 2 步验收脚本：测试底册扫描、文件名解析、特征缓存。

用法（在项目目录下，命令行执行）：
    python test_gallery.py             # 完整测试（含模型特征提取，首次需联网下载一次模型）
    python test_gallery.py --no-model  # 只测目录扫描和文件名解析（不加载模型，无需联网）

提示：把测试照片放到 base_photos/学校/年级/班级/ 目录下再运行。
"""
import sys
import time

from core.config import ensure_dirs, BASE_PHOTOS_DIR, GALLERY_CACHE_FILE
from core.gallery import Gallery, parse_filename


def test_parse() -> None:
    print("=" * 50)
    print("1) 文件名解析测试（身份证号 + 姓名）")
    samples = [
        "11010120000101001X张三.jpg",
        "11010120000101002X李四.png",
        "王五.jpg",   # 无身份证号，应整体当作姓名
    ]
    for s in samples:
        sid, name = parse_filename(s)
        print(f"   {s:28s} -> 身份证号={sid or '(空)':20s} 姓名={name}")


def test_scan_and_cache(with_model: bool) -> None:
    print("=" * 50)
    print("2) 底册目录扫描")
    gallery = Gallery()
    recognizer = None
    if with_model:
        print("   正在加载人脸模型（首次运行需联网下载模型，请耐心等待）...")
        from core.recognizer import Recognizer
        recognizer = Recognizer()

    t0 = time.time()
    stats = gallery.build(BASE_PHOTOS_DIR, recognizer)
    cost = time.time() - t0
    print(f"   扫描完成，耗时 {cost:.2f} 秒")
    print(f"   学校数={stats['schools']}  年级数={stats['grades']}  "
          f"班级数={stats['classes']}  学生数={stats['students']}")
    if stats["skipped"]:
        print(f"   跳过 {len(stats['skipped'])} 张（读取失败/无脸/异常）：")
        for s in stats["skipped"][:10]:
            print(f"     - {s}")

    for school, grades in gallery.schools.items():
        print(f"   学校: {school}")
        for grade, classes in grades.items():
            total = sum(len(v) for v in classes.values())
            print(f"     年级: {grade}（共 {total} 人）")
            for cls, faces in classes.items():
                print(f"       班级: {cls}（{len(faces)} 人）")

    if with_model and gallery.total > 0:
        print("=" * 50)
        print("3) 特征缓存测试")
        ensure_dirs()
        gallery.save_cache(GALLERY_CACHE_FILE)
        print(f"   已保存缓存: {GALLERY_CACHE_FILE}")

        g2 = Gallery()
        t0 = time.time()
        ok = g2.load_cache(GALLERY_CACHE_FILE)
        cost = time.time() - t0
        print(f"   重新加载缓存: {'成功' if ok else '失败'}，耗时 {cost:.3f} 秒，共 {g2.total} 人")
        print("   （第二次加载应远快于第一次建库，说明缓存生效）")


if __name__ == "__main__":
    no_model = "--no-model" in sys.argv
    ensure_dirs()
    test_parse()
    test_scan_and_cache(with_model=not no_model)
    print("=" * 50)
    print("验收完成。请对照文档第 2 步的验收标准逐项确认。")
