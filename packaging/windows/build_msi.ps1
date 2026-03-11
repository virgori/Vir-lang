<#
.SYNOPSIS
    Build MSI installer for Vir Language (Windows Server x86_64)
.DESCRIPTION
    Compiles the native library with MinGW, packages Python + stdlib,
    and creates an MSI installer using WiX Toolset.
.EXAMPLE
    .\build_msi.ps1
    .\build_msi.ps1 -SkipNative
    .\build_msi.ps1 -WixPath "C:\Program Files\WiX Toolset v3.14\bin"
#>

param(
    [string]$Version = "0.3.0",
    [string]$WixPath = "",
    [switch]$SkipNative
)

$ErrorActionPreference = "Stop"

$VirRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CoreDir = Join-Path $VirRoot "core"
$DistDir = Join-Path $VirRoot "dist"
$BuildDir = Join-Path $DistDir "windows-build"
$PackagingDir = Join-Path $VirRoot "packaging\windows"

Write-Host "═══ Vir Windows MSI Builder ═══"
Write-Host "  Version: $Version"
Write-Host "  Root:    $VirRoot"

# ── Locate WiX Toolset ───────────────────────────────────
if (-not $WixPath) {
    $candidates = @(
        "${env:ProgramFiles}\WiX Toolset v3.14\bin",
        "${env:ProgramFiles}\WiX Toolset v3.11\bin",
        "${env:ProgramFiles(x86)}\WiX Toolset v3.14\bin",
        "${env:ProgramFiles(x86)}\WiX Toolset v3.11\bin"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "candle.exe")) {
            $WixPath = $c
            break
        }
    }
    # Also search PATH
    if (-not $WixPath) {
        $candle = Get-Command candle.exe -ErrorAction SilentlyContinue
        if ($candle) { $WixPath = Split-Path $candle.Source }
    }
}

if (-not $WixPath -or -not (Test-Path (Join-Path $WixPath "candle.exe"))) {
    Write-Host "  ✗ WiX Toolset not found."
    Write-Host "    Install from: https://wixtoolset.org/docs/wix3/"
    Write-Host "    Or pass -WixPath to specify location."
    exit 1
}

Write-Host "  WiX:     $WixPath"

# ── Clean build dir ───────────────────────────────────────
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

# ── Build native library ─────────────────────────────────
if (-not $SkipNative) {
    Write-Host ""
    Write-Host "─── Building native library ───"
    Push-Location $CoreDir
    & make clean
    & make all
    Pop-Location
}

# ── Collect build artifacts ───────────────────────────────
Write-Host ""
Write-Host "─── Collecting artifacts ───"

# Copy native binaries
$nativeFiles = @("vir_core.dll", "libvir_core.a")
foreach ($f in $nativeFiles) {
    $src = Join-Path $CoreDir "lib\$f"
    if (Test-Path $src) {
        Copy-Item $src $BuildDir
        Write-Host "  ✓ $f"
    }
}

# Copy CLI exe
$cliExe = Join-Path $CoreDir "build\vir.exe"
if (Test-Path $cliExe) {
    Copy-Item $cliExe $BuildDir
    Write-Host "  ✓ vir.exe"
}

# ── Create LICENSE.rtf (required by WiX) ──────────────────
$licenseRtf = Join-Path $PackagingDir "LICENSE.rtf"
if (-not (Test-Path $licenseRtf)) {
    $licenseTxt = Get-Content (Join-Path $VirRoot "LICENSE") -Raw -ErrorAction SilentlyContinue
    if (-not $licenseTxt) { $licenseTxt = "MIT License`r`n`r`nCopyright (c) 2024 Vir Team" }
    $rtfContent = "{\rtf1\ansi\deff0 {\fonttbl {\f0 Consolas;}}`r`n\f0\fs20 $($licenseTxt -replace "`n", "\par`r`n")`r`n}"
    Set-Content -Path $licenseRtf -Value $rtfContent
    Write-Host "  ✓ Generated LICENSE.rtf"
}

# ── Compile WiX ───────────────────────────────────────────
Write-Host ""
Write-Host "─── Compiling MSI ───"

$wxsFile = Join-Path $PackagingDir "vir.wxs"
$wixObj = Join-Path $BuildDir "vir.wixobj"
$msiFile = Join-Path $DistDir "vir-lang-${Version}-x86_64.msi"

# Candle (compile)
& "$WixPath\candle.exe" `
    -dProductVersion="$Version" `
    -dBuildDir="$BuildDir" `
    -arch x64 `
    -out "$wixObj" `
    "$wxsFile"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ candle.exe failed"
    exit 1
}

# Light (link)
& "$WixPath\light.exe" `
    -ext WixUIExtension `
    -out "$msiFile" `
    "$wixObj"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ light.exe failed"
    exit 1
}

Write-Host ""
Write-Host "✓ MSI built: $msiFile"
Write-Host "  Install: msiexec /i `"$msiFile`""
