try {
    Write-Host "Checking Git Status..."
    git status
    Write-Host "`nRemote Config:"
    git remote -v
} catch {
    Write-Error "Git failed: $_"
}
