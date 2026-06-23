param(
    [string]$ConfigFile = "../config/pipeline.yaml",
    [int]$MaxBuilds = -1,
    [int]$MaxRetriesPerTask = 2,
    [switch]$NoJudge,
    [string]$TaskFilter = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path "$ScriptDir/.."
$DataDir = "$RootDir/data"

# Ensure directories exist
@("$DataDir/trajectories", "$DataDir/evaluations", "$DataDir/dpo_pairs",
  "$RootDir/build_workspaces") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

$RunId = "run_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$StatsFile = "$DataDir/stats_$RunId.json"

function Log { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Msg" }
function LogWarn { param([string]$Msg) Write-Host "[WARN] $Msg" -ForegroundColor Yellow }
function LogOk { param([string]$Msg) Write-Host "[OK] $Msg" -ForegroundColor Green }
function LogErr { param([string]$Msg) Write-Host "[ERR] $Msg" -ForegroundColor Red }

# Stats accumulator
$Stats = @{
    run_id = $RunId
    started_at = (Get-Date -Format 'o')
    total_builds = 0
    passed = 0
    failed = 0
    errors = 0
    retries = 0
    total_score = 0.0
    tasks_by_stack = @{}
}

function Save-Stats {
    $Stats.stats_file = $StatsFile
    $Stats | ConvertTo-Json -Depth 10 | Set-Content -Path $StatsFile -Encoding utf8
}

# --- Load tasks ---
function Load-Tasks {
    param([string]$Filter = "", [string[]]$TaskFiles)
    $AllTasks = @()
    foreach ($File in $TaskFiles) {
        $FullPath = if ([System.IO.Path]::IsPathRooted($File)) { $File } else { Join-Path $RootDir $File }
        if (-not (Test-Path $FullPath)) { LogWarn "Task file not found: $FullPath"; continue }
        $Content = Get-Content $FullPath -Encoding utf8 -ErrorAction SilentlyContinue
        foreach ($Line in $Content) {
            if ([string]::IsNullOrWhiteSpace($Line)) { continue }
            try {
                $Task = $Line | ConvertFrom-Json
                if ($Filter -and $Task.stack -notmatch $Filter) { continue }
                $AllTasks += $Task
            } catch {
                LogWarn "Skipping invalid JSON line in $File : $_"
            }
        }
    }
    if ($AllTasks.Count -eq 0) {
        LogErr "No tasks loaded. Check task files."
        exit 1
    }
    # Shuffle tasks for variety
    $Rng = [Random]::new()
    $AllTasks = $AllTasks | Sort-Object { $Rng.Next() }
    LogOk "Loaded $($AllTasks.Count) tasks"
    return $AllTasks
}

# --- Run a single build ---
function Invoke-Build {
    param(
        [pscustomobject]$Task,
        [string]$WorkspaceDir,
        [string]$BuildId
    )

    $TaskDir = Join-Path $WorkspaceDir $BuildId
    New-Item -ItemType Directory -Path $TaskDir -Force | Out-Null
    $TrajectoryFile = "$DataDir/trajectories/${BuildId}.json"
    $JudgeOutputFile = "$DataDir/evaluations/${BuildId}.json"

    Log "  Workspace: $TaskDir"
    Log "  Starting build (using opencode with coder model)..."

    # Build the opencode command
    $OpenCodeCmd = @(
        "opencode"
        "--config", (Join-Path $RootDir "config/opencode.json")
        "--no-auto-commits"
        "--yes"
        $Task.task
    )

    $TrajectorySteps = @()
    $StartTime = Get-Date

    # Run opencode and capture all output
    $LogFile = "$DataDir/trajectories/${BuildId}_raw.log"
    try {
        # Run with timeout (1 hour per build)
        $Proc = Start-Process -FilePath "opencode" -ArgumentList @(
            "--config", (Join-Path $RootDir "config/opencode.json"),
            "--no-auto-commits",
            "--yes",
            $Task.task
        ) -WorkingDirectory $TaskDir -NoNewWindow -PassThru -RedirectStandardOutput $LogFile -RedirectStandardError "${LogFile}.err"

        $TimeoutMinutes = 120
        $Completed = $Proc.WaitForExit($TimeoutMinutes * 60 * 1000)
        if (-not $Completed) {
            LogWarn "  Build timed out after ${TimeoutMinutes}min, killing..."
            Stop-Process -Id $Proc.Id -Force
            $ExitCode = -1
        } else {
            $ExitCode = $Proc.ExitCode
        }
    } catch {
        LogErr "  Failed to launch opencode: $_"
        return $null, "Launch error: $_"
    }

    $Duration = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)
    $RawLog = ""
    if (Test-Path $LogFile) { $RawLog = Get-Content $LogFile -Raw -ErrorAction SilentlyContinue }

    Log "  Build completed (exit=$ExitCode, duration=${Duration}s)"

    # Build build_output from log
    $BuildOutput = if ($RawLog) { $RawLog[-2000..-1] -join '' } else { "(no output)" }

    # Collect final state of workspace files
    $FilesSnapshot = @{}
    if (Test-Path $TaskDir) {
        Get-ChildItem $TaskDir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch '^\.' } |
            Select-Object -First 50 | ForEach-Object {
                $Rel = $_.FullName.Substring($TaskDir.Length + 1)
                try {
                    $Content = Get-Content $_.FullName -Raw -Encoding utf8 -ErrorAction SilentlyContinue
                    $FilesSnapshot[$Rel] = $Content
                } catch { $FilesSnapshot[$Rel] = "[read error]" }
            }
    }

    # Build trajectory object
    $Trajectory = @{
        id = $BuildId
        task_id = $Task.id
        task = $Task.task
        task_description = $Task.description
        stack = $Task.stack
        difficulty = $Task.difficulty
        workspace_dir = $TaskDir
        started_at = $StartTime.ToString("o")
        duration_seconds = $Duration
        exit_code = $ExitCode
        raw_log = $RawLog
        build_output = $BuildOutput
        workspace_files = $FilesSnapshot
        steps = @(
            @{
                step = 1
                action = "run_opencode"
                action_input = $Task.task
                observation = "Exit code: $ExitCode, Duration: ${Duration}s"
            }
        )
    }

    # Save trajectory
    $Trajectory | ConvertTo-Json -Depth 10 | Set-Content -Path $TrajectoryFile -Encoding utf8
    LogOk "  Trajectory saved: $TrajectoryFile"

    return $Trajectory, $BuildOutput
}

