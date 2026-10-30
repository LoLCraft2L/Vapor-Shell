# Vapor installer / updater / uninstaller (terminal UI).
#   Install or update:  irm https://raw.githubusercontent.com/LoLCraft2L/Vapor-Shell/main/scripts/install.ps1 | iex
# Options (needs the script-block form):
#   & ([scriptblock]::Create((irm <that url>))) -AutoStart      start Vapor at every login
#   & ([scriptblock]::Create((irm <that url>))) -Dir D:\Apps\Vapor   install somewhere else
# Vapor is installed into a "Vapor" folder inside the folder you run this from (cd there first).
#   & ([scriptblock]::Create((irm <that url>))) -Uninstall      remove Vapor
param(
    [string]$Repo = $(if ($env:VAPOR_REPO) { $env:VAPOR_REPO } else { "LoLCraft2L/Vapor-Shell" }),
    [string]$Dir  = '',
    [switch]$AutoStart,
    [switch]$Uninstall
)
$VaporVersion = 'v0.1.2'
$VaporStage   = 'closed beta testing'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$programs = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$menuLnk  = Join-Path $programs 'Vapor.lnk'
$startLnk = Join-Path $programs 'Startup\Vapor.lnk'

# install folder: -Dir if given, otherwise a "Vapor" folder inside the folder you are in right now.
# (-Uninstall run from somewhere else falls back to the folder the Start menu shortcut points to.)
$base = (Get-Location -PSProvider FileSystem).ProviderPath
if ($Dir) {
    if (-not [IO.Path]::IsPathRooted($Dir)) { $Dir = Join-Path $base $Dir }
} else {
    $Dir = Join-Path $base 'Vapor'
    if ($Uninstall -and -not (Test-Path (Join-Path $Dir 'Vapor.exe')) -and (Test-Path $menuLnk)) {
        try {
            $t = (New-Object -ComObject WScript.Shell).CreateShortcut($menuLnk).TargetPath
            if ($t) { $Dir = Split-Path $t }
        } catch {}
    }
}
$Dir = [IO.Path]::GetFullPath($Dir).TrimEnd('\')
$exe = Join-Path $Dir 'Vapor.exe'

# safety: never wipe a folder that holds other things (the install step clears the folder it installs into)
if ((Test-Path $Dir) -and -not (Test-Path $exe)) {
    $other = Get-ChildItem $Dir -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin 'config.json', 'files' } | Select-Object -First 1
    if ($other) { throw "'$Dir' already has files in it and no Vapor.exe. Use an empty or new folder (-Dir <path>)." }
}

# ------------------------------------------------------------------ the logo (ASCII art made from Vapor.png)
$LogoBigText = @'
                                                :**++.
                                            .*%%*:
                                     .:    :%@%
                #.         .:   .+#%#+.   :*%#:
              +#@%+.       +* :#@@@@@%%%#**:  +*#%%#
             +*%@@*+.        *#*: :#@#*.  .+*#*++#+
                #:    :***+.+.:*##+:   .++#*+ :+**#%%%@@@%#:
                .  .*%#+   .*%@%: +*#%@@%*+ .++.      .#@@@*
              +:  +@#:   +#@@@@@@@@%#%#.              +@@@#
              *+  *+  *#***@@@@@@%+*@+              +%@@#:
                +.   :+ .*@@@@@@%  @%+++.  .%+   .*%@%*.
            +**+.  :*##%@@@@@@@@%  :%@@@#     .*#@%#+
         +##*.  +##%@@@@@@@@@@@%+ :*@@@#.  :*%@%*:
      +#%*:   +%##%@@@%#****####%%%%#+..+#%%#+.
    *%%*   **%@@@@@@%+ :****++.    .+#%%#*:    +*
  *%@#.  :%%@@@@@@@@%*##.      +*#%%#+.  *.   +##+
.%@@#    %@@@@@@@%%@@#+  .+*#%%#*:     .*@%+    .
*@@@%+   *%%%%#+.  ++*#%%%#*:         +*%@@#*.
.#@@@@@%%####%%%%%%#**+ :**+.            %+
   :***###***++       *#*:               .
