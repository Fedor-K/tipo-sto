# Get OData metadata - simple version
$url = "http://172.22.0.89/1R96614/1R96614_AVTOSERV30_4pgnl9opb4/odata/standard.odata/" + '$metadata'

$user = [System.Text.Encoding]::UTF8.GetString([byte[]]@(0xD0,0x90,0xD0,0xB4,0xD0,0xBC,0xD0,0xB8,0xD0,0xBD,0xD0,0xB8,0xD1,0x81,0xD1,0x82,0xD1,0x80,0xD0,0xB0,0xD1,0x82,0xD0,0xBE,0xD1,0x80))
$pass = "12345678"
$pair = "${user}:${pass}"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($pair)
$base64 = [System.Convert]::ToBase64String($bytes)
$headers = @{
    Authorization = "Basic $base64"
}

$response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing -TimeoutSec 60
$content = $response.Content

# Find EntitySet names using regex
$matches = [regex]::Matches($content, 'EntitySet Name="([^"]+)"')
Write-Output "Available EntitySets (found $($matches.Count)):"
$matches | ForEach-Object { Write-Output $_.Groups[1].Value }
