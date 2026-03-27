@echo off
setlocal
set OPENAI_API_KEY=sk-db4420e5de254a1467cc5cfb1a845e13
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:OPENAI_API_KEY='%OPENAI_API_KEY%'; & 'd:\code\webnovel-writer\running\sisyphus-dispatcher.ps1' -RepoRoot 'd:\code\webnovel-writer' -MaxDispatches 16 -MaxParallel 2 -ApiBaseUrl 'https://api.asxs.top/v1' -ApiKey $env:OPENAI_API_KEY"
endlocal
