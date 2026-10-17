# -*- coding: utf-8 -*-
"""底册扫描建库：解析「学校/年级/班级」三级目录与「身份证号+姓名」文件名，生成/加载特征缓存。

建库采用增量策略：缓存中已存在且文件未变化的照片直接复用特征，
只对新增/修改过的照片重新提取特征，大幅加速二次建库。
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

# 从班级名中提取年级（如「高二一班」→「高二」、「初三年级」→「初三」）；提取不出则用默认年级
_GRADE_RE = re.compile(r"^(高一|高二|高三|初一|初二|初三|"
                       r"[一二三四五六七八九十零]+年级|中职|高职|中专|小学|初中|高中)")


def _derive_grade_from_class(cls: str) -> str:
    m = _GRADE_RE.match(cls)
    return m.group(1) if m else "默认年级"


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


def _file_sig(p: Path) -> str:
    """单张图片的指纹：大小 + 修改时间。用于判断照片是否变化。"""
    st = p.stat()
    return f"{st.st_size}|{int(st.st_mtime)}"


class Gallery:
    """底册索引：school -> grade -> class -> [StudentFace]。
    内部维护 self._cache: {相对路径: (StudentFace, 文件指纹)}，用于增量建库。"""

    def __init__(self):
        self.schools: Dict[str, Dict[str, Dict[str, List[StudentFace]]]] = {}
        self._flat: List[StudentFace] = []
        self._cache: Dict[str, Tuple[StudentFace, str]] = {}

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

    # ---- 建库（增量） ----
    def build(self, base_dir: str, recognizer) -> dict:
        """扫描三级目录建库。已缓存且文件未变的照片直接复用特征，
        只对新增/变更的照片调用 recognizer 提取特征。返回统计信息。"""
        base = Path(base_dir)
        self.schools = {}
        self._flat = []
        stats = {"schools": 0, "grades": 0, "classes": 0, "students": 0, "skipped": [],
                 "reused": 0, "changed": 0, "removed": 0}

        if not base.exists():
            return stats

        files = sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        total = len(files)
        if total:
            print(f"  底册共 {total} 张照片，正在建库（已缓存的照片直接复用）...", flush=True)

        new_cache: Dict[str, Tuple[StudentFace, str]] = {}
        seen_schools, seen_grades, seen_classes = set(), set(), set()

        for idx, img_file in enumerate(files):
            try:
                relp = img_file.relative_to(base)
            except ValueError:
                continue
            parts = relp.parts
            if len(parts) == 4:
                school, grade, cls, _fname = parts   # 标准：学校/年级/班级/照片
            elif len(parts) == 3:
                # 兼容两级结构：学校/班级/照片（用户常省略年级），
                # 从班级名推断年级（如「高二一班」→「高二」），推断不出则用「默认年级」
                school, cls, _fname = parts
                grade = _derive_grade_from_class(cls)
            else:
                stats["skipped"].append(
                    f"{relp}（目录层级应为 学校/年级/班级/照片 或 学校/班级/照片）")
                continue
            rel = str(relp)
            sig = _file_sig(img_file)

            seen_schools.add(school)
            seen_grades.add((school, grade))
            seen_classes.add((school, grade, cls))

            cached = self._cache.get(rel)
            if cached is not None and cached[1] == sig:
                sf = cached[0]               # 复用已缓存的特征
                stats["reused"] += 1
            else:
                sf = self._extract(img_file, school, grade, cls, recognizer, stats)
                stats["changed"] += 1

            if sf is not None:
                self.schools.setdefault(school, {}).setdefault(grade, {}) \
                    .setdefault(cls, []).append(sf)
                stats["students"] += 1
                new_cache[rel] = (sf, sig)

            if (idx + 1) % 100 == 0:
                print(f"  建库进度：{idx + 1}/{total}（新增/变更 {stats['changed']}，复用 {stats['reused']}）...", flush=True)

        stats["schools"] = len(seen_schools)
        stats["grades"] = len(seen_grades)
        stats["classes"] = len(seen_classes)
        # 旧缓存中存在、但本次已不在底册里的照片数（被删除/移动）
        stats["removed"] = len(self._cache) - len(set(self._cache) & set(new_cache))

        self._cache = new_cache
        self._flat = self._all_faces()
        return stats

    def _extract(self, img_file, school, grade, cls, recognizer, stats) -> Optional[StudentFace]:
        """提取一张照片的人脸特征，成功返回 StudentFace，失败返回 None 并记入 skipped。"""
        student_id, name = parse_filename(img_file.name)
        img = imread_unicode(img_file)
        if img is None:
            stats["skipped"].append(f"{img_file.name}（图片读取失败）")
            return None
        try:
            faces = recognizer.detect_faces(img)
        except Exception as e:  # 单张失败不中断整体建库
            stats["skipped"].append(f"{img_file.name}（检测异常：{e}）")
            return None
        face = recognizer.largest_face(faces)
        if face is None or face.embedding is None:
            stats["skipped"].append(f"{img_file.name}（未检测到人脸）")
            return None

        return StudentFace(
            student_id=student_id, name=name,
            school_dir=school, grade_dir=grade, class_dir=cls,
            embedding=np.asarray(face.embedding, dtype=np.float32),
        )

    def _all_faces(self) -> List[StudentFace]:
        result: List[StudentFace] = []
        for grades in self.schools.values():
            for classes in grades.values():
                for faces in classes.values():
                    result.extend(faces)
        return result

    def _rebuild_index(self) -> None:
        """从 self._cache 重建 schools / _flat 索引（加载缓存后直接可用）。"""
        self.schools = {}
        self._flat = []
        for sf, _sig in self._cache.values():
            self.schools.setdefault(sf.school_dir, {}).setdefault(sf.grade_dir, {}) \
                .setdefault(sf.class_dir, []).append(sf)
            self._flat.append(sf)

    # ---- 缓存 ----
    def save_cache(self, path: str) -> None:
        """把当前底册（含每张照片的相对路径与指纹）写入缓存，供下次增量复用。"""
        if not self._cache:
            # 底册已清空：删除旧缓存，避免下次加载到过期数据
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
            return
        items = sorted(self._cache.items(), key=lambda kv: kv[0])
        rels = [k for k, _ in items]
        sfs = [v[0] for _, v in items]
        sigs = [v[1] for _, v in items]
        np.savez_compressed(
            path,
            student_ids=np.array([f.student_id for f in sfs], dtype=object),
            names=np.array([f.name for f in sfs], dtype=object),
            school_dirs=np.array([f.school_dir for f in sfs], dtype=object),
            grade_dirs=np.array([f.grade_dir for f in sfs], dtype=object),
            class_dirs=np.array([f.class_dir for f in sfs], dtype=object),
            embeddings=np.array([f.embedding for f in sfs], dtype=np.float32),
            source_files=np.array(rels, dtype=object),
            source_sigs=np.array(sigs, dtype=object),
        )

    def load_cache(self, path: str, base_dir: str = None) -> bool:
        """加载缓存到 self._cache 并重建索引，供 build() 增量复用。
        返回 True 表示成功加载（含增量信息）；旧格式或损坏返回 False。"""
        if not Path(path).exists():
            return False
        try:
            data = np.load(path, allow_pickle=True)
        except Exception:
            return False
        if "source_files" not in data:
            return False  # 旧格式缓存（无增量信息），需全量重建一次
        self._cache = {}
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
            self._cache[str(data["source_files"][i])] = (sf, str(data["source_sigs"][i]))
        self._rebuild_index()
        return True

    @property
    def total(self) -> int:
        return len(self._flat)
