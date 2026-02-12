param(
  [string]$Base = "https://retire-production.up.railway.app"
)

# תצוגה יפה בלבד
chcp 65001 | Out-Null
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

Write-Host "BASE=$Base"

# סיסמה אינטראקטיבית (לא נכתבת בהיסטוריה)
$sec = Read-Host "Enter X-System-Password" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$SYS_PASS = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)

function New-ValidIsraeliId {
  # יוצר ת.ז. 9 ספרות תקינה עם ספרת ביקורת
  while ($true) {
    $base = Get-Random -Minimum 10000000 -Maximum 99999999  # 8 ספרות
    $s = "{0:D8}" -f $base
    $sum = 0
    for ($i=0; $i -lt 8; $i++) {
      $d = [int]$s[$i].ToString()
      $mul = if (($i % 2) -eq 0) { 1 } else { 2 }
      $p = $d * $mul
      if ($p -gt 9) { $p = $p - 9 }
      $sum += $p
    }
    $check = (10 - ($sum % 10)) % 10
    return ("{0}{1}" -f $s, $check)
  }
}

function CurlSave($url, $headersPath, $bodyPath, $method = "GET", $dataFile = $null) {
  $args = @("-sS", "-D", $headersPath, "-o", $bodyPath)
  if ($method -eq "POST") {
    $args += @("-H", "Content-Type: application/json; charset=utf-8", "--data-binary", "@$dataFile")
  }
  $args += @("-H", "X-System-Password: $SYS_PASS", $url)
  & curl.exe @args | Out-Null
}

# 1) _ping עם סיסמה
CurlSave "$Base/api/v1/_ping" ".\tmp_ping_headers.txt" ".\tmp_ping_body.json"
Select-String -Path .\tmp_ping_headers.txt -Pattern "^HTTP/" | ForEach-Object { $_.Line }

# 2) _ping בלי סיסמה (צריך 401)
& curl.exe -sS -D .\tmp_ping_401_headers.txt -o .\tmp_ping_401_body.json "$Base/api/v1/_ping" | Out-Null
Select-String -Path .\tmp_ping_401_headers.txt -Pattern "^HTTP/" | ForEach-Object { $_.Line }

# 3) clients GET ולהדפיס 3 שמות בעברית דרך Python
& curl.exe -sS -H "X-System-Password: $SYS_PASS" "$Base/api/v1/clients?limit=3" -o .\tmp_clients.json | Out-Null
python -c "import json; d=json.load(open('tmp_clients.json',encoding='utf-8')); items=d.get('items') or []; print('COUNT:',len(items)); [print(i.get('id'), i.get('id_number'), i.get('full_name')) for i in items]"

# 4) POST לקוח תקין בעברית (201) ואז GET חיפוש
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$idnum = New-ValidIsraeliId

$payload = @"
{
  `"id_number`": `"$idnum`",
  `"full_name`": `"יוסי כהן`",
  `"birth_date`": `"1980-01-01`",
  `"gender`": `"male`",
  `"marital_status`": `"married`"
}
"@
[System.IO.File]::WriteAllText(".\tmp_post_client.json", $payload, $utf8NoBom)

CurlSave "$Base/api/v1/clients" ".\tmp_post_headers.txt" ".\tmp_post_body.json" "POST" ".\tmp_post_client.json"
$httpLine = (Select-String -Path .\tmp_post_headers.txt -Pattern "^HTTP/").Line
Write-Host $httpLine

if ($httpLine -match " 201 ") {
  python -c "import json; d=json.load(open('tmp_post_body.json',encoding='utf-8')); print('POST_ID:', d.get('id')); print('POST_FULL_NAME:', d.get('full_name')); print('POST_ID_NUMBER:', d.get('id_number'))"

  & curl.exe -sS -H "X-System-Password: $SYS_PASS" "$Base/api/v1/clients?search=$idnum&limit=5" -o .\tmp_get_search.json | Out-Null
  python -c "import json; d=json.load(open('tmp_get_search.json',encoding='utf-8')); items=d.get('items') or []; print('SEARCH_COUNT:',len(items)); 
print('SEARCH_FULL_NAME:', (items[0].get('full_name') if items else None)); print('SEARCH_ID_NUMBER:', (items[0].get('id_number') if items else None))"
}
else {
  # אם קיבלנו 422/401/500, נדפיס detail בצורה חסינה
  python -c "import json; d=json.load(open('tmp_post_body.json',encoding='utf-8')); det=d.get('detail'); print('DETAIL_TYPE:', type(det).__name__); 
print(det if isinstance(det,str) else (det[0].get('msg') if isinstance(det,list) and det and isinstance(det[0],dict) else det))"
}

# ניקוי רגיש
Remove-Variable SYS_PASS -ErrorAction SilentlyContinue
Remove-Variable sec -ErrorAction SilentlyContinue

Write-Host "DONE"
