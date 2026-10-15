@echo off
chcp 65001 >nul
echo ============================================
echo   笑脸报到 - 安装依赖
echo ============================================
echo.
echo 正在安装依赖，可能需要几分钟，请耐心等待...
echo 首次会联网下载人脸模型（约300MB），请保持网络畅通。
echo.
python -m pip install -r requirements.txt
echo.
if errorlevel 1 (
    echo [失败] 安装出错，请检查网络后重试。
) else (
    echo [成功] 依赖安装完成！
)
echo.
pause
