# Test OData connection to Rent1C
$url = "http://172.22.0.89/1R96614/1R96614_AVTOSERV30_4pgnl9opb4/odata/standard.odata/"

# Try with Администратор (empty password)
$user = [System.Text.Encoding]::UTF8.GetString([byte[]]@(0xD0,0x90,0xD0,0xB4,0xD0,0xBC,0xD0,0xB8,0xD0,0xBD,0xD0,0xB8,0xD1,0x81,0xD1,0x82,0xD1,0x80,0xD0,0xB0,0xD1,0x82,0xD0,0xBE,0xD1,0x80))
$pass = ""
$pair = "${user}:${pass}"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($pair)
$base64 = [System.Convert]::ToBase64String($bytes)
$headers = @{
    Authorization = "Basic $base64"
    Accept = "application/json"
}

Write-Output "Testing with user: $user"
Write-Output "Auth header: Basic $base64"

try {
    $response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing -TimeoutSec 30
    Write-Output "Status: $($response.StatusCode)"
    Write-Output "Content: $($response.Content.Substring(0, [Math]::Min(500, $response.Content.Length)))"
} catch {
    $status = $_.Exception.Response.StatusCode.Value__
    Write-Output "Error Status: $status"
    Write-Output "Error: $($_.Exception.Message)"
}