'@
$LogoSmallText = @'
                              .+*++
                        .:   #@+
          +#      *..*#@#++**#+.+*:
        .*%@*:     +#**#%#+.:+**##:.+:
          .+ .***+ *##+:+*##*++*+*###@@#
         +: *#+ :#%@@%%%%#+         #@%+
         :. : +*+*@@@@+##    +:  .*%%*
       :**+.+*#%@@@@@% :%@@. ::*%%*:
    :##*..*#%@@@%%%%%*#%%#:+#%#*.
  +%#:.*#@@@@%++++*+++.+###*:  **
:%@+  %@@@@@%@#+ :+*###+. .#*  ::
#@@#++*###*+*####**.     :*%%*.
 +##%%%###*++ .**+         +.
'@

# colours sampled from Vapor.png: each digit below is a palette index for the character at the same spot in the art above
$LogoPalette = @('244;235;250', '221;202;244', '208;173;245', '192;152;245', '190;158;215', '175;136;245', '178;119;247', '181;126;234', '164;111;245', '180;99;240', '167;122;215', '161;110;232', '149;98;236', '145;94;212', '146;106;178', '110;69;150')
$LogoBigColors = @'
                                                6bbdde
                                            d6666f
                                     7e    eb66
                14         77   43335a7   b886b
              111227       a9 222335566888be  999999
             e12223e4        4234 77657e  ddd99dfd9
                77    cccddee443337f   aa5aaa dddccccc888888
                f  ccccc   42223a a5555555a ffdf      cdc888
              9d  cccd   4222223333556bb              dc888
              99  cc  1112422123355d8b              dc8888
                ef   11 e32112555  b6bdbd  242   8d88888
            77aae  41111111235555  dc8888     7d88888
         7777a  11111122235555668 db8888b  8d88888
      7677a   1012111233555bbbb8888888bdeb8888b
    6667   d1002101233 dddbbbbb    8fb88888    e4
  6667b  c70000001223a5bc      8db88888  44   f412
b666b    20000001223335  b8db88888     22213    e
6666b6   00000012  5adb888888         e222237a
66666668bbbbbbb88688888 ddddf            33
   666666666688       cccc               a
'@
$LogoSmallColors = @'
                              666bd
                        7a   b66
          12      7a2233568bb8d9999
        e122a7     4245765dffdb9edccc8
          aa cccdf 223a555555afddcccc888
         99 ccc 222223555bb         c888
         de d 114321355b8    a2  fc888
       77aae1111112555 d8888 44b8888
    7777a111112355568b88888fb8888
  666ad40111123ddbbb88bdb8888  42
666d  200012235b bfb88888 d42  42
66bde100001335b88888     e2223a
 666666688888 8dcd         77
'@

# ------------------------------------------------------------------ terminal setup
$ESC = [char]27
$script:tui = $false
$winW = 80; $winH = 25
try {
    if ($Host.Name -eq 'ConsoleHost' -and -not [Console]::IsOutputRedirected) {
        $winW = $Host.UI.RawUI.WindowSize.Width
        $winH = $Host.UI.RawUI.WindowSize.Height
        $script:tui = $true
        if (-not ($env:WT_SESSION -or $PSVersionTable.PSVersion.Major -ge 7)) {      # old console window: switch on ANSI colour support
            Add-Type -Namespace VaporCon -Name K -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
[DllImport("kernel32.dll")] public static extern bool GetConsoleMode(IntPtr h, out uint m);
[DllImport("kernel32.dll")] public static extern bool SetConsoleMode(IntPtr h, uint m);
'@
            $hOut = [VaporCon.K]::GetStdHandle(-11); [uint32]$mode = 0
            if (-not [VaporCon.K]::GetConsoleMode($hOut, [ref]$mode)) { $script:tui = $false }
            elseif (-not [VaporCon.K]::SetConsoleMode($hOut, ($mode -bor 4))) { $script:tui = $false }
        }
    }
} catch { $script:tui = $false }

$AREA = 6                                                   # lines of the live status area
# pick the biggest logo that fits the window (it must not scroll, or the redraw would smear)
$LogoText = ''; $ColorText = ''
if ($script:tui) {
    if ($winW -ge 64 -and $winH -ge 30)     { $LogoText = $LogoBigText; $ColorText = $LogoBigColors }
    elseif ($winW -ge 44 -and $winH -ge 24) { $LogoText = $LogoSmallText; $ColorText = $LogoSmallColors }
    if ($winH -lt 14) { $script:tui = $false }
}
$Logo = @(); $LogoCol = @(); if ($LogoText) { $Logo = @($LogoText -split "`r?`n"); $LogoCol = @($ColorText -split "`r?`n") }
$LogoH = $Logo.Count
$LogoW = 0; foreach ($r in $Logo) { if ($r.Length -gt $LogoW) { $LogoW = $r.Length } }

