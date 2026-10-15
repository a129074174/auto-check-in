@echo off
chcp 65001 >nul
echo ============================================
echo   笑脸报到 - 摄像头识别测试（第3步验收）
echo ============================================
echo.
echo 默认使用本地摄像头 + 第一个学校/年级（年级签到模式）。
echo 如需手机摄像头，请在命令行手动运行：
echo     python test_camera.py "http://手机IP:8080/video"
echo.
python test_camera.py
echo.
pause
