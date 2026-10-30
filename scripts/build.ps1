# Builds dist\Vapor\Vapor.exe (+ vaporctl.exe) and dist\Vapor-win64.zip.   Run from anywhere:  .\scripts\build.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)      # repo root (this script lives in scripts\)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE) { throw "pip failed" }

Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --clean vapor.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }

# vaporctl.exe goes next to Vapor.exe (that folder is what Vapor puts on your PATH)
if (Test-Path dist\vaporctl.exe) { Move-Item dist\vaporctl.exe dist\Vapor\vaporctl.exe -Force }
# optional default user files (ringtone, profile picture ...); the installer never overwrites existing ones
if (Test-Path files) { Copy-Item files dist\Vapor\files -Recurse -Force }

# .NET zip (Compress-Archive in Windows PowerShell 5.1 writes backslash paths, which the installer cannot unpack)
Add-Type -AssemblyName System.IO.Compression.FileSystem
Remove-Item dist\Vapor-win64.zip -ErrorAction SilentlyContinue
[IO.Compression.ZipFile]::CreateFromDirectory((Resolve-Path dist\Vapor).Path, (Join-Path (Resolve-Path dist).Path 'Vapor-win64.zip'), [IO.Compression.CompressionLevel]::Optimal, $false)
Write-Host "`nDone:  dist\Vapor\Vapor.exe   and   dist\Vapor-win64.zip" -ForegroundColor Green