function Mix($a, $b, [double]$t) { [int]($a + ($b - $a) * $t) }

# colour of every logo cell: taken from the palette sampled out of Vapor.png (white-lavender comet head, purple ring and tails)
$palRGB = @(); foreach ($p in $LogoPalette) { $palRGB += ,@($p -split ';' | ForEach-Object { [int]$_ }) }
$cellC = New-Object 'object[]' $LogoH
for ($y = 0; $y -lt $LogoH; $y++) {
    $row = $Logo[$y]; $crow = $LogoCol[$y]; $arr = New-Object 'int[]' ($row.Length * 3)
    for ($x = 0; $x -lt $row.Length; $x++) {
        $pi = 0
        if ($x -lt $crow.Length -and $crow[$x] -ne ' ') { $pi = [Convert]::ToInt32([string]$crow[$x], 16) }
        $rgb = $palRGB[$pi]
        $arr[$x*3] = $rgb[0]; $arr[$x*3+1] = $rgb[1]; $arr[$x*3+2] = $rgb[2]
    }
    $cellC[$y] = $arr
}

# one frame of the logo.  mode 'reveal': drawn up to the moving front (comet flow, lower-left to upper-right); 'shine': all drawn, a bright band sweeps over
function Get-LogoFrame([double]$front, [string]$mode) {
    $sb = New-Object System.Text.StringBuilder
    $band = 9.0
    for ($y = 0; $y -lt $LogoH; $y++) {
        $row = $Logo[$y]; $c = $cellC[$y]; $last = ''
        for ($x = 0; $x -lt $row.Length; $x++) {
            $ch = $row[$x]
            if ($ch -eq ' ') { [void]$sb.Append(' '); continue }
            $d = $x + ($LogoH - 1 - $y) * 2.0
            if ($mode -eq 'reveal') {
                if ($d -gt $front) { [void]$sb.Append(' '); continue }
                $k = 1.0 - ($front - $d) / $band
            } else {
                $k = 1.0 - [Math]::Abs($front - $d) / $band
            }
            if ($k -lt 0) { $k = 0 }
            $r = [int]($c[$x*3]   + (255 - $c[$x*3])   * $k)
            $g = [int]($c[$x*3+1] + (255 - $c[$x*3+1]) * $k)
            $b = [int]($c[$x*3+2] + (255 - $c[$x*3+2]) * $k)
            $col = "$r;$g;$b"
            if ($col -ne $last) { [void]$sb.Append("$ESC[38;2;${col}m"); $last = $col }
            [void]$sb.Append($ch)
        }
        [void]$sb.Append("$ESC[0m`r`n")
    }
    $sb.ToString()
}

function Get-Title {
    $text = 'V  A  P  O  R'
    $pad = [Math]::Max(2, [int](($LogoW - $text.Length) / 2))
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append(' ' * $pad)
    for ($i = 0; $i -lt $text.Length; $i++) {
        $t = $i / [double]($text.Length - 1)
        [void]$sb.Append("$ESC[1;38;2;$(Mix 250 160 $t);$(Mix 244 110 $t);255m$($text[$i])")
    }
    [void]$sb.Append("$ESC[0m`r`n")
    [void]$sb.Append(' ' * $pad); [void]$sb.Append("$ESC[38;2;120;100;170mfluid shell for Windows$ESC[0m`r`n")
    [void]$sb.Append(' ' * $pad); [void]$sb.Append("$ESC[38;2;192;132;252m$VaporVersion$ESC[38;2;120;100;170m  $([char]0x00B7)  $VaporStage$ESC[0m`r`n")
    $sb.ToString()
}

# ------------------------------------------------------------------ live area
$WAVE = 0x2581..0x2588 | ForEach-Object { [char]$_ }          # the 8 block heights, a wave surface
$script:stageState = @('pending', 'pending', 'pending', 'pending')
$script:stageLabel = @('Finding the latest release', 'Downloading', 'Unpacking', 'Installing')
$script:barFrac = -1.0; $script:barInfo = ''
$sw = [Diagnostics.Stopwatch]::StartNew()
$script:lastRender = -1000

