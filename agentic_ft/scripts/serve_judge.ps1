param(
    [string]$ModelName = "deepseek-r1-distill-70b",
    [string]$Quant = "q4_K_M",
    [string]$Port = "8081",
    [string]$Host = "127.0.0.1",
    [string]$LlamaCppDir = "",
    [string]$GgufPath = "",
    [int]$NGpuLayers = 99,
    [int]$CtxSize = 8192
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path "$ScriptDir/.."
$PidFile = "$RootDir/data/judge_server.pid"
$LogFile = "$RootDir/data/judge_server.log"

function Log { param([string]$Msg) Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Msg" }

# Stop existing server if running
if (Test-Path $PidFile) {
    $OldPid = Get-Content $PidFile
    try {
        $Proc = Get-Process -Id $OldPid -ErrorAction Stop
        Log "Stopping existing judge server (PID $OldPid)..."
        Stop-Process -Id $OldPid -Force
        Start-Sleep -Seconds 2
    } catch {}
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# Determine model path
$ModelPath = ""
if ($GgufPath) {
    $ModelPath = $GgufPath
} elseif ($LlamaCppDir) {
    $ModelPath = "$LlamaCppDir/models/$ModelName-$Quant.gguf"
} else {
    # Check common locations
    $Candidates = @(
        "C:/models/$ModelName-$Quant.gguf",
        "D:/models/$ModelName-$Quant.gguf",
        "$env:USERPROFILE/models/$ModelName-$Quant.gguf",
        "$RootDir/models/$ModelName-$Quant.gguf"
    )
    foreach ($c in $Candidates) {
        if (Test-Path $c) { $ModelPath = $c; break }
    }
}

if (-not $ModelPath -or -not (Test-Path $ModelPath)) {
    Log "ERROR: Model not found. Set -GgufPath or place GGUF at one of:"
    $Candidates | ForEach-Object { Log "  $_" }
    Log ""
    Log "Download it first:"
    Log "  huggingface-cli download TheBloke/DeepSeek-R1-Distill-70B-GGUF deepseek-r1-distill-70b-q4_k_m.gguf --local-dir C:/models"
    exit 1
}
Log "Using model: $ModelPath"

# Find llama-server
$LlamaServer = ""
if ($LlamaCppDir) {
    $LlamaServer = "$LlamaCppDir/build/bin/Release/llama-server.exe"
    if (-not (Test-Path $LlamaServer)) { $LlamaServer = "$LlamaCppDir/llama-server.exe" }
} else {
    $Paths = @("llama-server.exe", "$env:USERPROFILE/llama.cpp/llama-server.exe", "C:/llama.cpp/llama-server.exe")
    foreach ($p in $Paths) {
        if (Get-Command $p -ErrorAction SilentlyContinue) { $LlamaServer = $p; break }
        elseif (Test-Path $p) { $LlamaServer = $p; break }
    }
}

if (-not $LlamaServer -or -not (Test-Path $LlamaServer)) {
    Log "ERROR: llama-server.exe not found. Install llama.cpp or set -LlamaCppDir"
    Log "  git clone https://github.com/ggerganov/llama.cpp"
    Log "  cd llama.cpp && cmake -B build && cmake --build build --config Release"
    exit 1
}

Log "Using llama-server: $LlamaServer"

$Args = @(
    "-m", $ModelPath
    "--host", $Host
    "--port", $Port
    "--ctx-size", $CtxSize
    "-ngl", $NGpuLayers
    "--parallel", "2"
    "--batch-size", "512"
    "--ubatch-size", "512"
    "--no-mmap"
    "--mlock"
)

Log "Starting judge server on http://${Host}:${Port}..."
Log "Command: $LlamaServer $($Args -join ' ')"

$Process = Start-Process -FilePath $LlamaServer -ArgumentList $Args -NoNewWindow -PassThru -RedirectStandardOutput $LogFile -RedirectStandardError "${LogFile}.err"
$Process.Id | Out-File -FilePath $PidFile -Encoding ascii
Log "Judge server PID: $($Process.Id)"

# Wait for it to be ready
$ReadyUrl = "http://${Host}:${Port}/health"
Log "Waiting for server to become ready..."
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 2
    try {
        $Response = Invoke-WebRequest -Uri $ReadyUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($Response.StatusCode -eq 200) {
            Log "Judge server is READY at http://${Host}:${Port}"
            Log "Health check passed."
            exit 0
        }
    } catch {}
    if ($i % 10 -eq 0) { Log "  ... waiting ($($i*2)s)" }
}

Log "WARNING: Server may not be ready yet. Check logs: $LogFile"
