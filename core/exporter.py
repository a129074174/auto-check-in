# -*- coding: utf-8 -*-
"""签到结果导出：生成 .xlsx（含班级/姓名/时间/结果）。"""
import os
from dataclasses import dataclass
from datetime import datetime

from .config import DATA_DIR


@dataclass
class CheckinRecord:
    """一条签到记录。"""
    name: str                # 姓名
    class_name: str          # 班级
    time_str: str            # 签到时间（HH:MM:SS）
    result: str              # 结果：成功 / 失败 / 重复
    similarity: float = 0.0  # 相似度
    student_id: str = ""     # 身份证号
    school: str = ""         # 学校
    grade: str = ""          # 年级
    level: str = ""          # 匹配级别：class / grade


_HEADERS = ["序号", "姓名", "班级", "签到时间", "结果", "相似度", "身份证号", "学校", "年级", "匹配级别"]
_RESULT_COLORS = {"成功": "16A34A", "失败": "DC2626", "重复": "F59E0B"}


def make_export_path(scope_name: str = "") -> str:
    """生成带时间戳的导出文件路径（保存到 data 目录，gitignore 排除）。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"签到结果_{scope_name}_{ts}.xlsx" if scope_name else f"签到结果_{ts}.xlsx"
    return os.path.join(DATA_DIR, name)


def export_xlsx(records, filepath: str = None) -> str:
    """把签到记录列表导出为 Excel，返回文件路径。"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError as e:
        raise RuntimeError("缺少 openpyxl 依赖，请先双击「安装环境.bat」安装。") from e

    if filepath is None:
        filepath = make_export_path()

    wb = Workbook()
    ws = wb.active
    ws.title = "签到结果"

    # 表头
    head_fill = PatternFill("solid", fgColor="2563EB")
    head_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(_HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = head_fill
        cell.font = head_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 数据行（结果列按状态着色）
    for i, r in enumerate(records, 2):
        row = [
            i - 1,
            r.name,
            r.class_name,
            r.time_str,
            r.result,
            round(r.similarity, 3),
            r.student_id,
            r.school,
            r.grade,
            r.level,
        ]
        for col, v in enumerate(row, 1):
            cell = ws.cell(row=i, column=col, value=v)
            if r.result in _RESULT_COLORS and col == 5:
                cell.font = Font(color=_RESULT_COLORS[r.result], bold=True)

    # 列宽 + 冻结表头
    widths = [6, 12, 16, 12, 10, 10, 24, 16, 12, 10]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + col)].width = w
    ws.freeze_panes = "A2"

    wb.save(filepath)
    return filepath
