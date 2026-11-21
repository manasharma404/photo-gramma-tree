# Temporary public link for the ArgosX security scan (the product itself is offline by design).
#
#   powershell -ExecutionPolicy Bypass -File scripts\argosx_tunnel.ps1
#
# Needs: the app running (uv run python -m api.main, sign-in ON) and cloudflared in ..\tools\ (outside the repo;
# Cloudflare-signed, checked 21 Nov). Prints a https://...trycloudflare.com link to paste into ArgosX, keeps the
# tunnel open until you press Enter, then closes it, so the laptop is reachable from the internet only during
# the scan. Anyone with the link reaches the sign-in page and nothing else without a code.
$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "..\..\tools\cloudflared.exe"
if (-not (Test-Path $exe)) { throw "cloudflared.exe not found at $exe" }
if ((Get-AuthenticodeSignature $exe).Status -ne "Valid") { throw "cloudflared.exe is not validly signed; do not run it" }
try { Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 3 | Out-Null } catch { throw "The app is not running on port 8000. Start it first: uv run python -m api.main" }
$log = Join-Path $env:TEMP "typhon_tunnel.log"
if (Test-Path $log) { Remove-Item $log -Force -Confirm:$false }
$p = Start-Process -FilePath $exe -ArgumentList @("tunnel", "--no-autoupdate", "--url", "http://localhost:8000") `
     -RedirectStandardError $log -PassThru -WindowStyle Hidden
$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
  Start-Sleep -Seconds 1
  $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($m) { $url = $m.Matches[0].Value }
}
if (-not $url) { Stop-Process -Id $p.Id -Force; throw "No link after 60 s (venue network?). Log: $log" }
Write-Host ""
Write-Host "Link for ArgosX:  $url" -ForegroundColor Green
Write-Host "Tunnel is OPEN. Run the scan, download the report, then press Enter here to close it."
Read-Host | Out-Null
Stop-Process -Id $p.Id -Force
Write-Host "Tunnel closed. The link no longer reaches this laptop."
