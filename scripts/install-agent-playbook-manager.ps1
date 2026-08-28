[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repositoryRoot 'skills\global\agent-playbook-manager'
$target = Join-Path $env:USERPROFILE '.codex\skills\agent-playbook-manager'

$requiredFiles = @(
    (Join-Path $source 'SKILL.md'),
    (Join-Path $source 'agents\openai.yaml')
)

foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Missing required skill file: $requiredFile"
    }
}

if ($PSCmdlet.ShouldProcess($target, 'Install agent-playbook-manager skill')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $target 'agents') | Out-Null
    Copy-Item -LiteralPath (Join-Path $source 'SKILL.md') -Destination (Join-Path $target 'SKILL.md') -Force
    Copy-Item -LiteralPath (Join-Path $source 'agents\openai.yaml') -Destination (Join-Path $target 'agents\openai.yaml') -Force
    Write-Output "Installed agent-playbook-manager to $target"
}
