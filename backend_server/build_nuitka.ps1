#Requires -Version 5.1
param(
    [ValidateSet("cpu", "cuda", "directml", "openvino", "all")]
    [string]$Runtime = "cpu",
    [string]$OutputDirectory,
    [ValidatePattern("^\d+\.\d+\.\d+$")]
    [string]$Version = "0.5.0",
    [switch]$OneFile,
    [switch]$UIOnly,
    [switch]$CLIOnly,
    [switch]$RecreateEnvironment,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$BuildRoot = Join-Path $ScriptDir ".build"
$RuntimePackages = @{
    cpu = "onnxruntime>=1.16"
    cuda = "onnxruntime-gpu>=1.16"
    directml = "onnxruntime-directml>=1.16"
    openvino = "onnxruntime-openvino>=1.16"
}

# Prefer venv python explicitly
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $BootstrapPython = $VenvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $BootstrapPython = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $BootstrapPython = "python"
} else {
    throw "Python not found. Make sure python or py is available."
}

# Change into the script directory so the stale root phonemation_backend/
# is not on sys.path via the current working directory.
Set-Location $ScriptDir

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
}

function Build-Variant {
    param([string]$Variant)

    $EnvironmentDir = Join-Path $BuildRoot $Variant
    $Python = Join-Path $EnvironmentDir "Scripts\python.exe"
    if ($RecreateEnvironment -and (Test-Path $EnvironmentDir)) {
        Remove-Item -Recurse -Force $EnvironmentDir
    }
    if (-not (Test-Path $Python)) {
        Invoke-Checked $BootstrapPython @("-m", "venv", $EnvironmentDir)
    }

    # Ensure Nuitka is available
    if (-not $SkipDependencyInstall) {
        Invoke-Checked $Python @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked $Python @("-m", "pip", "install", "-r", (Join-Path $ScriptDir "requirements.txt"), "-r", (Join-Path $ScriptDir "requirements-build.txt"), $RuntimePackages[$Variant])
        Invoke-Checked $Python @("-m", "pip", "check")
    }

    $OutDir = if ($OutputDirectory) { Join-Path $OutputDirectory $Variant } else { Join-Path $ProjectDir "artifacts\backend\$Variant" }
    New-Item -ItemType Directory -Force $OutDir | Out-Null
    $BuildInfoPath = Join-Path $EnvironmentDir "build_info.json"
    [ordered]@{
        runtime = $Variant
        version = $Version
        onnxruntime_package = $RuntimePackages[$Variant]
    } | ConvertTo-Json | Set-Content $BuildInfoPath -Encoding UTF8
    $BaseArgs = @(
        "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--lto=no",
        "--enable-plugin=tk-inter",
        "--nofollow-import-to=sympy",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=PIL",
        "--nofollow-import-to=pandas",
        "--nofollow-import-to=scipy",
        "--nofollow-import-to=sklearn",
        "--nofollow-import-to=torch",
        "--nofollow-import-to=tensorflow",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=IPython",
        "--nofollow-import-to=jupyter",
        "--nofollow-import-to=setuptools",
        "--nofollow-import-to=pkg_resources",
        "--nofollow-import-to=cryptography",
        "--output-dir=$OutDir",
        "--remove-output",
        "--include-package=phonemation_backend",
        "--include-package=onnxruntime",
        "--include-distribution-metadata=soundfile",
        "--include-distribution-metadata=sounddevice",
        "--include-data-dir=$ScriptDir\phonemation_backend\json_files=phonemation_backend\json_files",
        "--include-data-dir=$ScriptDir\phonemation_backend\phonemes=phonemation_backend\phonemes",
        "--include-data-file=$BuildInfoPath=phonemation_backend/build_info.json",
        "--include-data-file=$ProjectDir\phonemation.ico=phonemation.ico",
        "--windows-icon-from-ico=$ProjectDir\phonemation.ico",
        "--company-name=Steveway",
        "--product-name=Phonemation Backend ($Variant)",
        "--file-description=Phonemation AI backend with $Variant acceleration",
        "--product-version=$Version",
        "--file-version=$Version"
    )
    if ($OneFile) {
        $BaseArgs += "--onefile"
    }

    # Build CLI version
    if (-not $UIOnly) {
        $CliArgs = $BaseArgs + @(
            "--windows-console-mode=force",
            "--output-filename=phonemation_backend_cli.exe",
            (Join-Path $ScriptDir "phonemation_backend\__main__.py")
        )
        Invoke-Checked $Python $CliArgs
    }

    # Build UI version
    if (-not $CLIOnly) {
        $UiArgs = $BaseArgs + @(
            "--windows-console-mode=disable",
            "--output-filename=phonemation_backend_ui.exe",
            (Join-Path $ScriptDir "main_ui.py")
        )
        Invoke-Checked $Python $UiArgs
    }

    Set-Content -Path (Join-Path $OutDir "runtime.txt") -Value $Variant -Encoding ASCII
    Write-Host "Built $Variant backend in $OutDir" -ForegroundColor Cyan
}

$Variants = if ($Runtime -eq "all") { @("cpu", "cuda", "directml", "openvino") } else { @($Runtime) }
foreach ($Variant in $Variants) {
    Build-Variant $Variant
}
