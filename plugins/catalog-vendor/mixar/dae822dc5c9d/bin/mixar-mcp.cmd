@echo off
rem Start the MCP launcher the Mixar desktop app installs for the current user.
rem Windows counterpart of bin/mixar-mcp: Duckwork runs ./bin/mixar-mcp, which
rem the MCP SDK resolves to this file through PATHEXT. MIXAR_MCP_LAUNCHER
rem overrides the path (a development or QA build). No parenthesised blocks:
rem a path such as "Program Files (x86)" would end one early.
setlocal
set "LAUNCHER=%MIXAR_MCP_LAUNCHER%"
if not "%LAUNCHER%"=="" goto check
if "%USERPROFILE%"=="" goto nohome
set "LAUNCHER=%USERPROFILE%\.mixar\connector\mixar-mcp.cmd"

:check
if not exist "%LAUNCHER%" goto missing
call "%LAUNCHER%" %*
exit /b %ERRORLEVEL%

:nohome
>&2 echo mixar-mcp: USERPROFILE is not set, so Mixar's launcher cannot be found.
exit /b 1

:missing
>&2 echo mixar-mcp: Mixar's MCP launcher was not found at %LAUNCHER%.
>&2 echo Install Mixar from https://www.mixar.app, open it, sign in, and turn on
>&2 echo profile menu ^> Connect MCP. Then reload MCP in Duckwork (/reload-mcp).
exit /b 1