# --- Evaluate with judge ---
function Invoke-Judge {
    param(
        [hashtable]$Trajectory,
        [string]$TrajectoryFile,
        [string]$BuildId
    )

    $JudgeOutputFile = "$DataDir/evaluations/${BuildId}.json"
    Log "  Evaluating with judge..."

    try {
        $JudgeResult = python (Join-Path $ScriptDir "judge_eval.py") `
            --trajectory $TrajectoryFile `
            --workspace $Trajectory.workspace_dir `
            --output $JudgeOutputFile 2>&1

        if ($LASTEXITCODE -ne 0) {
            LogWarn "  judge_eval.py failed: $JudgeResult"
            return $null
        }

        # Parse result from stdout
        $Result = $JudgeResult | Out-String | ConvertFrom-Json
        LogOk "  Judge score: $($Result.overall)/10 - $($Result.summary)"
        return $Result
    } catch {
        LogErr "  Judge evaluation error: $_"
        return $null
    }
}

# --- Main loop ---
function Main {
    # Collect task files from config or use defaults
    $TaskFiles = @(
        (Join-Path $RootDir "tasks/react.jsonl"),
        (Join-Path $RootDir "tasks/node.jsonl"),
        (Join-Path $RootDir "tasks/python.jsonl"),
        (Join-Path $RootDir "tasks/ml.jsonl")
    )

    $AllTasks = Load-Tasks -Filter $TaskFilter -TaskFiles $TaskFiles
    $TaskQueue = [System.Collections.Queue]::new()
    $AllTasks | ForEach-Object { $TaskQueue.Enqueue($_) }

    $BuildCount = 0
    $CycleCount = 0

    Log "=============================================="
    Log " Agentic Fine-Tuning Data Collection Pipeline"
    Log " Run ID: $RunId"
    Log " Tasks loaded: $($AllTasks.Count)"
    Log " Will run continuously. Press Ctrl+C to stop."
    Log "=============================================="

    Save-Stats

    while ($true) {
        if ($MaxBuilds -gt 0 -and $BuildCount -ge $MaxBuilds) {
            Log "Reached max builds ($MaxBuilds). Stopping."
            break
        }

        # Replenish queue if empty
        if ($TaskQueue.Count -eq 0) {
            $CycleCount++
            Log "--- Starting cycle $CycleCount (reshuffling tasks) ---"
            $Shuffled = $AllTasks | Sort-Object { Get-Random }
            $Shuffled | ForEach-Object { $TaskQueue.Enqueue($_) }
        }

        $Task = $TaskQueue.Dequeue()
        $BuildId = "${RunId}_build_$(Get-Date -Format 'yyyyMMdd_HHmmss')_$($Task.id)"
        $BuildCount++
        $Stats.total_builds = $BuildCount

        # Track by stack
        $Stack = $Task.stack
        if (-not $Stats.tasks_by_stack[$Stack]) { $Stats.tasks_by_stack[$Stack] = 0 }
        $Stats.tasks_by_stack[$Stack]++

        $StackInfo = if ($Stack) { "[$Stack] " } else { "" }
        Log ""
        Log "--- Build #$BuildCount: ${StackInfo}$($Task.task) ---"
        Log "  Difficulty: $($Task.difficulty)"

        $Attempt = 0
        $Succeeded = $false
        while ($Attempt -le $MaxRetriesPerTask -and -not $Succeeded) {
            if ($Attempt -gt 0) {
                $Stats.retries++
                Log "  Retry attempt $Attempt/$MaxRetriesPerTask..."
            }
            $Attempt++

            $Trajectory, $BuildOutput = Invoke-Build -Task $Task -WorkspaceDir "$RootDir/build_workspaces" -BuildId $BuildId
            if (-not $Trajectory) {
                $Stats.errors++
                LogErr "  Build failed to start"
                continue
            }

            if (-not $NoJudge) {
                $JudgeResult = Invoke-Judge -Trajectory $Trajectory -TrajectoryFile "$DataDir/trajectories/${BuildId}.json" -BuildId $BuildId
                if ($JudgeResult) {
                    $Score = [float]$JudgeResult.overall
                    $Stats.total_score += $Score

                    if ($JudgeResult.passed -or $Score -ge 6.0) {
                        $Stats.passed++
                        $Succeeded = $true
                        LogOk "  PASSED (score: $Score)"

                        # Save as DPO good pair candidate
                        if ($Score -ge 8.0) {
                            $DpoDir = "$DataDir/dpo_pairs/good"
                            New-Item -ItemType Directory -Path $DpoDir -Force | Out-Null
                            Copy-Item "$DataDir/trajectories/${BuildId}.json" "$DpoDir/${BuildId}.json" -Force
                        }
                    } else {
                        $Stats.failed++
                        LogWarn "  FAILED (score: $Score)"

                        # Save as DPO bad pair candidate on final attempt
                        if ($Attempt -gt $MaxRetriesPerTask -or $Score -lt 4.0) {
                            $DpoDir = "$DataDir/dpo_pairs/bad"
                            New-Item -ItemType Directory -Path $DpoDir -Force | Out-Null
                            Copy-Item "$DataDir/trajectories/${BuildId}.json" "$DpoDir/${BuildId}.json" -Force
                        }
                    }

                    # Log a summary line
                    Log "  Result: $($JudgeResult.summary)"
                }
            } else {
                $Succeeded = $true
            }
        }

        Save-Stats

        # Short pause between builds
        Start-Sleep -Seconds 5
    }

    Log "=============================================="
    Log " Pipeline finished."
    Log " Total builds: $($Stats.total_builds)"
    Log " Passed: $($Stats.passed)"
    Log " Failed: $($Stats.failed)"
    Log " Retries: $($Stats.retries)"
    $Avg = if ($Stats.passed -gt 0) { [math]::Round($Stats.total_score / ($Stats.passed + $Stats.failed), 2) } else { 0 }
    Log " Avg score: $Avg"
    Log " Stats: $StatsFile"
    Log "=============================================="
}

Main
