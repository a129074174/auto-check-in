# -*- coding: utf-8 -*-
"""笑脸报到 —— Flask 本地 Web 应用入口。

负责：摄像头采集、人脸检测识别、分级匹配、语音播报、结果导出，
通过浏览器页面（web/）提供实时画面、选班、结果展示等交互。
"""
import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime

import cv2
from flask import Flask, Response, jsonify, render_template, request, send_file

from core.config import (
    ensure_dirs, CAMERA_URL, SIMILARITY_THRESHOLD, RECOGNIZE_INTERVAL,
    DEDUP_COOLDOWN, GALLERY_CACHE_FILE, BASE_PHOTOS_DIR, CAMERA_CONFIG_FILE, DATA_DIR,
)
from core.camera import Camera, CameraError, list_cameras
from core.gallery import Gallery
from core.recognizer import Recognizer
from core.matcher import match, DedupTracker
from core.voice import VoiceBroadcaster
from core.exporter import CheckinRecord, export_xlsx, make_export_path

def _resource_path(rel: str) -> str:
    """打包后资源位于解包目录 _MEIPASS；源码运行时位于脚本所在目录。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


app = Flask(__name__,
            template_folder=_resource_path("web/templates"),
            static_folder=_resource_path("web/static"))

# ===== 全局状态 =====
gallery = Gallery()
recognizer = None
camera = Camera()
voice = VoiceBroadcaster()
dedup = DedupTracker(DEDUP_COOLDOWN)

_state_lock = threading.Lock()
checkin_active = False
current_scope = {"school": "", "grade": "", "cls": "", "scope": "grade"}
results = []              # CheckinRecord 列表
latest_frame = None       # 最新一帧（供 MJPEG 流）
latest_faces_info = []    # [(bbox, matched, name)]
_last_fail_record = 0.0
_last_repeat_record = {}   # 重复记录节流：学生key -> 上次记录时间


# ===== 摄像头配置持久化 =====
def load_camera_config() -> str:
    try:
        with open(CAMERA_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("url", "")
    except Exception:
        return ""


def save_camera_config(url: str) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CAMERA_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"url": url}, f, ensure_ascii=False)
    except Exception:
        pass


# ===== 初始化 =====
def init_recognizer() -> None:
    global recognizer
    if recognizer is None:
        recognizer = Recognizer()


def load_gallery() -> None:
    """加载底册：缓存存在且未变化则秒开，否则建库。"""
    if gallery.load_cache(GALLERY_CACHE_FILE, BASE_PHOTOS_DIR):
        return
    init_recognizer()
    stats = gallery.build(BASE_PHOTOS_DIR, recognizer)
    gallery.save_cache(GALLERY_CACHE_FILE)
    print(f"底册建库完成：学生 {stats['students']} 人，跳过 {len(stats['skipped'])} 张")


# ===== 识别循环（后台线程） =====
def recognition_loop() -> None:
    global latest_frame, latest_faces_info, _last_fail_record
    last_rec = 0.0
    while True:
        frame = camera.read_frame()
        if frame is None:
            time.sleep(0.1)
            continue

        with _state_lock:
            latest_frame = frame.copy()
            active = checkin_active
            scope = dict(current_scope)

        if not active:
            time.sleep(0.05)
            continue

        now = time.time()
        if now - last_rec < RECOGNIZE_INTERVAL:
            time.sleep(0.02)
            continue
        last_rec = now

        try:
            faces = recognizer.detect_faces(frame)
        except Exception:
            faces = []

        info = []
        for f in faces:
            b = f.bbox.astype(int)
            emb = f.embedding
            if emb is None:
                info.append((b, False, ""))
                continue

            result = match(emb, gallery, scope["school"], scope["grade"],
                           scope["cls"], scope["scope"], SIMILARITY_THRESHOLD)

            if result.matched and result.student is not None:
                stu = result.student
                info.append((b, True, stu.name))
                rec = CheckinRecord(
                    name=stu.name, class_name=stu.class_dir,
                    time_str=datetime.now().strftime("%H:%M:%S"),
                    result="成功", similarity=result.similarity,
                    student_id=stu.student_id, school=stu.school_dir,
                    grade=stu.grade_dir, level=result.level,
                )
                if dedup.should_record(stu):
                    with _state_lock:
                        results.append(rec)
                    voice.speak(f"{stu.name}签到成功")
                else:
                    # 重复：同一学生冷却期内只记一条、只播报一次，避免刷屏
                    key = dedup._key(stu)
                    if now - _last_repeat_record.get(key, 0.0) >= DEDUP_COOLDOWN:
                        _last_repeat_record[key] = now
                        rec.result = "重复"
                        with _state_lock:
                            results.append(rec)
                        voice.speak(f"{stu.name}重复签到")
            else:
                info.append((b, False, ""))
                if now - _last_fail_record >= DEDUP_COOLDOWN:
                    _last_fail_record = now
                    rec = CheckinRecord(
                        name="", class_name=scope["cls"] or "全部",
                        time_str=datetime.now().strftime("%H:%M:%S"),
                        result="失败", similarity=result.similarity,
                        school=scope["school"], grade=scope["grade"],
                    )
                    with _state_lock:
                        results.append(rec)

        with _state_lock:
            latest_faces_info[:] = info


# ===== MJPEG 视频流 =====
def generate_video():
    while True:
        with _state_lock:
            frame = latest_frame.copy() if latest_frame is not None else None
            info = list(latest_faces_info)
        if frame is None:
            time.sleep(0.05)
            continue
        for b, matched, _ in info:
            color = (0, 200, 0) if matched else (0, 0, 255)
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), color, 2)
            cv2.putText(frame, "OK" if matched else "NO",
                        (b[0], max(0, b[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        time.sleep(0.03)


# ===== 页面 =====
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(generate_video(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ===== 选班数据 =====
@app.route("/api/schools")
def api_schools():
    return jsonify(gallery.list_schools())


@app.route("/api/grades")
def api_grades():
    return jsonify(gallery.list_grades(request.args.get("school", "")))


@app.route("/api/classes")
def api_classes():
    return jsonify(gallery.list_classes(request.args.get("school", ""),
                                        request.args.get("grade", "")))


# ===== 签到控制 =====
@app.route("/api/start", methods=["POST"])
def api_start():
    global checkin_active, current_scope
    data = request.get_json(silent=True) or {}
    school = data.get("school", "")
    grade = data.get("grade", "")
    cls = data.get("cls", "")
    scope = "class" if cls and cls not in ("全部", "全部班级") else "grade"
    with _state_lock:
        current_scope = {"school": school, "grade": grade, "cls": cls, "scope": scope}
        checkin_active = True
    return jsonify({"ok": True, "scope": scope})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global checkin_active
    with _state_lock:
        checkin_active = False
        latest_faces_info.clear()   # 停止后清除画面上的识别框
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    with _state_lock:
        active = checkin_active
        scope = dict(current_scope)
        total = len(results)
        success = sum(1 for r in results if r.result == "成功")
    return jsonify({"active": active, "scope": scope, "total": total, "success": success})


@app.route("/api/results")
def api_results():
    with _state_lock:
        data = [{
            "name": r.name, "class_name": r.class_name, "time": r.time_str,
            "result": r.result, "similarity": round(r.similarity, 3),
            "student_id": r.student_id, "level": r.level,
        } for r in results]
    return jsonify(data)


@app.route("/api/clear", methods=["POST"])
def api_clear():
    global results
    with _state_lock:
        results.clear()
    return jsonify({"ok": True})


@app.route("/api/export")
def api_export():
    with _state_lock:
        records = list(results)
        scope = dict(current_scope)
    if not records:
        return jsonify({"ok": False, "error": "还没有签到记录"}), 400
    name_part = f"{scope['school']}_{scope['grade']}_{scope['cls'] or '全部'}"
    path = export_xlsx(records, make_export_path(name_part))
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


# ===== 摄像头设置 =====
@app.route("/api/camera", methods=["GET", "POST"])
def api_camera():
    if request.method == "GET":
        return jsonify({"url": load_camera_config(), "cameras": list_cameras()})
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    save_camera_config(url)
    try:
        camera.open(url)
        return jsonify({"ok": True, "remote": camera.is_remote})
    except CameraError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# ===== 入口 =====
def main() -> None:
    ensure_dirs()
    print("正在加载底册...")
    load_gallery()
    print(f"底册加载完成，共 {gallery.total} 人")

    url = load_camera_config() or CAMERA_URL
    try:
        camera.open(url)
        print(f"摄像头已打开：{'网络流' if camera.is_remote else '本地摄像头'}")
    except CameraError as e:
        print(f"[警告] {e}")
        print("  可在网页里点「摄像头设置」重新连接。")

    print("正在加载人脸模型...")
    init_recognizer()
    print("人脸模型加载完成。")

    threading.Thread(target=recognition_loop, daemon=True).start()

    port = 5000
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"启动完成，请在浏览器访问 http://127.0.0.1:{port}（已自动打开）")
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
