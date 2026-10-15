# -*- coding: utf-8 -*-
"""人脸匹配：先班级→再年级→失败 的分级匹配，以及会话去重。"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .gallery import StudentFace


@dataclass
class MatchResult:
    matched: bool
    student: Optional[StudentFace]
    level: str              # "class" | "grade" | "none"
    similarity: float


def _best_match(embedding, faces: List[StudentFace]) -> Tuple[Optional[StudentFace], float]:
    """在候选列表中找余弦相似度最高的一个，返回 (学生, 相似度)。"""
    if not faces:
        return None, 0.0
    e = np.asarray(embedding, dtype=np.float32)
    embs = np.array([f.embedding for f in faces], dtype=np.float32)
    e_norm = float(np.linalg.norm(e))
    emb_norm = np.linalg.norm(embs, axis=1)
    emb_norm = np.where(emb_norm == 0, 1.0, emb_norm)
    if e_norm == 0:
        return None, 0.0
    sims = np.dot(embs, e) / (e_norm * emb_norm)
    idx = int(np.argmax(sims))
    return faces[idx], float(sims[idx])


def match(embedding, gallery, school: str, grade: str, cls: str, scope: str, threshold: float) -> MatchResult:
    """分级匹配。
    scope == "class"：先在该班匹配，达不到阈值则回退整个年级；
    scope == "grade"：直接在整个年级匹配。
    均达不到阈值则返回 matched=False。
    """
    if scope == "class":
        best, sim = _best_match(embedding, gallery.class_gallery(school, grade, cls))
        if best is not None and sim >= threshold:
            return MatchResult(True, best, "class", sim)
        best, sim = _best_match(embedding, gallery.grade_gallery(school, grade))
        if best is not None and sim >= threshold:
            return MatchResult(True, best, "grade", sim)
        return MatchResult(False, best, "none", sim)

    if scope == "grade":
        best, sim = _best_match(embedding, gallery.grade_gallery(school, grade))
        if best is not None and sim >= threshold:
            return MatchResult(True, best, "grade", sim)
        return MatchResult(False, best, "none", sim)

    # 学校签到（整个学校所有年级）
    best, sim = _best_match(embedding, gallery.school_gallery(school))
    if best is not None and sim >= threshold:
        return MatchResult(True, best, "school", sim)
    return MatchResult(False, best, "none", sim)


class DedupTracker:
    """会话去重：同一学生在本次签到批次内只记一次成功，其余一律按重复处理。
    点「开始签到」开启新批次时调用 reset() 重新计数。"""

    def __init__(self, cooldown: float = 10.0):
        # cooldown 保留以兼容旧调用；现仅用作「重复/失败记录」的节流间隔（见 app.py）
        self.cooldown = cooldown
        self._recorded: set = set()

    @staticmethod
    def _key(student: StudentFace) -> str:
        if student.student_id:
            return f"id:{student.student_id}"
        return f"n:{student.school_dir}/{student.grade_dir}/{student.class_dir}/{student.name}"

    def should_record(self, student: StudentFace) -> bool:
        """返回 True 表示本批次首次见到该学生（记成功）；之后一律返回 False（记重复）。"""
        key = self._key(student)
        if key in self._recorded:
            return False
        self._recorded.add(key)
        return True

    def reset(self) -> None:
        """开始新的签到批次：清空已记录名单，同一学生可再次记一次成功。"""
        self._recorded.clear()
