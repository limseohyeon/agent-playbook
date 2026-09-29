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
}

process {
    if ($null -ne $InputText) {
        $inputLines.Add($InputText)
    }
}

end {
    $candidates = @()
    $pathPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pathPython) {
        $candidates += $pathPython.Source
    }

    $localPrograms = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $localPrograms) {
        $candidates += Get-ChildItem -LiteralPath $localPrograms -Filter python.exe -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -ExpandProperty FullName
    }

    $pythonExe = $candidates | Select-Object -First 1
    if (-not $pythonExe) {
        Write-Error 'Python 3 is required but was not found.'
        exit 1
    }

    if ($inputLines.Count -gt 0) {
        ($inputLines -join "`n") | & $pythonExe (Join-Path $PSScriptRoot 'gitlab_issue_lifecycle.py') $Command @RemainingArgs
    } else {
        & $pythonExe (Join-Path $PSScriptRoot 'gitlab_issue_lifecycle.py') $Command @RemainingArgs
    }
    exit $LASTEXITCODE
}
