# Tamin Kala Bakhtar - quick health check
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$cfg = Get-Content (Join-Path $Root 'data\config.json') -Raw | ConvertFrom-Json
$t = Get-ScheduledTask -TaskName 'TaminKala' -ErrorAction SilentlyContinue
if ($t) { Write-Host "  Service: $($t.State)" } else { Write-Host "  Service: not installed (run install.bat)" -ForegroundColor Yellow }
foreach ($x in @(@('Website', "http://localhost:$($cfg.site_port)/"), @('Cheque inquiry', "http://localhost:$($cfg.pichak_port)/api/health"), @('Insurance system', "http://localhost:$($cfg.bime_port)/"))) {
  try { $r = Invoke-WebRequest -Uri $x[1] -UseBasicParsing -TimeoutSec 8; Write-Host ("  OK  {0,-17} {1}" -f $x[0], $x[1]) -ForegroundColor Green }
  catch { Write-Host ("  XX  {0,-17} {1}" -f $x[0], $x[1]) -ForegroundColor Red }
}
Write-Host ""
Write-Host "  Last log lines (logs\server.log):"
Get-Content (Join-Path $Root 'logs\server.log') -Tail 15 -ErrorAction SilentlyContinue
