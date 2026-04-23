param(
    [string]$Config = "$PSScriptRoot\config\settings.json",
    [switch]$ApplyRename
)

$ErrorActionPreference = "Stop"

$python = "python"
$scripts = Join-Path $PSScriptRoot "scripts"

Write-Host "[1/3] scan_manifest.py"
& $python (Join-Path $scripts "scan_manifest.py") --config $Config

Write-Host "[2/3] dedupe_rename.py"
if ($ApplyRename) {
    & $python (Join-Path $scripts "dedupe_rename.py") --config $Config --apply
}
else {
    & $python (Join-Path $scripts "dedupe_rename.py") --config $Config
}

Write-Host "[3/3] extract_classify.py"
& $python (Join-Path $scripts "extract_classify.py") --config $Config

Write-Host "Pipeline finished."
