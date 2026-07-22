@echo off
setlocal
cd /d "%~dp0"

call :find_python
if not defined PYTHON_EXE (
    echo ERROR: Python with build dependencies was not found.
    echo Run: python -m pip install -r requirements-dev.txt
    endlocal & exit /b 1
)

echo Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" build.py
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
"%~1" -c "import PyInstaller, PyQt5, openpyxl, google.protobuf" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=%~1"
goto :eof
