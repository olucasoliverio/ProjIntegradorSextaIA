@echo off
echo Fechando Chrome existente...
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

echo Abrindo Chrome com remote debugging na porta 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --no-first-run --no-default-browser-check

timeout /t 3 /nobreak >nul
echo Chrome aberto! Agora acesse o site manualmente no Chrome.
echo.
echo Cole essa URL no Chrome:
echo https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza?q=^&types=28^&types=4^&types=5^&types=35^&types=228^&types=229^&types=230
echo.
echo Depois de passar pelo Cloudflare, rode: node inspect-cdp.js
pause
