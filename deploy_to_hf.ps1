# Deploy to Hugging Face Spaces directly from local machine
# Usage: .\deploy_to_hf.ps1
# Requires: HF_TOKEN and HF_SPACE set as environment variables, or edit below

param(
    [string]$HfToken  = $env:HF_TOKEN,
    [string]$HfSpace  = $env:HF_SPACE    # e.g. "YourUsername/retail-ai"
)

if (-not $HfToken) { Write-Error "Set HF_TOKEN env var or pass -HfToken"; exit 1 }
if (-not $HfSpace) { Write-Error "Set HF_SPACE env var or pass -HfSpace"; exit 1 }

$ErrorActionPreference = "Stop"
$WorkDir = $PSScriptRoot
$TempDir = "$env:TEMP\hf-deploy-$(Get-Random)"

Write-Host "Deploying to HF Space: $HfSpace" -ForegroundColor Cyan

# Copy repo to temp dir (avoids polluting the working tree)
Write-Host "Copying source..." -ForegroundColor Gray
Copy-Item -Path $WorkDir -Destination $TempDir -Recurse -Force
Set-Location $TempDir

# Remove files HF Spaces doesn't need
$removePatterns = @("*.pt","*.onnx","*.jpg","*.jpeg","*.png","*.gif",
                    "*.docx","*.xlsx","*.pptx","*.ipynb","*.db","*.sqlite")
foreach ($pat in $removePatterns) {
    Get-ChildItem -Recurse -Filter $pat | Remove-Item -Force -ErrorAction SilentlyContinue
}
Remove-Item -Recurse -Force "$TempDir\sample_test_images" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$TempDir\training"            -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$TempDir\.git"                -ErrorAction SilentlyContinue

# Init a fresh git repo and push to HF
git init
git config user.email "deploy@retail-ai"
git config user.name  "Retail AI Deploy"
git add -A
$sha = git -C $WorkDir rev-parse --short HEAD 2>$null
git commit -m "deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm') -- $sha"

$remote = "https://user:${HfToken}@huggingface.co/spaces/$HfSpace"
git remote add hf $remote
git push hf main --force

Set-Location $WorkDir
Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Deployed successfully to https://huggingface.co/spaces/$HfSpace" -ForegroundColor Green