function Get-Bar([double]$frac, [double]$t, [int]$width) {
    $sb = New-Object System.Text.StringBuilder
    $filled = [int][Math]::Floor($frac * $width)
    for ($i = 0; $i -lt $width; $i++) {
        if ($i -lt $filled) {
            $h = [Math]::Sin($i * 0.55 - $t * 6.0) * 0.5 + 0.5
            $g = [Math]::Sin($i * 0.25 - $t * 3.0) * 0.5 + 0.5
            $glyph = $WAVE[2 + [int]($h * 5.99)]
            [void]$sb.Append("$ESC[38;2;$(Mix 140 225 $g);$(Mix 92 200 $g);$(Mix 245 255 $g)m$glyph")
        } elseif ($i -eq $filled -and $frac -lt 1.0) {
            [void]$sb.Append("$ESC[38;2;255;255;255m$([char]0x2593)")
        } else {
            [void]$sb.Append("$ESC[38;2;58;40;96m$([char]0x00B7)")
        }
    }
    [void]$sb.Append("$ESC[0m")
    $sb.ToString()
}

function Get-StageLine([int]$i, [double]$t) {
    $label = $script:stageLabel[$i]
    switch ($script:stageState[$i]) {
        'done'    { return "  $ESC[38;2;192;132;252m$([char]0x25A0)$ESC[0m $ESC[38;2;215;200;245m$label$ESC[0m" }
        'active'  {
            $w = ''
            for ($k = 0; $k -lt 4; $k++) {
                $h = [Math]::Sin($t * 9.0 + $k * 1.2) * 0.5 + 0.5
                $w += "$ESC[38;2;$(Mix 150 235 $h);$(Mix 100 215 $h);255m$($WAVE[1 + [int]($h * 6.99)])"
            }
            return "  $w$ESC[0m $ESC[1;38;2;255;255;255m$label$ESC[0m"
        }
        default   { return "  $ESC[38;2;70;55;110m$([char]0x00B7)   $label$ESC[0m" }
    }
}

function Render([switch]$Force) {
    if (-not $script:tui) { return }
    $now = $sw.ElapsedMilliseconds
    if (-not $Force -and ($now - $script:lastRender) -lt 40) { return }
    $script:lastRender = $now
    $t = $now / 1000.0
    $barW = [Math]::Max(12, [Math]::Min(36, $winW - 44))
    $lines = @('', (Get-StageLine 0 $t), (Get-StageLine 1 $t))
    if ($script:barFrac -ge 0) { $lines += ("    " + (Get-Bar $script:barFrac $t $barW) + "  $ESC[38;2;190;170;235m" + $script:barInfo + "$ESC[0m") } else { $lines += '' }
    $lines += (Get-StageLine 2 $t)
    $lines += (Get-StageLine 3 $t)
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append("$ESC[${AREA}A")
    foreach ($l in $lines) { [void]$sb.Append("$ESC[2K$l`r`n") }
    [Console]::Out.Write($sb.ToString())
}

function Set-Stage([int]$i, [string]$state, [string]$label) {
    $script:stageState[$i] = $state
    if ($label) { $script:stageLabel[$i] = $label }
    if ($script:tui) { Render -Force }
    elseif ($state -eq 'active') { Write-Host "  $($script:stageLabel[$i]) ..." }
}

function Get-Err($e) { $x = $e.Exception; while ($x.InnerException) { $x = $x.InnerException }; $x.Message }

function Wait-Task($task) { while (-not $task.Wait(40)) { Render } }

# run a script block in its own runspace so the animation keeps moving while it works
function Invoke-Busy([scriptblock]$Script, [object[]]$ArgList) {
    $ps = [powershell]::Create()
    try {
        [void]$ps.AddScript($Script)
        foreach ($a in $ArgList) { [void]$ps.AddArgument($a) }
        $ar = $ps.BeginInvoke()
        while (-not $ar.AsyncWaitHandle.WaitOne(40)) { Render }
        [void]$ps.EndInvoke($ar)
    } finally { $ps.Dispose() }
}

