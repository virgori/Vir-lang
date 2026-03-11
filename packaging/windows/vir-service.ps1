<#
.SYNOPSIS
    Vir Language — Windows Service Manager
.DESCRIPTION
    Registers, starts, stops, and removes the Vir runtime as a Windows Service.
    Designed for Windows Server 2019/2022.
.EXAMPLE
    .\vir-service.ps1 -Action Install
    .\vir-service.ps1 -Action Start
    .\vir-service.ps1 -Action Stop
    .\vir-service.ps1 -Action Remove
    .\vir-service.ps1 -Action Status
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Install', 'Start', 'Stop', 'Remove', 'Status', 'Restart')]
    [string]$Action
)

$ServiceName = "VirRuntime"
$DisplayName = "Vir Language Runtime"
$Description = "Vir Language Runtime Server — JIT compiler and Q-IR VM"

# Locate binaries
$VirHome = if ($env:VIR_HOME) { $env:VIR_HOME } else { "${env:ProgramFiles}\Vir" }
$VirBin = Join-Path $VirHome "bin\vir.bat"
$ConfigFile = Join-Path $env:ProgramData "Vir\config\vir.conf"
$LogDir = Join-Path $env:ProgramData "Vir\log"

function Ensure-Directories {
    $dirs = @(
        (Join-Path $env:ProgramData "Vir\config"),
        (Join-Path $env:ProgramData "Vir\log"),
        (Join-Path $env:ProgramData "Vir\cache"),
        (Join-Path $env:ProgramData "Vir\data")
    )
    foreach ($d in $dirs) {
        if (-not (Test-Path $d)) {
            New-Item -ItemType Directory -Path $d -Force | Out-Null
            Write-Host "  Created: $d"
        }
    }
}

switch ($Action) {
    'Install' {
        Write-Host "═══ Installing Vir as Windows Service ═══"

        # Ensure directories exist
        Ensure-Directories

        # Copy default config if not present
        if (-not (Test-Path $ConfigFile)) {
            $srcConf = Join-Path $VirHome "config\vir.conf"
            if (Test-Path $srcConf) {
                Copy-Item $srcConf $ConfigFile
                Write-Host "  Copied default config to $ConfigFile"
            }
        }

        # The service runs Python with the Vir module
        $BinaryPath = "python -m src.runtime.lifecycle --server --config `"$ConfigFile`""

        # Create the service using sc.exe
        $existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "  Service already exists. Remove first: .\vir-service.ps1 -Action Remove"
            exit 1
        }

        # Use NSSM (Non-Sucking Service Manager) if available, otherwise sc.exe
        $nssm = Get-Command nssm -ErrorAction SilentlyContinue
        if ($nssm) {
            & nssm install $ServiceName python
            & nssm set $ServiceName AppParameters "-m src.runtime.lifecycle --server --config `"$ConfigFile`""
            & nssm set $ServiceName DisplayName $DisplayName
            & nssm set $ServiceName Description $Description
            & nssm set $ServiceName AppDirectory $VirHome
            & nssm set $ServiceName AppStdout (Join-Path $LogDir "vir-stdout.log")
            & nssm set $ServiceName AppStderr (Join-Path $LogDir "vir-stderr.log")
            & nssm set $ServiceName AppRotateFiles 1
            & nssm set $ServiceName AppRotateBytes 10485760
            & nssm set $ServiceName Start SERVICE_DEMAND_START
            Write-Host "  ✓ Service installed via NSSM"
        } else {
            # Fallback: sc.exe (limited — no stdout redirect)
            sc.exe create $ServiceName `
                binpath= "$BinaryPath" `
                DisplayName= "$DisplayName" `
                start= demand
            sc.exe description $ServiceName "$Description"
            Write-Host "  ✓ Service installed via sc.exe"
            Write-Host "  ⚠ For better log management, install NSSM: https://nssm.cc"
        }

        Write-Host ""
        Write-Host "  Start: .\vir-service.ps1 -Action Start"
        Write-Host "  Config: $ConfigFile"
    }

    'Start' {
        Write-Host "Starting $ServiceName..."
        Start-Service -Name $ServiceName
        Write-Host "  ✓ Service started"
    }

    'Stop' {
        Write-Host "Stopping $ServiceName..."
        Stop-Service -Name $ServiceName -Force
        Write-Host "  ✓ Service stopped"
    }

    'Restart' {
        Write-Host "Restarting $ServiceName..."
        Restart-Service -Name $ServiceName -Force
        Write-Host "  ✓ Service restarted"
    }

    'Remove' {
        Write-Host "Removing $ServiceName..."
        $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq 'Running') {
            Stop-Service -Name $ServiceName -Force
        }

        $nssm = Get-Command nssm -ErrorAction SilentlyContinue
        if ($nssm) {
            & nssm remove $ServiceName confirm
        } else {
            sc.exe delete $ServiceName
        }
        Write-Host "  ✓ Service removed"
    }

    'Status' {
        $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($svc) {
            Write-Host "Service: $ServiceName"
            Write-Host "  Status:  $($svc.Status)"
            Write-Host "  Display: $($svc.DisplayName)"
            Write-Host "  Start:   $($svc.StartType)"
        } else {
            Write-Host "Service '$ServiceName' is not installed."
        }
    }
}
