# Tamin Kala Bakhtar - one-click update from GitHub Releases (run through update.bat)
# 1) With data\github-token.txt (read-only token): downloads the latest release by itself.
# 2) Without it: uses the newest TaminKala-windows*.zip in Downloads (downloaded from the Releases page),
#    or opens the Releases page in the browser.
# Then stops the service, replaces the program files (data\ and logs\ are kept) and runs install.ps1.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Repo   = 'User-BH/taminkala'
$Asset  = 'TaminKala-windows.zip'
$Root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Server = Join-Path $Root 'server.py'
$TokenF = Join-Path $Root 'data\github-token.txt'
$Work   = Join-Path $env:TEMP 'TaminKala-update'

function Say($t)  { Write-Host "  > $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  OK  $t" -ForegroundColor Green }
function Fail($t) { Write-Host "  XX  $t" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Tamin Kala Bakhtar - update" -ForegroundColor White
$current = if (Test-Path (Join-Path $Root 'VERSION.txt')) { (Get-Content (Join-Path $Root 'VERSION.txt') -Raw).Trim() } else { '' }
Write-Host "  Installed version: $current"
Write-Host ""
Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Work | Out-Null
$zip = Join-Path $Work $Asset

# ---- 1) get the package
$token = if (Test-Path $TokenF) { (Get-Content $TokenF -Raw).Trim() } else { '' }
if ($token) {
  Say "Checking the latest version on GitHub"
  $h = @{ Authorization = "Bearer $token"; 'X-GitHub-Api-Version' = '2022-11-28' }
  try { $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $h -UseBasicParsing }
  catch { Fail "GitHub did not answer ($($_.Exception.Message)). Check the internet connection or the token in data\github-token.txt." }
  $a = $rel.assets | Where-Object { $_.name -eq $Asset } | Select-Object -First 1
  if (-not $a) { Fail "Release $($rel.tag_name) has no $Asset." }
  if ($current -and $rel.body -match "version: $([regex]::Escape($current))\b") { Ok "Already up to date ($($rel.tag_name))."; exit 0 }
  Say "Downloading $($rel.tag_name) ($([math]::Round($a.size / 1MB)) MB)"
  $h.Accept = 'application/octet-stream'
  Invoke-WebRequest -Uri $a.url -Headers $h -OutFile $zip -UseBasicParsing
} else {
  $dl = Join-Path $env:USERPROFILE 'Downloads'
  $found = Get-ChildItem -Path $dl -Filter 'TaminKala-windows*.zip' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $found) {
    Start-Process "https://github.com/$Repo/releases/latest"
    Write-Host "  The Releases page is now open in the browser." -ForegroundColor Yellow
    Write-Host "  Download $Asset (it goes to the Downloads folder), then run update.bat again." -ForegroundColor Yellow
    exit 0
  }
  Say "Using $($found.FullName)  ($($found.LastWriteTime))"
  Copy-Item $found.FullName $zip
}

# ---- 2) unpack and check
Say "Unpacking"
Expand-Archive -Path $zip -DestinationPath $Work -Force
$new = Join-Path $Work 'TaminKala'
if (-not (Test-Path (Join-Path $new 'server.py'))) { Fail "The zip file is not a TaminKala package." }
$newVer = (Get-Content (Join-Path $new 'VERSION.txt') -Raw).Trim()
if ($newVer -eq $current) {
  Ok "Already up to date ($newVer)."
  if (-not $token) { Write-Host "  For a newer version, download $Asset again from https://github.com/$Repo/releases/latest" -ForegroundColor Yellow }
  exit 0
}

# ---- 3) stop the service so its files can be replaced
Say "Stopping the service"
Stop-ScheduledTask -TaskName 'TaminKala' -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$Server*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2

# ---- 4) replace program files (data\ and logs\ stay as they are)
Say "Replacing files: $current -> $newVer"
robocopy $new $Root /E /XD (Join-Path $new 'data') (Join-Path $new 'logs') /R:3 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "Copying files failed (robocopy code $LASTEXITCODE). Run update.bat again." }
Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
Ok "Files updated to $newVer"

# ---- 5) the usual install step (service, firewall, health check)
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'tools\install.ps1')
