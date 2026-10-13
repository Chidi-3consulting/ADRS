[CmdletBinding()]
param(
    [int]$IconMinIndex,
    [int]$IconMaxIndex,
    [string]$UndoFile
)

$ErrorActionPreference = "Stop"
$iconFolder = Join-Path $PSScriptRoot "Assets\ICO"
$iconCatalog = @(
    [pscustomobject]@{ Index = 1; Key = "lifecycle"; Label = "Lifecycle"; Keywords = @("retention", "lifecycle", "schedule", "expiry", "expire", "disposal", "delete", "review", "timer", "purge", "data-retention") }
    [pscustomobject]@{ Index = 2; Key = "policy"; Label = "Retention Policy"; Keywords = @("policy", "policies", "rule", "rules", "category", "categories", "compliance", "jurisdiction", "gdpr", "ndpr", "ndpa", "popia", "ccpa", "retention-policy") }
    [pscustomobject]@{ Index = 3; Key = "records"; Label = "Records"; Keywords = @("record", "records", "inventory", "register", "database", "csv", "import", "archive", "attachment", "data-owner") }
    [pscustomobject]@{ Index = 4; Key = "consent"; Label = "Consent"; Keywords = @("consent", "purpose", "notice", "preference", "withdrawal", "receipt", "opt-in", "opt-out") }
    [pscustomobject]@{ Index = 5; Key = "rights"; Label = "Data Rights"; Keywords = @("dsar", "request", "subject", "access", "erasure", "rectification", "portability", "rights", "privacy", "individual") }
    [pscustomobject]@{ Index = 6; Key = "audit"; Label = "Audit Evidence"; Keywords = @("audit", "evidence", "report", "reports", "ledger", "history", "hash", "verification", "verify", "incident", "breach") }
    [pscustomobject]@{ Index = 7; Key = "integrations"; Label = "Integrations"; Keywords = @("api", "integration", "integrations", "webhook", "dispatch", "crm", "erp", "banking", "queue", "key", "keys", "system") }
    [pscustomobject]@{ Index = 8; Key = "governance"; Label = "Governance"; Keywords = @("governance", "ropa", "processor", "vendor", "vendors", "dpia", "risk", "legal", "hold", "freeze", "officer", "organization") }
)
$excludedDirectoryNames = @(".git", ".venv", "venv", "node_modules", "storage", "backups", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build")

function Show-FolderPicker([string]$Description) {
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = $Description
    $dialog.ShowNewFolderButton = $false
    try {
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            return $dialog.SelectedPath
        }
        return $null
    }
    finally {
        $dialog.Dispose()
    }
}

function Get-FeatureTokens([string]$Text) {
    return @([regex]::Matches($Text.ToLowerInvariant(), "[a-z0-9]+") | ForEach-Object { $_.Value })
}

