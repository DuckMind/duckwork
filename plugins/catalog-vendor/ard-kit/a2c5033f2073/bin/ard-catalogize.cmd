@echo off
rem Windows twin of bin/ard-catalogize: cmd.exe cannot exec a #!/bin/sh script,
rem and Windows Python ships as python/py, never python3. The interpreter is
rem probed, not assumed - `where python` alone also matches the Microsoft
rem Store stub, which resolves but refuses to run anything.
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PY="
for %%P in (python py python3) do (
    if not defined PY %%P -c "import sys" >nul 2>nul && set "PY=%%P"
)
if not defined PY (
    echo ard-kit: no usable Python interpreter on PATH ^(tried python, py, python3^) 1>&2
    exit /b 127
)
if defined PYTHONPATH (set "PYTHONPATH=%ROOT%;%PYTHONPATH%") else (set "PYTHONPATH=%ROOT%")
"%PY%" -m ard_kit.catalogize %*
exit /b %ERRORLEVEL%
