$ErrorActionPreference = "Stop"
try {
    Write-Output "Starting environment fix..."
    $pythonPath = "C:\Users\HP\AppData\Local\Programs\Python\Python312\python.exe"
    if (-not (Test-Path $pythonPath)) {
        Write-Error "Python 3.12 not found at $pythonPath"
    }
    
    Write-Output "Creating venv_312..."
    & $pythonPath -m venv venv_312
    
    Write-Output "Installing requirements..."
    & .\venv_312\Scripts\pip.exe install -r requirements.txt
    
    Write-Output "Successfully finished environment setup."
} catch {
    Write-Error "Failed to setup environment: $_"
}
