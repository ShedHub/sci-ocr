param(
    [int]$Port = 8080,
    [int]$ContextSize = 4096,
    [int]$Threads = 16
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LlamaServer = Join-Path $ProjectRoot "local_tools\llama.cpp\llama-server.exe"
$ModelPath = Join-Path $ProjectRoot "models\vision\qwen3.6-27b\Qwen3.6-27B-Q4_K_M.gguf"
$MmprojPath = Join-Path $ProjectRoot "models\vision\qwen3.6-27b\mmproj-F16.gguf"

foreach ($Path in @($LlamaServer, $ModelPath, $MmprojPath)) {
    if (-not (Test-Path $Path)) {
        throw "Required file is missing: $Path"
    }
}

& $LlamaServer `
    -m $ModelPath `
    --mmproj $MmprojPath `
    --host 127.0.0.1 `
    --port $Port `
    -c $ContextSize `
    -t $Threads
