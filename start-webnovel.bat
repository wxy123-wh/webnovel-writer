@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PROJECT_ROOT=%~1"

if not defined PROJECT_ROOT if exist "%CD%\webnovel-project\.webnovel\state.json" set "PROJECT_ROOT=%CD%\webnovel-project"
if not defined PROJECT_ROOT if exist "%CD%\xiaoshuo\.webnovel\state.json" set "PROJECT_ROOT=%CD%\xiaoshuo"

if defined PROJECT_ROOT if not exist "%PROJECT_ROOT%\.webnovel\state.json" if exist "%CD%\%PROJECT_ROOT%\.webnovel\state.json" set "PROJECT_ROOT=%CD%\%PROJECT_ROOT%"

if not defined PROJECT_ROOT goto :missing_project
if not exist "%PROJECT_ROOT%\.webnovel\state.json" goto :invalid_project

set "PYTHON_CMD="
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD goto :missing_python

echo [webnovel] project root: "%PROJECT_ROOT%"
echo [webnovel] starting dashboard on http://127.0.0.1:8765
call %PYTHON_CMD% -X utf8 "webnovel-writer\scripts\webnovel.py" dashboard --project-root "%PROJECT_ROOT%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [webnovel] dashboard exited with code %EXIT_CODE%
)

pause
exit /b %EXIT_CODE%

:missing_project
echo [webnovel] no novel project detected.
echo.
echo Usage:
echo   %~nx0 [project-root]
echo.
echo Examples:
echo   %~nx0 xiaoshuo
echo   %~nx0 webnovel-project
echo   %~nx0 D:\path\to\your\project
echo.
echo Expected project marker:
echo   ^<project-root^>\.webnovel\state.json
pause
exit /b 1

:invalid_project
echo [webnovel] invalid project root: "%PROJECT_ROOT%"
echo Missing: "%PROJECT_ROOT%\.webnovel\state.json"
pause
exit /b 1

:missing_python
echo [webnovel] Python 3 was not found in PATH.
echo Install Python 3.10+ and retry.
pause
exit /b 1
