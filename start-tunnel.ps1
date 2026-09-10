# Public HTTPS for the local UI at http://127.0.0.1:8080
# Leave this window open. Ctrl+C stops the tunnel.

$ErrorActionPreference = "Stop"
$port = 8080

try {
    Invoke-WebRequest -Uri "http://127.0.0.1:$port" -UseBasicParsing -TimeoutSec 5 | Out-Null
} catch {
    Write-Host "UI is not running at http://127.0.0.1:$port"
    Write-Host "Start the stack first:"
    Write-Host "  docker compose --env-file .env -f infra/compose/compose.yaml up -d"
    exit 1
}

Write-Host "Forwarding http://127.0.0.1:$port"
Write-Host "Copy the https://….lhr.life URL from the output below."
Write-Host "Ctrl+C to stop."
Write-Host ""

ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R "80:127.0.0.1:$port" nokey@localhost.run
