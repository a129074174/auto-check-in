@echo off
chcp 65001 >nul
echo ============================================
echo   人脸签到系统 - 上传代码到 GitHub
echo ============================================
echo.
echo [1/2] 提交本地改动...
git add -A
git commit -m "更新代码" 2>nul
echo.
echo [2/2] 推送到远程仓库...
git push -u origin main
echo.
if errorlevel 1 (
    echo [失败] 推送失败。请检查：
    echo   1. 网络是否正常；
    echo   2. 是否已登录 GitHub（首次推送需要输入账号和 Token/密码）。
) else (
    echo [成功] 代码已推送到 GitHub！
)
echo.
pause
