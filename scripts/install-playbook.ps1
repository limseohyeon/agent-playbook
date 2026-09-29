[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Manager', 'All')]
    [string] $Scope = 'Manager',

    [string[]] $Name,

    [switch] $Force,

    [switch] $Uninstall,

    [switch] $List,

    [switch] $Status,

    [ValidateSet('Text', 'Json')]
    [string] $Format = 'Text'
)

$ErrorActionPreference = 'Stop'

$installer = Join-Path $PSScriptRoot 'install_playbook.py'
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Missing installer: $installer"
}

$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonPath = $null
if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
    $pythonPath = $bundledPython
}
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command py -ErrorAction SilentlyContinue
    }
    if ($python) {
        $pythonPath = $python.Source
    }
}
if (-not $pythonPath) {
    throw 'Python is required to install playbook artifacts.'
}

$pythonArgs = @(
    $installer,
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
if ($List) {
    $pythonArgs += '--list'
}
if ($Status) {
    $pythonArgs += '--status'
}
$pythonArgs += @('--format', $Format.ToLowerInvariant())

if (@($Uninstall, $List, $Status).Where({ $_ }).Count -gt 1) {
    throw 'Use only one of -Uninstall, -List, or -Status.'
}

$action = $(
    if ($Uninstall) { 'Uninstall' }
    elseif ($List) { 'List' }
    elseif ($Status) { 'Status' }
    else { 'Install' }
)
$target = "codex $( $Scope.ToLowerInvariant() )"
if ($Name) {
    $target = "codex $($Name -join ', ')"
}

if ($WhatIfPreference) {
    $pythonArgs += '--dry-run'
    & $pythonPath @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    return
}

if ($PSCmdlet.ShouldProcess($target, $action)) {
    & $pythonPath @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