function Get-FeatureScores([string]$TargetText, [string[]]$SolutionTokens, [object[]]$Choices) {
    $targetTokens = Get-FeatureTokens $TargetText
    $scores = @{}
    foreach ($choice in $Choices) {
        $score = 0
        foreach ($keyword in $choice.Keywords) {
            if ($targetTokens -contains $keyword) {
                $score += 12
            }
            elseif ($TargetText.IndexOf($keyword, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $score += 6
            }
            if ($SolutionTokens -contains $keyword) {
                $score += 1
            }
        }
        $scores[[int]$choice.Index] = $score
    }
    return $scores
}

function Get-OptimalDistinctGroup([object[]]$Items, [object[]]$Choices, [int]$Limit) {
    $assigned = @()
    $indices = @($Choices | ForEach-Object { [int]$_.Index })
    foreach ($item in $Items) {
        $assigned += [pscustomobject]@{
            Item = $item
            Candidates = @($indices)
        }
    }
    $count = $assigned.Count
    if ($count -eq 0) {
        return @()
    }
    $columns = $indices.Count
    if ($count -gt $columns) {
        throw "Internal error: distinct assignment group is larger than the chosen icon range."
    }

    $u = New-Object 'double[]' ($count + 1)
    $v = New-Object 'double[]' ($columns + 1)
    $p = New-Object 'int[]' ($columns + 1)
    $way = New-Object 'int[]' ($columns + 1)

    for ($row = 1; $row -le $count; $row++) {
        $p[0] = $row
        $column0 = 0
        $minValues = New-Object 'double[]' ($columns + 1)
        for ($j = 0; $j -le $columns; $j++) { $minValues[$j] = [double]::PositiveInfinity }
        $used = New-Object 'bool[]' ($columns + 1)
        do {
            $used[$column0] = $true
            $row0 = $p[$column0]
            $delta = [double]::PositiveInfinity
            $column1 = 0
            for ($column = 1; $column -le $columns; $column++) {
                if (-not $used[$column]) {
                    $iconIndex = $indices[$column - 1]
                    $baseScore = [double]$assigned[$row0 - 1].Item.Scores[$iconIndex]
                    $cost = -$baseScore - [double]$script:randomScores[$row0 - 1][$iconIndex]
                    $current = $cost - $u[$row0] - $v[$column]
                    if ($current -lt $minValues[$column]) {
                        $minValues[$column] = $current
                        $way[$column] = $column0
                    }
                    if ($minValues[$column] -lt $delta) {
                        $delta = $minValues[$column]
                        $column1 = $column
                    }
                }
            }
            for ($column = 0; $column -le $columns; $column++) {
                if ($used[$column]) {
                    $u[$p[$column]] += $delta
                    $v[$column] -= $delta
                }
                else {
                    $minValues[$column] -= $delta
                }
            }
            $column0 = $column1
        } while ($p[$column0] -ne 0)

        do {
            $column1 = $way[$column0]
            $p[$column0] = $p[$column1]
            $column0 = $column1
        } while ($column0 -ne 0)
    }

    $result = @()
    for ($column = 1; $column -le $columns; $column++) {
        if ($p[$column] -gt 0) {
            $row = $p[$column] - 1
            $iconIndex = $indices[$column - 1]
            $result += [pscustomobject]@{
                Item = $assigned[$row].Item
                IconIndex = $iconIndex
            }
        }
    }
    return $result
}

function Restore-PreviousIcons([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Undo file not found: $Path"
    }
    $shell = New-Object -ComObject WScript.Shell
    $rows = @(Import-Csv -LiteralPath $Path)
    $restored = 0
    foreach ($row in $rows) {
        if (-not (Test-Path -LiteralPath $row.ShortcutPath -PathType Leaf)) {
            Write-Warning "Shortcut no longer exists; skipped: $($row.ShortcutPath)"
            continue
        }
        $link = $shell.CreateShortcut($row.ShortcutPath)
        $link.IconLocation = [string]$row.PreviousIconLocation
        $link.Save()
        $restored++
    }
    Write-Host "Restored $restored shortcut icon(s)."
}

if ($UndoFile) {
    Add-Type -AssemblyName System.Windows.Forms
    Restore-PreviousIcons $UndoFile
    return
}

if (-not (Test-Path -LiteralPath $iconFolder -PathType Container)) {
    throw "Brand icons are missing. Run Build-SafeDataBrand.ps1 first. Expected: $iconFolder"
}
Add-Type -AssemblyName System.Windows.Forms

$available = @($iconCatalog | Where-Object {
    Test-Path -LiteralPath (Join-Path $iconFolder ("SafeData-{0:D2}-{1}.ico" -f $_.Index, $_.Key))
})
if ($available.Count -ne $iconCatalog.Count) {
    throw "Some logo files are missing. Run Build-SafeDataBrand.ps1 first."
}

$solutionFolder = Show-FolderPicker "Select the SafeData solution folder (for example, the repository or your SafeData install folder)."
if (-not $solutionFolder) {
    Write-Host "Cancelled without changing any shortcuts."
    return
}
$solutionNames = @()
foreach ($entry in @(Get-ChildItem -LiteralPath $solutionFolder -Force -ErrorAction Stop | Where-Object {
    $_.Name -notin $excludedDirectoryNames
} | Select-Object -First 250)) {
    $solutionNames += $entry.Name
}
$solutionTokens = Get-FeatureTokens ($solutionFolder + " " + ($solutionNames -join " "))

$targetFolders = @()
do {
    $targetFolder = Show-FolderPicker "Select a folder containing Windows shortcuts (.lnk) to brand."
    if (-not $targetFolder) {
        break
    }
    if ($targetFolders -notcontains $targetFolder) {
        $targetFolders += $targetFolder
    }
    $again = [System.Windows.Forms.MessageBox]::Show(
        "Add another folder of shortcuts?",
        "SafeData Icon Picker",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
} while ($again -eq [System.Windows.Forms.DialogResult]::Yes)

if ($targetFolders.Count -eq 0) {
    Write-Host "No shortcut folders selected. Nothing was changed."
    return
}

if ($PSBoundParameters.ContainsKey("IconMinIndex") -and $PSBoundParameters.ContainsKey("IconMaxIndex")) {
    $minimum = $IconMinIndex
    $maximum = $IconMaxIndex
}
else {
    $range = Read-Host "Choose the icon-number range 1-8 (for example, 2-6). Press Enter for 1-8"
    if ([string]::IsNullOrWhiteSpace($range)) {
        $minimum = 1
        $maximum = 8
    }
    elseif ($range -match '^\s*(\d+)\s*[-,]\s*(\d+)\s*$') {
        $minimum = [int]$Matches[1]
        $maximum = [int]$Matches[2]
    }
    else {
        throw "Enter a range such as 1-8 or 3-6."
    }
}

if ($minimum -lt 1 -or $maximum -gt 8 -or $minimum -gt $maximum) {
    throw "The icon range must be between 1 and 8, with the minimum no greater than the maximum."
}
$choices = @($available | Where-Object { $_.Index -ge $minimum -and $_.Index -le $maximum })

$shortcutPaths = @()
foreach ($folder in $targetFolders) {
    $shortcutPaths += @(Get-ChildItem -LiteralPath $folder -Filter "*.lnk" -File -Recurse -ErrorAction Stop |
        Select-Object -ExpandProperty FullName)
}
$shortcutPaths = @($shortcutPaths | Sort-Object -Unique)
if ($shortcutPaths.Count -eq 0) {
    Write-Host "No .lnk shortcuts were found in the selected folders. Nothing was changed."
    return
}

$shell = New-Object -ComObject WScript.Shell
$random = New-Object System.Random
$items = @()
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $targetText = ($shortcutPath + " " + $shortcut.TargetPath + " " + $shortcut.Arguments)
    $items += [pscustomobject]@{
        ShortcutPath = $shortcutPath
        Name = [System.IO.Path]::GetFileNameWithoutExtension($shortcutPath)
        TargetPath = [string]$shortcut.TargetPath
        PreviousIconLocation = [string]$shortcut.IconLocation
        Scores = (Get-FeatureScores $targetText $solutionTokens $choices)
    }
}

$ranked = @($items | ForEach-Object {
    $bestScore = [int]($_.Scores.Values | Measure-Object -Maximum).Maximum
    [pscustomobject]@{ Item = $_; BestScore = $bestScore; TieBreak = $random.Next() }
} | Sort-Object @{Expression = "BestScore"; Descending = $true }, @{Expression = "TieBreak"; Descending = $true })

$assignments = @()
$randomScores = @()
$groupSize = $choices.Count
for ($start = 0; $start -lt $ranked.Count; $start += $groupSize) {
    $group = @($ranked[$start..([math]::Min($start + $groupSize - 1, $ranked.Count - 1))] |
        ForEach-Object { $_.Item })
    for ($row = 0; $row -lt $group.Count; $row++) {
        $rowScores = @{}
        foreach ($choice in $choices) {
            $rowScores[[int]$choice.Index] = $random.Next(0, 5)
        }
        $randomScores += ,$rowScores
    }
    $script:randomScores = $randomScores
    $assignments += @(Get-OptimalDistinctGroup $group $choices $groupSize)
}

$plan = @($assignments | ForEach-Object {
    $choice = $available | Where-Object { $_.Index -eq $_.IconIndex } | Select-Object -First 1
    $icoName = "SafeData-{0:D2}-{1}.ico" -f $_.IconIndex, ($available | Where-Object { $_.Index -eq $_.IconIndex } | Select-Object -ExpandProperty Key -First 1)
    [pscustomobject]@{
        ShortcutPath = $_.Item.ShortcutPath
        Name = $_.Item.Name
        IconIndex = $_.IconIndex
        IconLabel = ($available | Where-Object { $_.Index -eq $_.IconIndex } | Select-Object -ExpandProperty Label -First 1)
        IconPath = Join-Path $iconFolder $icoName
        PreviousIconLocation = $_.Item.PreviousIconLocation
    }
})

Write-Host ""
Write-Host "SafeData shortcut icon preview (nothing has been changed yet):"
$plan | Format-Table Name, IconIndex, IconLabel, IconPath -AutoSize | Out-Host
Write-Host ("Shortcuts found: {0}; distinct icon designs in range: {1}; selected solution folder: {2}" -f $plan.Count, $choices.Count, $solutionFolder)
$confirmation = Read-Host "Type APPLY to change only these shortcuts' icon locations"
if ($confirmation -cne "APPLY") {
    Write-Host "Cancelled without changing any shortcuts."
    return
}

$stateFolder = Join-Path $env:LOCALAPPDATA "SafeDataIconPicker"
[System.IO.Directory]::CreateDirectory($stateFolder) | Out-Null
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$undoPath = Join-Path $stateFolder "undo-$runId.csv"
$undoRows = @()
$applied = 0
try {
    foreach ($entry in $plan) {
        $link = $shell.CreateShortcut($entry.ShortcutPath)
        $undoRows += [pscustomobject]@{
            ShortcutPath = $entry.ShortcutPath
            PreviousIconLocation = $link.IconLocation
            NewIconPath = $entry.IconPath
            IconIndex = $entry.IconIndex
        }
        $link.IconLocation = "$($entry.IconPath),0"
        $link.Save()
        $applied++
    }
}
catch {
    foreach ($row in $undoRows) {
        try {
            $link = $shell.CreateShortcut($row.ShortcutPath)
            $link.IconLocation = [string]$row.PreviousIconLocation
            $link.Save()
        }
        catch {
            Write-Warning "Could not restore shortcut after an error: $($row.ShortcutPath) — $($_.Exception.Message)"
        }
    }
    throw "Shortcut update failed; previous icon locations were restored where possible. $($_.Exception.Message)"
}

$undoRows | Export-Csv -LiteralPath $undoPath -NoTypeInformation -Encoding UTF8
Write-Host ""
Write-Host "Applied SafeData icons to $applied shortcut(s). No files were moved, renamed, or deleted."
Write-Host "To undo, run: .\Run-SafeDataIconPicker.ps1 -UndoFile `"$undoPath`""
