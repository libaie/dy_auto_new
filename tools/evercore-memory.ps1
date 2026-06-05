param(
    [Parameter(Position = 0)]
    [ValidateSet("health", "save", "search", "flush", "help")]
    [string]$Command = "help",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Text,

    [string]$BaseUrl = $env:EVERCORE_BASE_URL,
    [string]$GroupId = $env:EVERCORE_GROUP_ID,
    [string]$SenderId = $env:EVERCORE_SENDER_ID,
    [ValidateRange(1, 100)]
    [int]$TopK = 5,
    [ValidateSet("keyword", "vector", "hybrid", "agentic")]
    [string]$Method = "keyword"
)

$ErrorActionPreference = "Stop"
$RawMessageFetchLimit = 100

function Get-Sha256Hex {
    param([string]$Value)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        return [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-CurrentProjectGroupId {
    $path = (Get-Location).Path
    $hash = (Get-Sha256Hex $path).Substring(0, 16)
    return "codex_$hash"
}

function Get-CurrentProjectLabel {
    $leaf = Split-Path -Leaf (Get-Location).Path
    if ([string]::IsNullOrWhiteSpace($leaf)) {
        return "workspace"
    }
    return $leaf
}

function Join-Text {
    param([string[]]$Parts)

    return (($Parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join " ").Trim()
}

function New-StableMessageId {
    param(
        [string]$Content,
        [long]$Timestamp
    )

    $hash = (Get-Sha256Hex "$GroupId|$SenderId|$Content|$Timestamp").Substring(0, 24)
    return "codex_msg_$hash"
}

function Get-ErrorResponseBody {
    param($ErrorRecord)

    if ($ErrorRecord.ErrorDetails -and -not [string]::IsNullOrWhiteSpace($ErrorRecord.ErrorDetails.Message)) {
        return $ErrorRecord.ErrorDetails.Message
    }

    $response = $ErrorRecord.Exception.Response
    if ($null -eq $response) {
        return $null
    }

    try {
        $stream = $response.GetResponseStream()
        if ($null -eq $stream) {
            return $null
        }

        $reader = New-Object System.IO.StreamReader($stream)
        try {
            return $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
    } catch {
        return $null
    }
}

function Write-Stderr {
    param([string]$Message)
    [Console]::Error.WriteLine($Message)
}

function Write-EverCoreFailure {
    param(
        [object]$Failure,
        [switch]$ProviderHint
    )

    Write-Stderr ("EverCore request failed: {0} {1}" -f $Failure.method, $Failure.uri)
    if ($Failure.status_code) {
        Write-Stderr ("HTTP status: {0}" -f $Failure.status_code)
    }
    if ($Failure.error) {
        Write-Stderr ("Error: {0}" -f $Failure.error)
    }
    if ($Failure.error_detail) {
        Write-Stderr ("Response: {0}" -f $Failure.error_detail)
    }
    if ($ProviderHint) {
        Write-Stderr "Likely cause: EverCore extraction needs valid LLM, embedding, or rerank provider keys in methods/EverCore/.env."
        Write-Stderr "Fix: configure the provider keys, restart EverCore, then run this command again."
    }
}

function Invoke-EverCore {
    param(
        [ValidateSet("GET", "POST")]
        [string]$MethodName,
        [string]$Path,
        [object]$Body = $null,
        [switch]$AllowFailure
    )

    $uri = "{0}{1}" -f $BaseUrl.TrimEnd("/"), $Path

    try {
        if ($null -eq $Body) {
            $data = Invoke-RestMethod -Method $MethodName -Uri $uri -TimeoutSec 30
        } else {
            $json = $Body | ConvertTo-Json -Depth 30
            $data = Invoke-RestMethod -Method $MethodName -Uri $uri -ContentType "application/json" -Body $json -TimeoutSec 45
        }

        return [pscustomobject]@{
            ok = $true
            method = $MethodName
            uri = $uri
            status_code = 200
            data = $data
            error = $null
            error_detail = $null
        }
    } catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
            } catch {
                $statusCode = $null
            }
        }

        $failure = [pscustomobject]@{
            ok = $false
            method = $MethodName
            uri = $uri
            status_code = $statusCode
            data = $null
            error = $_.Exception.Message
            error_detail = Get-ErrorResponseBody $_
        }

        if ($AllowFailure) {
            return $failure
        }

        Write-EverCoreFailure $failure
        exit 1
    }
}

function Get-RawMessageText {
    param([object]$RawMessage)

    $texts = @()
    if ($RawMessage.content_items) {
        foreach ($item in @($RawMessage.content_items)) {
            if ($item.text) {
                $texts += [string]$item.text
            } elseif ($item.content) {
                $texts += [string]$item.content
            }
        }
    }

    return ($texts -join " ").Trim()
}

function Test-RawMessageMatchesQuery {
    param(
        [object]$RawMessage,
        [string]$Query
    )

    $rawText = Get-RawMessageText $RawMessage
    if ([string]::IsNullOrWhiteSpace($rawText)) {
        return $false
    }

    $textLower = $rawText.ToLowerInvariant()
    $queryLower = $Query.ToLowerInvariant()
    if ($textLower.Contains($queryLower)) {
        return $true
    }

    $tokens = @($Query -split "\s+" | Where-Object { $_.Trim().Length -ge 2 })
    if ($tokens.Count -eq 0) {
        return $false
    }

    foreach ($token in $tokens) {
        if (-not $textLower.Contains($token.ToLowerInvariant())) {
            return $false
        }
    }

    return $true
}

function Search-RawMessageById {
    param(
        [string]$MessageId,
        [long]$Timestamp
    )

    $filters = [ordered]@{
        group_id = $GroupId
    }

    if ($Timestamp -gt 0) {
        $filters["timestamp"] = [ordered]@{
            gte = $Timestamp - 60000
            lte = $Timestamp + 60000
        }
    }

    $payload = [ordered]@{
        query = $MessageId
        method = "keyword"
        memory_types = @("raw_message")
        top_k = $RawMessageFetchLimit
        filters = $filters
    }

    $result = Invoke-EverCore -MethodName "POST" -Path "/api/v1/memories/search" -Body $payload -AllowFailure
    if (-not $result.ok) {
        return [pscustomobject]@{
            found = $false
            raw = $null
            saturated = $false
            scanned = 0
            search_failed = $true
        }
    }

    $searchData = $result.data.data
    if ($null -eq $searchData -or $null -eq $searchData.raw_messages) {
        return [pscustomobject]@{
            found = $false
            raw = $null
            saturated = $false
            scanned = 0
            search_failed = $false
        }
    }

    $rawMessages = @($searchData.raw_messages)
    foreach ($raw in $rawMessages) {
        if ($raw.message_id -eq $MessageId) {
            return [pscustomobject]@{
                found = $true
                raw = $raw
                saturated = $rawMessages.Count -ge $RawMessageFetchLimit
                scanned = $rawMessages.Count
                search_failed = $false
            }
        }
    }

    return [pscustomobject]@{
        found = $false
        raw = $null
        saturated = $rawMessages.Count -ge $RawMessageFetchLimit
        scanned = $rawMessages.Count
        search_failed = $false
    }
}

function Write-Usage {
    @"
EverCore memory CLI for Codex

Usage:
  .\tools\evercore-memory.ps1 health
  .\tools\evercore-memory.ps1 save "summary to remember"
  .\tools\evercore-memory.ps1 search "query text"
  .\tools\evercore-memory.ps1 flush

Options:
  -BaseUrl   EverCore base URL. Default: http://localhost:1995 or EVERCORE_BASE_URL
  -GroupId   Memory group id. Default: codex_<sha256 current directory> or EVERCORE_GROUP_ID
  -SenderId  Sender id for saved notes. Default: codex_user or EVERCORE_SENDER_ID
  -TopK      Search result count. Default: 5
  -Method    keyword, vector, hybrid, agentic. Default: keyword

Notes:
  Run flush only after EverCore provider keys are configured. On an unconfigured
  server, flush can return no_extraction and pending raw notes may no longer
  appear in raw-message search.

Current effective scope:
  BaseUrl:   $BaseUrl
  GroupId:   $GroupId
  SenderId:  $SenderId
  Directory: $((Get-Location).Path)
"@
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = "http://localhost:1995"
}

if ([string]::IsNullOrWhiteSpace($GroupId)) {
    $GroupId = Get-CurrentProjectGroupId
}

if ([string]::IsNullOrWhiteSpace($SenderId)) {
    $SenderId = "codex_user"
}

function Invoke-Health {
    $result = Invoke-EverCore -MethodName "GET" -Path "/health"
    $result.data | ConvertTo-Json -Depth 10
}

function Invoke-Save {
    $content = Join-Text $Text
    if ([string]::IsNullOrWhiteSpace($content)) {
        Write-Stderr "save requires text."
        exit 2
    }

    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $messageId = New-StableMessageId -Content $content -Timestamp $timestamp
    $projectPath = (Get-Location).Path
    $projectLabel = Get-CurrentProjectLabel

    $payload = [ordered]@{
        group_id = $GroupId
        group_meta = [ordered]@{
            name = "Codex $projectLabel"
            description = "Codex workspace memory for $projectPath"
        }
        messages = @(
            [ordered]@{
                message_id = $messageId
                sender_id = $SenderId
                sender_name = "Codex"
                role = "user"
                timestamp = $timestamp
                content = $content
            }
        )
    }

    $result = Invoke-EverCore -MethodName "POST" -Path "/api/v1/memories/group" -Body $payload -AllowFailure
    if ($result.ok) {
        $apiData = $result.data.data
        $status = "submitted"
        if ($apiData -and $apiData.status) {
            $status = [string]$apiData.status
        }

        [pscustomobject]@{
            command = "save"
            status = $status
            group_id = $GroupId
            message_id = $messageId
            response = $result.data
        } | ConvertTo-Json -Depth 30
        return
    }

    if ($result.status_code -eq 500) {
        $rawLookup = Search-RawMessageById -MessageId $messageId -Timestamp $timestamp
        if ($rawLookup.found) {
            [pscustomobject]@{
                command = "save"
                status = "recorded_pending"
                group_id = $GroupId
                message_id = $messageId
                warning = "EverCore persisted the raw message, but memory extraction failed. Configure provider keys in methods/EverCore/.env, restart EverCore, then run flush."
                response_error = $result.error_detail
            } | ConvertTo-Json -Depth 30
            return
        }

        if ($rawLookup.saturated) {
            [pscustomobject]@{
                command = "save"
                status = "recorded_unconfirmed"
                group_id = $GroupId
                message_id = $messageId
                warning = "EverCore returned an extraction failure and raw-message confirmation reached the 100-message API cap without finding this message. Persistence may have succeeded, but could not be confirmed. Configure provider keys, flush old pending messages, or use a narrower group scope."
                response_error = $result.error_detail
            } | ConvertTo-Json -Depth 30
            return
        }
    }

    Write-EverCoreFailure $result -ProviderHint:($result.status_code -eq 500)
    exit 1
}

function Invoke-Search {
    $query = Join-Text $Text
    if ([string]::IsNullOrWhiteSpace($query)) {
        Write-Stderr "search requires query text."
        exit 2
    }

    $episodePayload = [ordered]@{
        query = $query
        method = $Method
        memory_types = @("episodic_memory")
        top_k = $TopK
        filters = [ordered]@{
            group_id = $GroupId
        }
    }

    $rawPayload = [ordered]@{
        query = $query
        method = "keyword"
        memory_types = @("raw_message")
        top_k = $RawMessageFetchLimit
        filters = [ordered]@{
            group_id = $GroupId
        }
    }

    $episodeResult = Invoke-EverCore -MethodName "POST" -Path "/api/v1/memories/search" -Body $episodePayload
    $rawResult = Invoke-EverCore -MethodName "POST" -Path "/api/v1/memories/search" -Body $rawPayload
    $episodeData = $episodeResult.data.data
    $rawData = $rawResult.data.data

    $episodes = @()
    if ($episodeData -and $episodeData.episodes) {
        $episodes = @($episodeData.episodes)
    }

    $rawMessages = @()
    $rawMessagesScanned = 0
    if ($rawData -and $rawData.raw_messages) {
        $rawMessagesScanned = @($rawData.raw_messages).Count
        $rawMessages = @(
            $rawData.raw_messages |
                Where-Object { Test-RawMessageMatchesQuery -RawMessage $_ -Query $query } |
                Select-Object -First $TopK
        )
    }

    $warning = $null
    if ($rawMessagesScanned -ge $RawMessageFetchLimit) {
        $warning = "Raw-message search scanned the first $RawMessageFetchLimit pending messages in this scope before client filtering. Older matching pending notes may require extraction/provider configuration or a narrower workspace scope."
    }

    $formattedEpisodes = @(
        foreach ($episode in $episodes) {
            $episodeText = $episode.summary
            if ([string]::IsNullOrWhiteSpace($episodeText)) {
                $episodeText = $episode.episode
            }

            [pscustomobject]@{
                id = $episode.id
                score = $episode.score
                timestamp = $episode.timestamp
                subject = $episode.subject
                text = $episodeText
            }
        }
    )

    $formattedRawMessages = @(
        foreach ($raw in $rawMessages) {
            [pscustomobject]@{
                id = $raw.id
                message_id = $raw.message_id
                timestamp = $raw.timestamp
                sender_id = $raw.sender_id
                text = Get-RawMessageText $raw
            }
        }
    )

    [pscustomobject]@{
        command = "search"
        status = "ok"
        group_id = $GroupId
        method = $Method
        warning = $warning
        count = $formattedEpisodes.Count + $formattedRawMessages.Count
        episodes = $formattedEpisodes
        raw_messages = $formattedRawMessages
    } | ConvertTo-Json -Depth 30
}

function Invoke-Flush {
    $payload = [ordered]@{
        group_id = $GroupId
    }

    $result = Invoke-EverCore -MethodName "POST" -Path "/api/v1/memories/group/flush" -Body $payload -AllowFailure
    if ($result.ok) {
        $apiData = $result.data.data
        $status = "submitted"
        if ($apiData -and $apiData.status) {
            $status = [string]$apiData.status
        }

        $warning = $null
        if ($status -eq "no_extraction") {
            $warning = "EverCore accepted the flush but did not create extracted memories. Flushed pending raw messages may no longer appear in raw-message search. If you expected searchable episodic memory, configure provider keys and save enough context before flushing."
        }

        [pscustomobject]@{
            command = "flush"
            status = $status
            group_id = $GroupId
            warning = $warning
            response = $result.data
        } | ConvertTo-Json -Depth 30
        return
    }

    Write-EverCoreFailure $result -ProviderHint:($result.status_code -eq 500)
    exit 1
}

switch ($Command) {
    "health" {
        Invoke-Health
    }
    "save" {
        Invoke-Save
    }
    "search" {
        Invoke-Search
    }
    "flush" {
        Invoke-Flush
    }
    "help" {
        Write-Usage
    }
}
