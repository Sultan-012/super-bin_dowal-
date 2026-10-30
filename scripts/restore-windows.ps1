param([Parameter(Mandatory=$true)][string]$BackupFile,[Parameter(Mandatory=$true)][string]$TargetDatabase,[string]$DatabaseUser='postgres',[string]$DatabaseHost='127.0.0.1',[int]$DatabasePort=5432)
$ErrorActionPreference='Stop'
if ($TargetDatabase -notmatch '^bin_doul_restore[a-zA-Z0-9_]*$') { throw 'Restore to a NEW database named bin_doul_restore..., never over operational data.' }
if (-not (Test-Path $BackupFile)) { throw 'Backup file not found.' }
& createdb --host $DatabaseHost --port $DatabasePort --username $DatabaseUser $TargetDatabase
if ($LASTEXITCODE -ne 0) { throw 'Target must be a new database; restore aborted.' }
& pg_restore --host $DatabaseHost --port $DatabasePort --username $DatabaseUser --dbname $TargetDatabase --no-owner --exit-on-error $BackupFile
if ($LASTEXITCODE -ne 0) { throw 'Restore failed. Keep the original database unchanged.' }
$holdScript=Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\after-restore-hold-notifications.sql'
& psql --host $DatabaseHost --port $DatabasePort --username $DatabaseUser --dbname $TargetDatabase --set ON_ERROR_STOP=1 --file $holdScript
if ($LASTEXITCODE -ne 0) { throw 'Restore completed but post-restore notification hold failed. Keep n8n disabled.' }
Write-Host 'Restored to a separate database. Check totals and permissions before changing DATABASE_URL.'
