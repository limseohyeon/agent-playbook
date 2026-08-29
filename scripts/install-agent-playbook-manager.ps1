[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'

$installer = Join-Path $PSScriptRoot 'install-playbook.ps1'
$forwardArgs = @{
    Runtime = 'Codex'
    Scope = 'Manager'
}
if ($WhatIfPreference) {
    $forwardArgs['WhatIf'] = $true
}

& $installer @forwardArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
