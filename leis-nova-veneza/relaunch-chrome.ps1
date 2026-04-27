Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222", "--no-first-run", "--no-default-browser-check"
Start-Sleep -Seconds 5
$result = netstat -ano | Select-String ":9222"
if ($result) {
    Write-Host "SUCESSO: Porta 9222 ativa!"
    Write-Host $result
} else {
    Write-Host "FALHA: Porta 9222 nao encontrada"
}
