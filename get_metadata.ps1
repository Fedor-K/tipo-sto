# Get OData metadata
$url = "http://172.22.0.89/1R96614/1R96614_AVTOSERV30_4pgnl9opb4/odata/standard.odata/" + '$metadata'

$user = [System.Text.Encoding]::UTF8.GetString([byte[]]@(0xD0,0x90,0xD0,0xB4,0xD0,0xBC,0xD0,0xB8,0xD0,0xBD,0xD0,0xB8,0xD1,0x81,0xD1,0x82,0xD1,0x80,0xD0,0xB0,0xD1,0x82,0xD0,0xBE,0xD1,0x80))
$pass = "12345678"
$pair = "${user}:${pass}"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($pair)
$base64 = [System.Convert]::ToBase64String($bytes)
$headers = @{
    Authorization = "Basic $base64"
}

Write-Output "Getting metadata from: $url"

try {
    $response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing -TimeoutSec 60
    Write-Output "Status: $($response.StatusCode)"

    # Parse XML to find EntitySet names
    [xml]$xml = $response.Content
    $ns = @{edmx = "http://schemas.microsoft.com/ado/2007/06/edmx"; edm = "http://schemas.microsoft.com/ado/2008/09/edm"}

    $entitySets = $xml.SelectNodes("//edm:EntitySet", $ns) | Select-Object -ExpandProperty Name
    Write-Output "`nAvailable EntitySets:"
    $entitySets | ForEach-Object { Write-Output "  $_" }
} catch {
    Write-Output "Error: $($_.Exception.Message)"
}
