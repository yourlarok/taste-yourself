$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Speech

$assetDirectory = Join-Path $PSScriptRoot "..\miniprogram\assets"
New-Item -ItemType Directory -Force -Path $assetDirectory | Out-Null

$prompts = @{
    "scan-front" = [Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String("6K+36Z2i5ZCR6ZWc5aS077yM5ZCO6YCA5Yiw5YWo6Lqr6L+b5YWl6L2u5buT77yM5Y+M6IeC6Ieq54S25YiG5byA44CC")
    )
    "scan-side" = [Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String("546w5Zyo6K+35ZCR5bem6L2s6Lqr77yM5L+d5oyB5L6n6Z2i56uZ56uL77yM6Lqr5L2T5LiN6KaB5pmD5Yqo44CC")
    )
}

foreach ($name in $prompts.Keys) {
    $wavePath = Join-Path $env:TEMP "$name.wav"
    $mp3Path = Join-Path $assetDirectory "$name.mp3"
    $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $speaker.SelectVoice("Microsoft Huihui Desktop")
    $speaker.Rate = 1
    $speaker.SetOutputToWaveFile($wavePath)
    $speaker.Speak($prompts[$name])
    $speaker.Dispose()
    & ffmpeg -loglevel error -y -i $wavePath -codec:a libmp3lame -b:a 48k -ac 1 $mp3Path
    Remove-Item -LiteralPath $wavePath
}

Write-Output "Generated scan voice assets in $assetDirectory"
