@echo off
chcp 65001 >nul
echo ============================================
echo   笑脸报到 - 上传代码到 GitHub
echo ============================================
echo.
echo [1/2] 提交本地改动...
git add -A
git commit -m "更新代码" 2>nul
echo.
echo [2/2] 推送到远程仓库...
git push -u origin main
if errorlevel 1 goto :fail
echo.
echo [成功] 代码已推送到 GitHub！
goto :end

:fail
echo.
echo [失败] 推送失败。请检查：
echo   1. 网络或代理是否正常，可稍后重试；
echo   2. 是否已登录 GitHub（首次推送需要输入账号和 Token/密码）。

:end
echo.
pause
