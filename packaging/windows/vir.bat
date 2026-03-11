@echo off
REM ═══════════════════════════════════════════════════════════════
REM Vir Language — Windows CLI wrapper
REM ═══════════════════════════════════════════════════════════════
setlocal

if defined VIR_HOME (
    set "VIR_PYTHON=%VIR_HOME%\python"
) else (
    set "VIR_PYTHON=%~dp0..\python"
)

python -m src.runtime.lifecycle %*
