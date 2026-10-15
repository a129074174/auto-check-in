@echo off
chcp 65001 >nul
echo ============================================
echo   笑脸报到 - 打包成免安装文件夹
echo ============================================
echo.

echo [1/3] 清理隐私数据...
if exist data (
    echo   正在清空 data 目录（特征缓存、签到结果）...
    rmdir /s /q data
)
echo   提示：base_photos 底册照片不会被打包，请确认其中无真实隐私残留。

echo [2/3] 确认打包工具 PyInstaller...
python -m pip install pyinstaller -q

echo [3/3] 开始打包（首次较慢，约几分钟，请耐心等待）...
python -m PyInstaller --clean --noconfirm checkin.spec

echo.
if exist "dist\笑脸报到\笑脸报到.exe" (
    echo [成功] 打包完成！
    echo 产物位置：dist\笑脸报到\
    echo 把整个文件夹拷贝到别的电脑，双击里面的「笑脸报到.exe」即可使用。
) else (
    echo [失败] 打包未成功，请把上面的错误信息发给开发者。
)
echo.
pause
