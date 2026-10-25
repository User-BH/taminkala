# Tamin Kala Bakhtar - remove the background service and firewall rule (files are kept)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Task = 'TaminKala'
$Server = Join-Path $Root 'server.py'

Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$Server*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-NetFirewallRule -DisplayName 'TaminKala*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Write-Host "  OK  Service and firewall rules removed" -ForegroundColor Green

# give port 80 back to IIS if install.ps1 stopped its default site
$mark = Join-Path $Root 'data\iis-stopped.txt'
if (Test-Path $mark) {
  try {
    Import-Module WebAdministration -ErrorAction Stop
    $name = (Get-Content $mark -Raw).Trim()
    Set-ItemProperty "IIS:\Sites\$name" -Name serverAutoStart -Value $true
    Start-Website -Name $name
    Remove-Item $mark
    Write-Host "  OK  IIS site '$name' started again" -ForegroundColor Green
  } catch { Write-Host "  !!  Could not restart the IIS site: $_" -ForegroundColor Yellow }
}
