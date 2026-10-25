# Tamin Kala Bakhtar - Windows installer (run through install.bat, which asks for admin rights)
# Designed and developed by Rahvar Peyvand Dadeh
# Safe to run again: it is also the "update" step after extracting a new version over this folder.
$ErrorActionPreference = 'Stop'
$Root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Task   = 'TaminKala'
$Rule   = 'TaminKala'
$PyW    = Join-Path $Root 'python\pythonw.exe'
$Server = Join-Path $Root 'server.py'
$Data   = Join-Path $Root 'data'
$Config = Join-Path $Data 'config.json'

function Say($t)  { Write-Host "  > $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  !!  $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "  XX  $t" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Tamin Kala Bakhtar - install / update" -ForegroundColor White
Write-Host "  Folder: $Root"
Write-Host ""

# 1) folder path must be plain ASCII (Python and Task Scheduler dislike other characters)
if ($Root -match '[^\x00-\x7F]') { Fail "Move this folder to a path with English letters only, for example C:\TaminKala, then run install.bat again." }
if (-not (Test-Path $PyW))    { Fail "python\pythonw.exe not found. Extract the whole zip file first." }
if (-not (Test-Path $Server)) { Fail "server.py not found. Extract the whole zip file first." }

# 2) files from a downloaded zip are blocked by Windows until unblocked
Say "Unblocking files"
Get-ChildItem -Path $Root -Recurse -File | Unblock-File -ErrorAction SilentlyContinue

# 3) settings
if (-not (Test-Path $Data)) { New-Item -ItemType Directory -Path $Data | Out-Null }
if (-not (Test-Path $Config)) {
  '{ "site_port": 80, "pichak_port": 8081, "bime_port": 8082, "pichak_ocr": true, "threads": 8 }' | Set-Content -Path $Config -Encoding ASCII
  Ok "Created data\config.json"
}
$cfg = Get-Content $Config -Raw | ConvertFrom-Json

# stop a running copy first so its ports are free
if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) {
  Say "Stopping the running service"
  Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$Server*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

function Test-PortFree([int]$p) {
  try { $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $p); $l.Start(); $l.Stop(); return $true } catch { return $false }
}

# 4) site port: IIS "Default Web Site" usually holds port 80 with its welcome page
$site = [int]$cfg.site_port
if (-not (Test-PortFree $site)) {
  $stopped = $false
  try {
    Import-Module WebAdministration -ErrorAction Stop
    foreach ($w in Get-Website) {
      $usesPort = $false
      foreach ($b in $w.bindings.Collection) { if ($b.bindingInformation -match (":" + $site + ":")) { $usesPort = $true } }
      if ($usesPort -and $w.State -eq 'Started') {
        if ($w.Name -eq 'Default Web Site') {
          Say "Port $site is used by the IIS 'Default Web Site' (Windows welcome page). Stopping only that site."
          Stop-Website -Name $w.Name
          Set-ItemProperty "IIS:\Sites\$($w.Name)" -Name serverAutoStart -Value $false
          Set-Content -Path (Join-Path $Data 'iis-stopped.txt') -Value $w.Name -Encoding ASCII
          $stopped = $true
        } else {
          Warn "Port $site is used by the IIS site '$($w.Name)'. It was NOT touched."
        }
      }
    }
  } catch { }
  if ($stopped) { Start-Sleep -Seconds 2 }
  if (-not (Test-PortFree $site)) {
    $alt = @(8080, 8000, 8888) | Where-Object { ($_ -ne [int]$cfg.pichak_port) -and ($_ -ne [int]$cfg.bime_port) -and (Test-PortFree $_) } | Select-Object -First 1
    if (-not $alt) { Fail "Port $site is busy and no free alternative was found." }
    Warn "Port $site is busy (another program). The website will use port $alt instead."
    $cfg.site_port = $alt; $site = $alt
    ($cfg | ConvertTo-Json) | Set-Content -Path $Config -Encoding ASCII
  }
}
foreach ($p in @([int]$cfg.pichak_port, [int]$cfg.bime_port)) {
  if (-not (Test-PortFree $p)) { Fail "Port $p is used by another program. Change it in data\config.json and run install.bat again." }
}
Ok "Ports: site $site, cheque inquiry $($cfg.pichak_port), insurance $($cfg.bime_port)"

# 5) start with Windows (no login needed) and restart automatically on failure
Say "Registering the background service (Task Scheduler)"
$action    = New-ScheduledTaskAction -Execute $PyW -Argument ('"' + $Server + '"') -WorkingDirectory $Root
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $Task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Tamin Kala Bakhtar website, cheque inquiry and insurance systems' -Force | Out-Null
Ok "Service registered: starts with Windows"

# 6) firewall
Say "Opening firewall ports"
Get-NetFirewallRule -DisplayName $Rule -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $Rule -Direction Inbound -Protocol TCP -LocalPort @($site, [int]$cfg.pichak_port, [int]$cfg.bime_port) -Action Allow | Out-Null
Ok "Firewall open for $site, $($cfg.pichak_port), $($cfg.bime_port)"

# 7) start and check
Say "Starting"
Start-ScheduledTask -TaskName $Task
function Check([string]$name, [string]$url) {
  for ($i = 0; $i -lt 30; $i++) {
    try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -eq 200) { Ok "$name is running  ($url)"; return $true } } catch { }
    Start-Sleep -Seconds 1
  }
  Warn "$name did not answer at $url - see logs\server.log"; return $false
}
$a = Check 'Website'          "http://localhost:$site/"
$b = Check 'Cheque inquiry'   "http://localhost:$($cfg.pichak_port)/api/health"
$c = Check 'Insurance system' "http://localhost:$($cfg.bime_port)/"

Write-Host ""
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress
foreach ($ip in $ips) {
  $sfx = if ($site -eq 80) { '' } else { ":$site" }
  Write-Host "  Website:          http://$ip$sfx/" -ForegroundColor White
  Write-Host "  Cheque inquiry:   http://${ip}:$($cfg.pichak_port)/" -ForegroundColor White
  Write-Host "  Insurance system: http://${ip}:$($cfg.bime_port)/" -ForegroundColor White
}
Write-Host ""
if ($a -and $b -and $c) { Ok "Done." } else { Warn "Installed, but some parts did not answer. Run status.bat or send logs\server.log for support." }
Start-Process "http://localhost:$site/"
