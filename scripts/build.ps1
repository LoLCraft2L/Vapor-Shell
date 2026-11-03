# Builds dist\Vapor\Vapor.exe (+ vaporctl.exe) and dist\Vapor-win64.zip, plus dist\Harmony-win64.zip and dist\Synapse-win64.zip.   Run from anywhere:  .\scripts\build.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)      # repo root (this script lives in scripts\)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE) { throw "pip failed" }

# the version comes from the git tag:  git tag v0.1.4   (CI: the pushed tag).  It is stamped into vaporctl.py (VERSION = "...") before building.
if ($env:GITHUB_REF_TYPE -eq 'tag') { $tag = $env:GITHUB_REF_NAME }
else {
    $ea = $ErrorActionPreference; $ErrorActionPreference = 'Continue'      # PowerShell 5.1 turns git's stderr into errors otherwise
    $tag = (git describe --tags --abbrev=0 2>$null | Select-Object -First 1)
    $ErrorActionPreference = $ea
}
if (-not $tag) { throw "no git tag found - create one first, e.g.  git tag v0.1.4" }
$ver = ([string]$tag).Trim().TrimStart('v', 'V')
$vc = Get-ChildItem -Recurse -Filter vaporctl.py | Where-Object { $_.FullName -notmatch '\\(build|dist)\\' } | Select-Object -First 1
if ($vc) {
    $txt = [IO.File]::ReadAllText($vc.FullName)
    $new = [regex]::Replace($txt, '(?m)^VERSION = "[^"]*"', "VERSION = `"$ver`"")
    if ($new -ne $txt) { [IO.File]::WriteAllText($vc.FullName, $new, (New-Object Text.UTF8Encoding($false))) }
    Write-Host "Version $ver stamped into $($vc.Name)"
}

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

# optional packages (the installer's "Would you also like to install these optional packages?" question): each one becomes
# dist\<Name>-win64.zip.  They are attached to the same GitHub release as Vapor-win64.zip (the release workflow does that), and the
# file names have to match $ExtraCatalog in install.ps1.  A package is skipped when its .pyw is not in the repo root.
$extras = @(
    @{ Name = 'Harmony'; Script = 'Harmony.pyw'; Pip = @('PySide6', 'Pillow') },
    @{ Name = 'Synapse'; Script = 'Synapse.pyw'; Pip = @('PySide6') }
)
foreach ($x in $extras) {
    if (-not (Test-Path $x.Script)) { Write-Host "Skipping $($x.Name): $($x.Script) is not in the repo root" -ForegroundColor Yellow; continue }
    $pip = $x.Pip
    python -m pip install $pip
    if ($LASTEXITCODE) { throw "pip failed ($($x.Name))" }
    python -m PyInstaller --noconfirm --clean --windowed --name $x.Name --distpath "dist\$($x.Name)Build" --workpath "build\$($x.Name.ToLower())" --specpath build $x.Script
    if ($LASTEXITCODE) { throw "PyInstaller failed ($($x.Name))" }
    $zipPath = Join-Path (Resolve-Path dist).Path "$($x.Name)-win64.zip"
    Remove-Item $zipPath -ErrorAction SilentlyContinue
    [IO.Compression.ZipFile]::CreateFromDirectory((Resolve-Path "dist\$($x.Name)Build\$($x.Name)").Path, $zipPath, [IO.Compression.CompressionLevel]::Optimal, $false)
    Remove-Item "dist\$($x.Name)Build" -Recurse -Force
    Write-Host "Done:  dist\$($x.Name)-win64.zip" -ForegroundColor Green
}
