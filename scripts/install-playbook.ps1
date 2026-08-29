[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Codex', 'Cursor', 'All')]
    [string] $Runtime = 'Codex',

    [ValidateSet('Manager', 'All')]
    [string] $Scope = 'Manager',

    [string[]] $Name,

    [switch] $Force,

    [switch] $Uninstall
)

$ErrorActionPreference = 'Stop'

$installer = Join-Path $PSScriptRoot 'install_playbook.py'
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Missing installer: $installer"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw 'Python is required to install playbook artifacts.'
}

$pythonArgs = @(
    $installer,
    '--runtime', $Runtime.ToLowerInvariant(),
    '--scope', $Scope.ToLowerInvariant()
)
foreach ($artifactName in $Name) {
    $pythonArgs += @('--name', $artifactName)
}
if ($Force) {
    $pythonArgs += '--force'
}
if ($Uninstall) {
    $pythonArgs += '--uninstall'
}

$action = $(if ($Uninstall) { 'Uninstall' } else { 'Install' })
$target = "$( $Runtime.ToLowerInvariant() ) $( $Scope.ToLowerInvariant() )"
if ($Name) {
    $target = "$( $Runtime.ToLowerInvariant() ) $($Name -join ', ')"
}

if ($WhatIfPreference) {
    $pythonArgs += '--dry-run'
    & $python.Source @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    return
}

if ($PSCmdlet.ShouldProcess($target, $action)) {
    & $python.Source @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
