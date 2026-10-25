# Tamin Kala Bakhtar - one-click update from GitHub (run through update.bat)
# The package lives on the repository's "release" branch: TaminKala-windows.zip + VERSION.txt
# 1) With data\github-token.txt (read-only token): downloads the latest package by itself.
# 2) Without it: uses the newest TaminKala-windows*.zip in Downloads,
#    or starts that download in the browser (the browser must be signed in to GitHub).
# Then stops the service, replaces the program files (data\ and logs\ are kept) and runs install.ps1.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Repo   = 'User-BH/taminkala'
$Asset  = 'TaminKala-windows.zip'
$Branch = 'release'
$Url    = "https://github.com/$Repo/raw/refs/heads/$Branch/$Asset"
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
  $h = @{ Authorization = "Bearer $token"; 'X-GitHub-Api-Version' = '2022-11-28'; Accept = 'application/vnd.github.raw' }
  $api = "https://api.github.com/repos/$Repo/contents"
  Say "Checking the latest version on GitHub"
  try { $latest = ([string](Invoke-RestMethod -Uri "$api/VERSION.txt?ref=$Branch" -Headers $h -UseBasicParsing)).Trim() }
  catch { Fail "GitHub did not answer ($($_.Exception.Message)). Check the internet connection or the token in data\github-token.txt." }
  if ($latest -eq $current) { Ok "Already up to date ($current)."; exit 0 }
  Say "Downloading version $latest"
  Invoke-WebRequest -Uri "$api/$Asset`?ref=$Branch" -Headers $h -OutFile $zip -UseBasicParsing
} else {
  $dl = Join-Path $env:USERPROFILE 'Downloads'
  $found = Get-ChildItem -Path $dl -Filter 'TaminKala-windows*.zip' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $found) {
    Start-Process $Url
    Write-Host "  The download has started in the browser (sign in to GitHub there if asked)." -ForegroundColor Yellow
    Write-Host "  When $Asset is in the Downloads folder, run update.bat again." -ForegroundColor Yellow
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
  if (-not $token) {   # the zip in Downloads is the one already installed: fetch the newest
    Start-Process $Url
    Write-Host "  Downloading the newest package in the browser; run update.bat again when it is in Downloads." -ForegroundColor Yellow
  }
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
