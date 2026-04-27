$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$args = @("--remote-debugging-port=9222", "--no-first-run", "--no-default-browser-check")
& $chromePath @args
