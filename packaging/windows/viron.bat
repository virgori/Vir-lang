@echo off
REM ═══════════════════════════════════════════════════════════════
REM Viron — Windows CLI wrapper (package manager / OS shell)
REM ═══════════════════════════════════════════════════════════════
setlocal

python -m src.viron.cli %*
