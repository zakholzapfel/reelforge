$ErrorActionPreference = 'Stop'
$destination = Join-Path $PSScriptRoot '../build/webview2/MicrosoftEdgeWebview2Setup.exe'
New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $destination
$signature = Get-AuthenticodeSignature $destination
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*CN=Microsoft Corporation,*') {
    Remove-Item $destination
    throw 'WebView2 bootstrapper did not have a valid Microsoft signature.'
}
Write-Host 'Verified Microsoft WebView2 bootstrapper.'
