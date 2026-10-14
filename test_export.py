# -*- coding: utf-8 -*-
"""第 4 步验收脚本：生成示例签到记录并导出 Excel（示例数据均为合成占位符，非真实信息）。"""
from core.exporter import CheckinRecord, export_xlsx, make_export_path


def main() -> None:
    records = [
        CheckinRecord(name="张三", class_name="(1)班", time_str="08:00:15",
                      result="成功", similarity=0.68, student_id="11010120000101001X",
                      school="示例学校", grade="2024级", level="class"),
        CheckinRecord(name="李四", class_name="(1)班", time_str="08:01:02",
                      result="成功", similarity=0.71, student_id="11010120000101002X",
                      school="示例学校", grade="2024级", level="class"),
        CheckinRecord(name="张三", class_name="(1)班", time_str="08:02:30",
                      result="重复", similarity=0.66, student_id="11010120000101001X",
                      school="示例学校", grade="2024级", level="class"),
        CheckinRecord(name="", class_name="", time_str="08:03:10",
                      result="失败", similarity=0.21),
    ]
    path = make_export_path("示例学校_2024级_(1)班")
    export_xlsx(records, path)
    print(f"已导出：{path}")
    print("请用 Excel 打开检查：字段是否齐全、成功/重复/失败的颜色是否正确。")


if __name__ == "__main__":
    main()
