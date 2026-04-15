# 道法自然 · 双机 Windsurf 对话备份同步
# 将本机最新 dao_autosave.py / proto_utils.py 推送至 179 笔记本
# 并验证/重启 179 上的计划任务守护进程
#
# 用法: .\→双机同步.ps1 [-Force] [-Status]

param(
    [switch]$Force,
    [switch]$Status
)

$ErrorActionPreference = 'SilentlyContinue'
$REMOTE_IP    = "192.168.31.179"
$LOCAL_ROOT   = Split-Path $PSScriptRoot -Parent
$TRACKER      = "$LOCAL_ROOT\Windsurf万法归宗\对话追踪"
$REMOTE_DIR   = "D:\dao_autosave"
$TASK_NAME    = "道之永存_Windsurf对话自动备份"
$PYTHON_179   = "C:\Program Files\Python311\python.exe"

chcp 65001 | Out-Null
Write-Host ""
Write-Host "══════════════════════════════════" -ForegroundColor Cyan
Write-Host "  道法自然 · 双机 Windsurf 对话备份同步" -ForegroundColor Cyan
Write-Host "  本机 <-> 笔记本 $REMOTE_IP"           -ForegroundColor Cyan
Write-Host "══════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$ping = Test-Connection $REMOTE_IP -Count 1 -ErrorAction SilentlyContinue
if (-not $ping) {
    Write-Host "[X] 无法连接 $REMOTE_IP" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] 网络连通: $REMOTE_IP" -ForegroundColor Green

$autosave_path = "$TRACKER\dao_autosave.py"
if (-not (Test-Path $autosave_path)) {
    Write-Host "[X] 找不到本机 dao_autosave.py" -ForegroundColor Red
    exit 1
}
$local_mtime = (Get-Item $autosave_path).LastWriteTime
Write-Host "[本机] dao_autosave.py 修改时间: $local_mtime" -ForegroundColor Gray

$remote_info = Invoke-Command -ComputerName $REMOTE_IP -ScriptBlock {
    param($rdir, $tname)
    $mtime = if (Test-Path "$rdir\dao_autosave.py") { (Get-Item "$rdir\dao_autosave.py").LastWriteTime } else { $null }
    $task  = Get-ScheduledTask $tname -ErrorAction SilentlyContinue
    $procs = (Get-Process python -ErrorAction SilentlyContinue).Count
    $count = (Get-ChildItem "$rdir\永存\2026-04" -Directory -ErrorAction SilentlyContinue).Count
    @{mtime=$mtime; task_state=$task.State; procs=$procs; conv_count=$count}
} -ArgumentList $REMOTE_DIR,$TASK_NAME -ErrorAction SilentlyContinue

if (-not $remote_info) {
    Write-Host "[X] WinRM 连接失败" -ForegroundColor Red
    exit 1
}

Write-Host "[179] 脚本修改时间: $($remote_info.mtime)" -ForegroundColor Gray
Write-Host "[179] 计划任务: $($remote_info.task_state)" -ForegroundColor Gray
Write-Host "[179] Python进程: $($remote_info.procs)" -ForegroundColor Gray
Write-Host "[179] 已备份对话: $($remote_info.conv_count)" -ForegroundColor Gray

if ($Status) { exit 0 }

$need_sync = $Force -or ($remote_info.mtime -eq $null) -or ($local_mtime -gt $remote_info.mtime)
if (-not $need_sync) {
    Write-Host "[OK] 远程脚本已是最新" -ForegroundColor Green
} else {
    Write-Host "[->] 同步脚本..." -ForegroundColor Yellow
    $as = [System.IO.File]::ReadAllText($autosave_path, [System.Text.Encoding]::UTF8)
    $proto_path = "$TRACKER\proto_utils.py"
    $pu = if (Test-Path $proto_path) { [System.IO.File]::ReadAllText($proto_path, [System.Text.Encoding]::UTF8) } else { "" }
    Invoke-Command -ComputerName $REMOTE_IP -ScriptBlock {
        param($as, $pu, $dir)
        New-Item -Path $dir -ItemType Directory -Force | Out-Null
        [System.IO.File]::WriteAllText("$dir\dao_autosave.py", $as, [System.Text.Encoding]::UTF8)
        if ($pu) { [System.IO.File]::WriteAllText("$dir\proto_utils.py", $pu, [System.Text.Encoding]::UTF8) }
    } -ArgumentList $as,$pu,$REMOTE_DIR -ErrorAction Stop
    Write-Host "[OK] 脚本同步完成" -ForegroundColor Green
}

Invoke-Command -ComputerName $REMOTE_IP -ScriptBlock {
    param($python, $script_dir, $tname)
    $script   = "$script_dir\dao_autosave.py"
    $existing = Get-ScheduledTask $tname -ErrorAction SilentlyContinue
    if (-not $existing) {
        $action   = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $script_dir
        $triggers = @((New-ScheduledTaskTrigger -AtStartup),(New-ScheduledTaskTrigger -AtLogOn))
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $tname -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
        echo "TASK_CREATED"
    } else { echo "TASK_EXISTS state=$($existing.State)" }
    $running = (Get-Process python -ErrorAction SilentlyContinue).Count
    if ($running -eq 0) {
        Start-ScheduledTask $tname -ErrorAction SilentlyContinue
        Start-Sleep 3
        echo "STARTED procs=$((Get-Process python -ErrorAction SilentlyContinue).Count)"
    } else { echo "DAEMON_RUNNING procs=$running" }
} -ArgumentList $PYTHON_179,$REMOTE_DIR,$TASK_NAME

Write-Host ""
Write-Host "[OK] 双机同步完成" -ForegroundColor Green
