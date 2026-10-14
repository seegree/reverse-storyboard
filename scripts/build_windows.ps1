param([switch]$SkipFetch)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $IsWindows -and $env:OS -ne 'Windows_NT') { throw 'Build this application on Windows.' }
if (-not $SkipFetch) {
    python scripts/fetch_runtime.py --platform windows --model 256
    if ($LASTEXITCODE -ne 0) { throw 'Runtime download failed.' }
}
$required = @('runtime/bin/ffmpeg.exe', 'runtime/bin/ffprobe.exe', 'runtime/bin/llama/llama-mtmd-cli.exe',
    'runtime/models/SmolVLM-256M-Instruct-Q8_0.gguf', 'runtime/models/mmproj-SmolVLM-256M-Instruct-Q8_0.gguf')
foreach ($path in $required) { if (-not (Test-Path $path)) { throw "Missing runtime asset: $path" } }
python -m PyInstaller --clean --noconfirm packaging/EditDetector.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
$destination = 'dist/EditDetector/runtime'
New-Item -ItemType Directory -Force "$destination/models" | Out-Null
Copy-Item -Recurse -Force runtime/bin $destination
Copy-Item runtime/models/SmolVLM-256M-Instruct-Q8_0.gguf "$destination/models/"
Copy-Item runtime/models/mmproj-SmolVLM-256M-Instruct-Q8_0.gguf "$destination/models/"
Copy-Item runtime/manifest-256.json $destination
Copy-Item README.md, docs/THIRD_PARTY.md dist/EditDetector/
Copy-Item docs/WINDOWS_REVIEW.md dist/EditDetector/START-HERE.md
Copy-Item -Recurse docs/licenses dist/EditDetector/licenses
# Include license metadata for the exact installed Python dependencies.
python scripts/collect_licenses.py dist/EditDetector/licenses/python
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
$bytes = (Get-ChildItem dist/EditDetector -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ("Portable folder size: {0:N1} MiB" -f ($bytes / 1MB))
Write-Host 'Run dist/EditDetector/EditDetector-CLI.exe self-test --output <new-folder> before distribution.'