function Stop-Vapor {
    $ctl = Join-Path $Dir 'vaporctl.exe'
    if ((Test-Path $ctl) -and (Get-Process -Name Vapor -ErrorAction SilentlyContinue)) {
        try { & $ctl quit | Out-Null; Start-Sleep -Seconds 2 } catch {}
    }
    Get-Process -Name Vapor, vaporctl -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}
function New-Shortcut($path, $target) {
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
    $s.TargetPath = $target; $s.WorkingDirectory = Split-Path $target; $s.Save()
}

# ------------------------------------------------------------------ intro: the logo flows in
function Show-Intro {
    if (-not $script:tui) { Write-Host "Vapor installer $VaporVersion ($VaporStage)"; return }
    [Console]::Out.Write("$ESC[?25l`r`n")
    if ($LogoH -gt 0) {
        $maxD = $LogoW + $LogoH * 2 + 12
        for ($f = 0; $f -le [int]($maxD / 6) + 2; $f++) {
            $frame = Get-LogoFrame ($f * 6.0) 'reveal'
            if ($f -gt 0) { [Console]::Out.Write("$ESC[${LogoH}A") }
            [Console]::Out.Write($frame)
            Start-Sleep -Milliseconds 28
        }
    }
    [Console]::Out.Write((Get-Title))
    [Console]::Out.Write(("`r`n" * $AREA))
}

function Show-Outro {                                      # one shine over the logo when everything is done
    if (-not ($script:tui -and $LogoH -gt 0)) { return }
    $up = $LogoH + 3 + $AREA
    [Console]::Out.Write("$ESC[${up}A")
    $maxD = $LogoW + $LogoH * 2 + 12
    for ($f = -1; $f -le [int]($maxD / 6) + 2; $f++) {
        [Console]::Out.Write((Get-LogoFrame ($f * 6.0) 'shine'))
        Start-Sleep -Milliseconds 22
        [Console]::Out.Write("$ESC[${LogoH}A")
    }
    [Console]::Out.Write((Get-LogoFrame (-1000.0) 'shine'))
    [Console]::Out.Write("$ESC[$(3 + $AREA)B")
}

