param(
    [string]$InputPath = "",
    [string]$Output = "output",
    [string]$ImageDir = "",
    [string]$CoreReference = "",
    [ValidateSet("prepare", "approve-deck", "prepare-page", "approve-page", "generate", "approve-image", "status")]
    [string]$Stage = "prepare",
    [int]$Page = 0,
    [switch]$PromptOnly,
    [switch]$Legacy
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Resolve-Python {
    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "py",
        "python"
    )
    foreach ($candidate in $candidates) {
        try {
            $cmd = Get-Command $candidate -ErrorAction Stop
            return $cmd.Source
        }
        catch {
        }
    }
    throw "Python not found. Install Python 3.10+ or create .venv in the project."
}

function Resolve-InputReport {
    param([string]$ExplicitPath)
    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath)) {
            throw "Input report not found: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $supported = @("*.docx", "*.pdf", "*.md", "*.txt")
    $files = foreach ($pattern in $supported) {
        Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "input") -Filter $pattern -File -ErrorAction SilentlyContinue
    }
    $latest = $files | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        throw "No report found in input\. Put a .docx, .pdf, .md, or .txt file there first."
    }
    return $latest.FullName
}

$python = Resolve-Python
$report = $null
if ($Legacy -or $Stage -eq "prepare") {
    $report = Resolve-InputReport $InputPath
}

Write-Host "Project: $ProjectRoot"
Write-Host "Python: $python"
if ($report) {
    Write-Host "Input report: $report"
}

$mode = if ($Legacy) { "legacy" } else { "production" }
$argsList = @("-X", "utf8", "src\main.py", "--mode", $mode, "--output", $Output)

if ($Legacy) {
    $argsList += @("--input", $report)
}
else {
    $argsList += @("--stage", $Stage)
    if ($Stage -eq "prepare") {
        $argsList += @("--input", $report)
    }
    if ($Page -gt 0) {
        $argsList += @("--page", $Page)
    }
}

if ($CoreReference) {
    $argsList += @("--core-reference", $CoreReference)
}

if ($ImageDir -and ($Legacy -or $Stage -eq "generate")) {
    $argsList += @("--mockup-provider", "existing", "--image-dir", $ImageDir)
}
elseif (($Legacy -or $Stage -eq "generate") -and ($PromptOnly -or -not $env:OPENAI_API_KEY)) {
    Write-Host "This image stage will create GPT image prompts only."
    $argsList += @("--mockup-provider", "prompt_only")
}

& $python @argsList
$code = $LASTEXITCODE

if ($Legacy -and ($PromptOnly -or -not $env:OPENAI_API_KEY) -and $code -eq 2) {
    Write-Host "Prompt-only checkpoint completed. Prompts are in output\slide_images\image_prompts.md."
    exit 0
}

exit $code
