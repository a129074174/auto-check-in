# -*- coding: utf-8 -*-
"""第 3 步验收脚本：摄像头实时识别 + 分级匹配 + 去重（命令行版）。

用法：
    python test_camera.py
        默认本地摄像头 + 第一个学校/年级 + 年级签到模式
    python test_camera.py "http://192.168.1.100:8080/video"
        指定手机摄像头地址
    python test_camera.py "" 示例学校 2024级 "(1)班"
        指定学校/年级/班级（班级签到模式；班级留空或写"全部"为年级签到）

运行中按 q 键退出。
"""
import sys
import time

import cv2

from core.config import (
    ensure_dirs, CAMERA_URL, SIMILARITY_THRESHOLD, RECOGNIZE_INTERVAL,
    DEDUP_COOLDOWN, GALLERY_CACHE_FILE, BASE_PHOTOS_DIR,
)
from core.gallery import Gallery
from core.recognizer import Recognizer
from core.camera import Camera, CameraError, list_cameras
from core.matcher import match, DedupTracker


def load_gallery() -> Gallery:
    gallery = Gallery()
    gallery.load_cache(GALLERY_CACHE_FILE)
    rec = Recognizer()
    stats = gallery.build(BASE_PHOTOS_DIR, rec)
    if stats.get("changed") or stats.get("removed"):
        gallery.save_cache(GALLERY_CACHE_FILE)
    print(f"建库完成：学生 {stats['students']} 人（新增/变更 {stats['changed']}，复用 {stats['reused']}，跳过 {len(stats['skipped'])} 张）")
    return gallery


def pick_scope(cls: str) -> str:
    """根据班级参数决定签到范围。"""
    if not cls or cls in ("全部", "全部班级", "all"):
        return "grade"
    return "class"


def main() -> None:
    ensure_dirs()
    args = sys.argv[1:]
    camera_url = args[0] if len(args) > 0 else CAMERA_URL

    gallery = load_gallery()
    if gallery.total == 0:
        print("底册为空，请先在 base_photos 下放入照片后重试。")
        return

    schools = gallery.list_schools()
    if not schools:
        print("底册为空。")
        return
    school = args[1] if len(args) > 1 else schools[0]
    grades = gallery.list_grades(school)
    grade = args[2] if len(args) > 2 else (grades[0] if grades else "")
    cls = args[3] if len(args) > 3 else ""
    scope = pick_scope(cls)

    print(f"签到范围：学校={school}  年级={grade}  班级={cls or '全部'}  模式={scope}")

    # 枚举可用摄像头设备（DroidCam 虚拟摄像头会以某个索引出现）
    available = list_cameras()
    print(f"检测到摄像头设备索引：{available if available else '无'}")
    if not camera_url or camera_url == "0":
        print("  本地模式下默认使用索引 0；")
        print("  如用 DroidCam 虚拟摄像头，请用参数指定索引，例如：python test_camera.py 1")

    cam = Camera()
    try:
        cam.open(camera_url)
    except CameraError as e:
        print(f"[错误] {e}")
        return
    print(f"摄像头已打开：{'网络流' if cam.is_remote else '本地摄像头（索引 ' + str(camera_url or 0) + '）'}")

    rec = Recognizer()
    dedup = DedupTracker(DEDUP_COOLDOWN)
    last_rec = 0.0
    display = []  # [(bbox, matched, name)]

    print("实时识别中... 按 q 键退出")
    while True:
        frame = cam.read_frame()
        if frame is None:
            print("读取画面失败，可能摄像头已断开。")
            break

        now = time.time()
        if now - last_rec >= RECOGNIZE_INTERVAL:
            last_rec = now
            faces = rec.detect_faces(frame)
            display = []
            for f in faces:
                b = f.bbox.astype(int)
                emb = f.embedding
                if emb is None:
                    display.append((b, False, ""))
                    continue
                result = match(emb, gallery, school, grade, cls, scope, SIMILARITY_THRESHOLD)
                name = ""
                if result.matched and result.student is not None:
                    name = result.student.name
                    if dedup.should_record(result.student):
                        print(f"[签到成功] {name}  相似度={result.similarity:.2f}  级别={result.level}")
                    else:
                        print(f"[重复] {name}（冷却期内）")
                else:
                    print(f"[未匹配] 相似度={result.similarity:.2f}")
                display.append((b, result.matched, name))

        for b, matched, name in display:
            color = (0, 255, 0) if matched else (0, 0, 255)
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), color, 2)
            cv2.putText(frame, "OK" if matched else "NO",
                        (b[0], max(0, b[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("face-check-in (q=quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cam.release()
    cv2.destroyAllWindows()
    print("已退出。")


if __name__ == "__main__":
    main()
