#!/usr/bin/env pwsh
# Force clear frontend build cache and restart

$frontendDir = "c:\Users\atuls\Startup\Trade Options\01 Figma"

Write-Host "Clearing frontend build cache..." -ForegroundColor Yellow

# Remove cache directories
Remove-Item "$frontendDir\.next" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$frontendDir\.vite" -Recurse -Force -ErrorAction SilentlyContinue  
Remove-Item "$frontendDir\dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$frontendDir\node_modules\.cache" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "✓ Cache cleared!" -ForegroundColor Green
Write-Host ""
Write-Host "Now restart your frontend dev server and refresh the browser (Ctrl+Shift+R)" -ForegroundColor Cyan
