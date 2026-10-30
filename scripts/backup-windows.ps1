param([string]$Database='bin_doul', [string]$DatabaseUser='postgres', [string]$DatabaseHost='127.0.0.1', [int]$DatabasePort=5432, [string]$BackupDirectory)
$ErrorActionPreference='Stop'
if (-not $BackupDirectory) { $BackupDirectory=Join-Path (Split-Path $PSScriptRoot -Parent) 'backups' }
New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
$backupFile=Join-Path $BackupDirectory ($Database+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.dump')
& pg_dump --host $DatabaseHost --port $DatabasePort --username $DatabaseUser --dbname $Database --format custom --file $backupFile
if ($LASTEXITCODE -ne 0) { throw 'Backup failed. Review pg_dump output.' }
Write-Host ('Backup created: '+$backupFile)
