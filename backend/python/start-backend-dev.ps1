param(
    [string]$EnvFile = "..\.env"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $scriptDir $EnvFile

if (-not (Test-Path $envPath)) {
    throw "Env file not found: $envPath"
}

Write-Host "Loading env vars from: $envPath"

Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()

    if (-not $line -or $line.StartsWith("#")) {
        return
    }

    $parts = $line -split "=", 2
    if ($parts.Count -ne 2) {
        return
    }

    $key = $parts[0].Trim()
    $value = $parts[1].Trim()

    # Remove optional wrapping quotes from values
    if (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    [Environment]::SetEnvironmentVariable($key, $value, "Process")
}

Write-Host "Starting FastAPI dev server..."
uv run .\fast_api.py
