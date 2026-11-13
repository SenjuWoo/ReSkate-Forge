# One-time setup for an extracted Windows Forge. All paths resolve from this script.
$ErrorActionPreference = 'Stop'
$forgeRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $forgeRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonArgs = @('-3', '-m', 'reskateforge')
    $pythonCmd = 'py'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonArgs = @('-m', 'reskateforge')
    $pythonCmd = 'python'
} else {
    throw 'Python 3.10+ is required. Install Python, then rerun Setup-Forge.ps1.'
}

Write-Host "ReSkateForge: checking bundled tools and your installed software..."
& $pythonCmd @pythonArgs doctor
if ($LASTEXITCODE -ne 0) { throw 'Forge doctor did not run successfully.' }

$mcpScript = Join-Path $forgeRoot 'Forge-MCP.cmd'
$configDir = Join-Path $forgeRoot 'local-config'
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
$server = @{ command = 'cmd.exe'; args = @('/d', '/c', $mcpScript) }
$mcpConfig = @{ mcpServers = @{ reskateforge = $server } }
$mcpConfig | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $configDir 'mcp-servers.json') -Encoding UTF8

# Toml strings are escaped using quoted JSON-style strings, which TOML accepts.
$cmdPath = ($mcpScript | ConvertTo-Json -Compress)
$codexToml = "[mcp_servers.reskateforge]`ncommand = `"cmd.exe`"`nargs = [`"/d`", `"/c`", $cmdPath]`n"
Set-Content -LiteralPath (Join-Path $configDir 'codex-mcp.toml') -Value $codexToml -Encoding UTF8

Write-Host ''
Write-Host 'Forge is ready to run with Forge.cmd. Its Studio and compiler stay inside this folder.'
Write-Host 'AI connection examples generated in local-config (no app settings were overwritten).'
Write-Host "MCP entrypoint: $mcpScript"
Write-Host 'Sample: .\Forge.cmd plan "Replace my skater with Kitana"'
