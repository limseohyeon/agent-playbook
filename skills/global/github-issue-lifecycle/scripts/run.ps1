[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [string]$Command,

    [Parameter(ValueFromPipeline = $true)]
    [AllowEmptyString()]
    [string]$InputText,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

begin {
    $inputLines = [System.Collections.Generic.List[string]]::new()
    $hasPipelineInput = $false
}

process {
    if ($PSBoundParameters.ContainsKey('InputText')) {
        $hasPipelineInput = $true
        $inputLines.Add($InputText)
    }
}

end {
    $candidates = @()
    $pythonPrefixArgs = @()
    $pathPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pathPython) {
        $candidates += $pathPython.Source
    }

    $localPrograms = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $localPrograms) {
        foreach ($minor in 14..10) {
            $versionedPython = Join-Path $localPrograms ("Python3{0}\python.exe" -f $minor)
            if (Test-Path -LiteralPath $versionedPython) {
                $candidates += $versionedPython
            }
        }
        $candidates += Get-ChildItem -LiteralPath $localPrograms -Filter python.exe -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -ExpandProperty FullName
    }

    $pythonExe = $candidates | Select-Object -First 1
    if (-not $pythonExe) {
        $pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($pythonLauncher) {
            $pythonExe = $pythonLauncher.Source
            $pythonPrefixArgs = @('-3')
        }
    }
    if (-not $pythonExe) {
        Write-Error 'Python 3 is required but was not found.'
        exit 1
    }

    if ($hasPipelineInput) {
        ($inputLines -join "`n") | & $pythonExe @pythonPrefixArgs (Join-Path $PSScriptRoot 'github_issue_lifecycle.py') $Command @RemainingArgs
    } else {
        & $pythonExe @pythonPrefixArgs (Join-Path $PSScriptRoot 'github_issue_lifecycle.py') $Command @RemainingArgs
    }
    exit $LASTEXITCODE
}