# ================================================================== uninstall
if ($Uninstall) {
    try {
        Show-Intro
        Write-Host "  Removing Vapor ..."
        Stop-Vapor
        Remove-Item $menuLnk, $startLnk -Force -ErrorAction SilentlyContinue
        Remove-Item $Dir -Recurse -Force -ErrorAction SilentlyContinue
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
        $raw = $key.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
        $new = ($raw -split ';' | Where-Object { $_ -and ($_.TrimEnd('\') -ne $Dir.TrimEnd('\')) }) -join ';'
        if ($new -ne $raw) { $key.SetValue('Path', $new, 'ExpandString') }
        $key.Close()
        Write-Host "  Vapor removed. (Logs and settings in $env:LOCALAPPDATA\vapor were kept.)" -ForegroundColor Green
    } finally { if ($script:tui) { [Console]::Out.Write("$ESC[?25h") } }
    return
}

if ($Repo -like 'YOUR_*') { throw "Edit install.ps1: set `$Repo to your GitHub 'user/repo' (or set `$env:VAPOR_REPO)." }

# ================================================================== install / update
$tmp = Join-Path $env:TEMP ("vapor-" + [guid]::NewGuid().ToString('N'))
$failed = $null
$tag = ''
try {
    Show-Intro
    New-Item -ItemType Directory $tmp | Out-Null
    Add-Type -AssemblyName System.Net.Http
    $http = New-Object System.Net.Http.HttpClient
    $http.Timeout = [TimeSpan]::FromMinutes(30)
    $http.DefaultRequestHeaders.UserAgent.ParseAdd('vapor-installer')

    # 1  find the release
    Set-Stage 0 'active' $null
    $task = $http.GetStringAsync("https://api.github.com/repos/$Repo/releases/latest")
    Wait-Task $task
    $rel = $task.Result | ConvertFrom-Json
    $asset = $rel.assets | Where-Object { $_.name -eq 'Vapor-win64.zip' } | Select-Object -First 1
    if (-not $asset) { throw "Release $($rel.tag_name) has no Vapor-win64.zip." }
    $tag = $rel.tag_name
    Set-Stage 0 'done' "Found Vapor $tag"

    # 2  download, with the wave bar
    $zip = Join-Path $tmp 'Vapor-win64.zip'
    $total = [double]$asset.size
    Set-Stage 1 'active' "Downloading Vapor $tag"
    $script:barFrac = 0.0
    $resp = $null; $stream = $null; $fs = $null
    try {
        $task = $http.GetAsync($asset.browser_download_url, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead)
        Wait-Task $task
        $resp = $task.Result
        [void]$resp.EnsureSuccessStatusCode()
        $task = $resp.Content.ReadAsStreamAsync(); Wait-Task $task; $stream = $task.Result
        $fs = [IO.File]::Create($zip)
        $buf = New-Object byte[] 65536
        $got = 0.0; $speed = 0.0; $lastB = 0.0; $lastT = $sw.Elapsed.TotalSeconds
        while ($true) {
            $rt = $stream.ReadAsync($buf, 0, $buf.Length)
            Wait-Task $rt
            $n = $rt.Result
            if ($n -le 0) { break }
            $fs.Write($buf, 0, $n); $got += $n
            $nowS = $sw.Elapsed.TotalSeconds
            if (($nowS - $lastT) -ge 0.5) {
                $inst = ($got - $lastB) / ($nowS - $lastT)
                $speed = if ($speed -eq 0) { $inst } else { $speed * 0.6 + $inst * 0.4 }
                $lastB = $got; $lastT = $nowS
            }
            $script:barFrac = [Math]::Min(1.0, $got / $total)
            $script:barInfo = ('{0,3}%  {1:0.0} / {2:0.0} MB  {3:0.0} MB/s' -f [int]($script:barFrac * 100), ($got / 1MB), ($total / 1MB), ($speed / 1MB))
            Render
        }
    } finally {
        if ($fs) { $fs.Dispose() }
        if ($stream) { $stream.Dispose() }
        if ($resp) { $resp.Dispose() }
    }
    $script:barFrac = 1.0
    $script:barInfo = ('100%  {0:0.0} MB' -f ($total / 1MB))
    Set-Stage 1 'done' "Downloaded Vapor $tag"

    # 3  unpack
    Set-Stage 2 'active' $null
    Invoke-Busy {
        param($z, $d)
        $ErrorActionPreference = 'Stop'
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($z, $d)
    } @($zip, (Join-Path $tmp 'new'))
    Set-Stage 2 'done' 'Unpacked'

    # 4  install (keeps config.json and files\)
    Set-Stage 3 'active' $null
    Invoke-Busy {
        param($Dir, $Src)
        $ErrorActionPreference = 'Stop'
        $ctl = Join-Path $Dir 'vaporctl.exe'
        if ((Test-Path $ctl) -and (Get-Process -Name Vapor -ErrorAction SilentlyContinue)) {
            try { & $ctl quit | Out-Null; Start-Sleep -Seconds 2 } catch {}
        }
        Get-Process -Name Vapor, vaporctl -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        New-Item -ItemType Directory $Dir -Force | Out-Null
        Get-ChildItem $Dir -Force | Where-Object { $_.Name -notin 'config.json', 'files' } | Remove-Item -Recurse -Force
        Get-ChildItem $Src -Force | Where-Object { $_.Name -ne 'files' } | Copy-Item -Destination $Dir -Recurse -Force
        if (Test-Path (Join-Path $Src 'files')) {
            robocopy (Join-Path $Src 'files') (Join-Path $Dir 'files') /E /XC /XN /XO /NFL /NDL /NJH /NJS /NP | Out-Null
        }
    } @($Dir, (Join-Path $tmp 'new'))
    New-Shortcut $menuLnk $exe
    if ($AutoStart) { New-Shortcut $startLnk $exe }
    Set-Stage 3 'done' 'Installed'
} catch {
    $failed = Get-Err $_
} finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    if ($http) { $http.Dispose() }
}

if ($failed) {
    if ($script:tui) { [Console]::Out.Write("$ESC[?25h") }
    Write-Host ""
    Write-Host "  Install failed: $failed" -ForegroundColor Red
    return
}

Show-Outro
if ($script:tui) { [Console]::Out.Write("$ESC[?25h") }
Write-Host "  Vapor $tag is installed in $Dir" -ForegroundColor Green
Start-Process $exe -WorkingDirectory $Dir