param(
    [string]$Action = "status"
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType=WindowsRuntime] | Out-Null
$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()

if (-not $profile) {
    Write-Output "ERROR:Brak aktywnego profilu sieciowego"
    exit 1
}

[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType=WindowsRuntime] | Out-Null
$manager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)

if ($Action -eq "start") {
    $res = Await ($manager.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
    $cfg = $manager.GetCurrentAccessPointConfiguration()
    Write-Output "RESULT:$($res.Status)"
    Write-Output "SSID:$($cfg.Ssid)"
    Write-Output "PASSWORD:$($cfg.Passphrase)"
}
elseif ($Action -eq "stop") {
    $res = Await ($manager.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
    Write-Output "RESULT:$($res.Status)"
}
elseif ($Action -eq "info") {
    $cfg = $manager.GetCurrentAccessPointConfiguration()
    Write-Output "STATE:$($manager.TetheringOperationalState)"
    Write-Output "SSID:$($cfg.Ssid)"
    Write-Output "PASSWORD:$($cfg.Passphrase)"
}
else {
    Write-Output "STATE:$($manager.TetheringOperationalState)"
}
