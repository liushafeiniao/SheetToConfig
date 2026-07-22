@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0dist\SheetToConfig.exe" (
    start "" "%~dp0dist\SheetToConfig.exe"
    endlocal & exit /b 0
)

call :find_python
if not defined PYTHON_EXE (
    echo ERROR: dist\SheetToConfig.exe is missing and Python was not found.
    echo Run: python -m pip install -r requirements.txt
    endlocal & exit /b 1
)

for %%I in ("%PYTHON_EXE%") do set "PYTHONW_EXE=%%~dpIpythonw.exe"
if not exist "%PYTHONW_EXE%" set "PYTHONW_EXE=%PYTHON_EXE%"
start "" /D "%~dp0" "%PYTHONW_EXE%" "%~dp0SheetToConfig.py"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%

:find_python
set "PYTHON_EXE="
for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%~fI"
if defined PYTHON_EXE goto :eof
for /f "delims=" %%I in ('where python 2^>nul') do call :try_python "%%~fI"
goto :eof

:try_python
if defined PYTHON_EXE goto :eof
"%~1" -c "import PyQt5, openpyxl, google.protobuf" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=%~1"
goto :eof
