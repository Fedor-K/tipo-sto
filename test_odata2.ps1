# Test OData connection to Rent1C with various credentials
$url = "http://172.22.0.89/1R96614/1R96614_AVTOSERV30_4pgnl9opb4/odata/standard.odata/"

# Various credential combinations to try
$credentials = @(
    @{user = [System.Text.Encoding]::UTF8.GetString([byte[]]@(0xD0,0x90,0xD0,0xB4,0xD0,0xBC,0xD0,0xB8,0xD0,0xBD,0xD0,0xB8,0xD1,0x81,0xD1,0x82,0xD1,0x80,0xD0,0xB0,0xD1,0x82,0xD0,0xBE,0xD1,0x80)); pass = ""},
    @{user = [System.Text.Encoding]::UTF8.GetString([byte[]]@(0xD0,0x90,0xD0,0xB4,0xD0,0xBC,0xD0,0xB8,0xD0,0xBD,0xD0,0xB8,0xD1,0x81,0xD1,0x82,0xD1,0x80,0xD0,0xB0,0xD1,0x82,0xD0,0xBE,0xD1,0x80)); pass = "12345678"},
    @{user = [System.Text.Encoding]::UTF8.GetString([byte[]]@(0xD0,0x90,0xD0,0xB4,0xD0,0xBC,0xD0,0xB8,0xD0,0xBD,0xD0,0xB8,0xD1,0x81,0xD1,0x82,0xD1,0x80,0xD0,0xB0,0xD1,0x82,0xD0,0xBE,0xD1,0x80)); pass = "X7gDhIChmV"},
    @{user = "Administrator"; pass = ""},
    @{user = "admin"; pass = ""},
    @{user = "1R96614U1"; pass = "X7gDhIChmV"},
    @{user = ""; pass = ""}
)

foreach ($cred in $credentials) {
    $user = $cred.user
    $pass = $cred.pass
    $pair = "${user}:${pass}"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($pair)
    $base64 = [System.Convert]::ToBase64String($bytes)
    $headers = @{
        Authorization = "Basic $base64"
        Accept = "application/json"
    }

    Write-Output "Testing: '$user' / '$pass'"

    try {
        $response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing -TimeoutSec 10
        Write-Output "  SUCCESS! Status: $($response.StatusCode)"
        Write-Output "  Content: $($response.Content.Substring(0, [Math]::Min(300, $response.Content.Length)))"
        break
    } catch {
        $status = $_.Exception.Response.StatusCode.Value__
        Write-Output "  Failed: $status"
    }
}
