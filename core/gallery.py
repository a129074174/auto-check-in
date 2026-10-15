# -*- coding: utf-8 -*-
"""底册扫描建库：解析「学校/年级/班级」三级目录与「身份证号+姓名」文件名，生成/加载特征缓存。"""
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

from .config import IMAGE_EXTS


@dataclass
class StudentFace:
    """一张底册照片对应一个学生。"""
    student_id: str          # 身份证号（从文件名解析，可能为空）
    name: str                # 姓名（从文件名解析）
    school_dir: str          # 学校目录名
    grade_dir: str           # 年级目录名
    class_dir: str           # 班级目录名
    embedding: np.ndarray    # 512 维人脸特征


_ID_PATTERN = re.compile(r"^(\d{17}[\dXx])(.*)$")


def parse_filename(filename: str) -> Tuple[str, str]:
    """把「身份证号+姓名」文件名拆成 (身份证号, 姓名)。
    无法按 18 位身份证号解析时，身份证号返回空串、整个主名当作姓名。"""
    stem = Path(filename).stem
    m = _ID_PATTERN.match(stem)
    if m:
        return m.group(1).upper(), m.group(2)
    return "", stem


def imread_unicode(path) -> np.ndarray:
    """读取图片，兼容中文路径（cv2.imread 对中文路径不友好，改用 imdecode）。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def compute_base_signature(base_dir: str) -> str:
    """计算底册目录的指纹：所有图片文件的相对路径 + 大小 + 修改时间。
    底册增删改照片后指纹会变化，用于让特征缓存自动失效、重新建库。"""
    base = Path(base_dir)
    items = []
    if base.exists():
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                st = p.stat()
                items.append(f"{p.relative_to(base)}|{st.st_size}|{int(st.st_mtime)}")
    return hashlib.md5("\n".join(items).encode("utf-8")).hexdigest()


class Gallery:
    """底册索引：school -> grade -> class -> [StudentFace]。"""

    def __init__(self):
        self.schools: Dict[str, Dict[str, Dict[str, List[StudentFace]]]] = {}
        self._flat: List[StudentFace] = []
        self.base_signature: str = ""

    # ---- 查询 ----
    def class_gallery(self, school: str, grade: str, cls: str) -> List[StudentFace]:
        return self.schools.get(school, {}).get(grade, {}).get(cls, [])

    def grade_gallery(self, school: str, grade: str) -> List[StudentFace]:
        result: List[StudentFace] = []
        for cls in self.schools.get(school, {}).get(grade, {}).values():
            result.extend(cls)
        return result

    def school_gallery(self, school: str) -> List[StudentFace]:
        result: List[StudentFace] = []
        for grades in self.schools.get(school, {}).values():
            for cls in grades.values():
                result.extend(cls)
        return result

    def list_schools(self) -> List[str]:
        return list(self.schools.keys())

    def list_grades(self, school: str) -> List[str]:
        return list(self.schools.get(school, {}).keys())

    def list_classes(self, school: str, grade: str) -> List[str]:
        return list(self.schools.get(school, {}).get(grade, {}).keys())

    # ---- 建库 ----
    def build(self, base_dir: str, recognizer) -> dict:
        """扫描三级目录，为每张底册照片提取人脸特征。返回统计信息。"""
        base = Path(base_dir)
        self.schools = {}
        self._flat = []
        stats = {"schools": 0, "grades": 0, "classes": 0, "students": 0, "skipped": []}

        if not base.exists():
            return stats

        for school_dir in sorted(base.iterdir()):
            if not school_dir.is_dir():
                continue
            stats["schools"] += 1
            for grade_dir in sorted(school_dir.iterdir()):
                if not grade_dir.is_dir():
                    continue
                stats["grades"] += 1
                for class_dir in sorted(grade_dir.iterdir()):
                    if not class_dir.is_dir():
                        continue
                    stats["classes"] += 1
                    for img_file in sorted(class_dir.iterdir()):
                        if img_file.suffix.lower() not in IMAGE_EXTS:
                            continue
                        self._add_photo(
                            img_file, school_dir.name, grade_dir.name, class_dir.name,
                            recognizer, stats,
                        )
        self._flat = self._all_faces()
        self.base_signature = compute_base_signature(base_dir)
        return stats

    def _add_photo(self, img_file, school, grade, cls, recognizer, stats) -> None:
        student_id, name = parse_filename(img_file.name)
        img = imread_unicode(img_file)
        if img is None:
            stats["skipped"].append(f"{img_file.name}（图片读取失败）")
            return
        try:
            faces = recognizer.detect_faces(img)
        except Exception as e:  # 单张失败不中断整体建库
            stats["skipped"].append(f"{img_file.name}（检测异常：{e}）")
            return
        face = recognizer.largest_face(faces)
        if face is None or face.embedding is None:
            stats["skipped"].append(f"{img_file.name}（未检测到人脸）")
            return

        sf = StudentFace(
            student_id=student_id, name=name,
            school_dir=school, grade_dir=grade, class_dir=cls,
            embedding=np.asarray(face.embedding, dtype=np.float32),
        )
        self.schools.setdefault(school, {}).setdefault(grade, {}).setdefault(cls, []).append(sf)
        stats["students"] += 1

    def _all_faces(self) -> List[StudentFace]:
        result: List[StudentFace] = []
        for grades in self.schools.values():
            for classes in grades.values():
                for faces in classes.values():
                    result.extend(faces)
        return result

    # ---- 缓存 ----
    def save_cache(self, path: str) -> None:
        if not self._flat:
            return
        np.savez_compressed(
            path,
            student_ids=np.array([f.student_id for f in self._flat], dtype=object),
            names=np.array([f.name for f in self._flat], dtype=object),
            school_dirs=np.array([f.school_dir for f in self._flat], dtype=object),
            grade_dirs=np.array([f.grade_dir for f in self._flat], dtype=object),
            class_dirs=np.array([f.class_dir for f in self._flat], dtype=object),
            embeddings=np.array([f.embedding for f in self._flat], dtype=np.float32),
            base_signature=np.array([self.base_signature], dtype=object),
        )

    def load_cache(self, path: str, base_dir: str = None) -> bool:
        if not Path(path).exists():
            return False
        data = np.load(path, allow_pickle=True)
        # 底册目录变化（增删照片）时，让缓存自动失效
        if base_dir is not None:
            if "base_signature" not in data:
                return False  # 旧格式缓存（无签名），强制重建
            cached_sig = str(data["base_signature"][0]) if len(data["base_signature"]) > 0 else ""
            if cached_sig != compute_base_signature(base_dir):
                return False
        self.schools = {}
        self._flat = []
        n = len(data["student_ids"])
        for i in range(n):
            sf = StudentFace(
                student_id=str(data["student_ids"][i]),
                name=str(data["names"][i]),
                school_dir=str(data["school_dirs"][i]),
                grade_dir=str(data["grade_dirs"][i]),
                class_dir=str(data["class_dirs"][i]),
                embedding=np.asarray(data["embeddings"][i], dtype=np.float32),
            )
            self.schools.setdefault(sf.school_dir, {}).setdefault(sf.grade_dir, {}) \
                .setdefault(sf.class_dir, []).append(sf)
            self._flat.append(sf)
        return True

    @property
    def total(self) -> int:
        return len(self._flat)
