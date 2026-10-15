@echo off
chcp 65001 >nul
echo ============================================
echo   笑脸报到 - 底册扫描测试（第2步验收）
echo ============================================
echo.
echo 请先把测试照片放到 base_photos\学校\年级\班级\ 目录下。
echo.
python test_gallery.py
echo.
pause
