@echo off
rem Avvia la chat nel browser con un doppio clic. La logica sta in avvio_chat (python -m avvio_chat).
cd /d "%~dp0"
title Assistente del laboratorio - chat
if not exist ".venv\Scripts\python.exe" (
  echo Manca l'ambiente virtuale .venv. Segui "La prima volta" nel file AVVIO-RAPIDO.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m avvio_chat %*
rem Dopo un errore, qualunque sia il codice, la finestra resta aperta finche' non premi un tasto.
set "CODICE=%errorlevel%"
if not "%CODICE%"=="0" pause
exit /b %CODICE%
