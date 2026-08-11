param(
    [string]$InputPath = "",
    [string]$Output = "output",
    [string]$ImageDir = "",
    [string]$CoreReference = "",
    [switch]$PromptOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Resolve-Python {
    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
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
$report = Resolve-InputReport $InputPath

Write-Host "Project: $ProjectRoot"
Write-Host "Input report: $report"
Write-Host "Python: $python"

$argsList = @("src\main.py", "--input", $report, "--output", $Output)

if ($CoreReference) {
    $argsList += @("--core-reference", $CoreReference)
}

if ($ImageDir) {
    $argsList += @("--mockup-provider", "existing", "--image-dir", $ImageDir)
}
elseif ($PromptOnly -or -not $env:OPENAI_API_KEY) {
    Write-Host "OPENAI_API_KEY is not set, so this run will create GPT image prompts only."
    Write-Host "Use Codex automation or image2/GPT image generation to save slide_XX.png, then rerun with -ImageDir."
    $argsList += @("--mockup-provider", "prompt_only")
}

& $python @argsList
$code = $LASTEXITCODE

if (($PromptOnly -or -not $env:OPENAI_API_KEY) -and $code -eq 2) {
    Write-Host "Prompt-only checkpoint completed. Prompts are in output\slide_images\image_prompts.md."
    exit 0
}

exit $code
