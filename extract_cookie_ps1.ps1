# 从 Chrome 提取 douyin.com 所有 Cookie（含 httpOnly）
Add-Type -AssemblyName System.Security

$chromeData = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default"
$stateFile = "$chromeData\Local State"
$cookieDb  = "$chromeData\Network\Cookies"

if (-not (Test-Path $stateFile)) { Write-Host "找不到 Chrome Local State"; exit 1 }
if (-not (Test-Path $cookieDb))  { Write-Host "找不到 Chrome Cookies 数据库"; exit 1 }

# 1. 读取加密密钥
$state = Get-Content $stateFile -Raw | ConvertFrom-Json
$encryptedKey = [Convert]::FromBase64String($state.os_crypt.encrypted_key)
$encryptedKey = $encryptedKey[5..($encryptedKey.Length - 1)]  # 去掉 "DPAPI" 前缀
$key = [System.Security.Cryptography.ProtectedData]::Unprotect($encryptedKey, $null, 'CurrentUser')

Write-Host "Encryption key loaded ($($key.Length) bytes)"

# 2. 复制数据库（Chrome 锁定）
$tmpDb = "$env:TEMP\chrome_cookies_temp.db"
Copy-Item $cookieDb $tmpDb -Force

# 3. 加载 SQLite
# 尝试找到 System.Data.SQLite
$sqliteDll = Get-ChildItem "$env:USERPROFILE\.nuget" -Recurse -Filter "System.Data.SQLite.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $sqliteDll) {
    # 改用 Python 处理 SQLite
    Write-Host "Using Python for SQLite..."
    $script = @"
import sqlite3, shutil, tempfile, os, json, base64, sys

# AES 解密
from Cryptodome.Cipher import AES

key = base64.b64decode('$([Convert]::ToBase64String($key))')

src = r'$cookieDb'
tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tmp.close()
shutil.copy2(src, tmp.name)

conn = sqlite3.connect(f'file:{tmp.name}?mode=ro', uri=True)
conn.text_factory = bytes
c = conn.cursor()
c.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%douyin.com'")
rows = c.fetchall()
conn.close()
os.unlink(tmp.name)

cookies = {}
for name, enc_val in rows:
    name = name.decode('utf-8', 'replace')
    if enc_val[:3] in (b'v10', b'v20'):
        nonce = enc_val[3:15]
        ct = enc_val[15:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        try:
            val = cipher.decrypt_and_verify(ct[:-16], ct[-16:])
            cookies[name] = val.decode('utf-8', 'replace')
        except:
            cookies[name] = '[DECRYPT_FAILED]'
    else:
        try:
            cookies[name] = enc_val.decode('utf-8', 'replace')
        except:
            cookies[name] = '[BINARY]'

# 输出为 JSON
print(json.dumps(cookies, ensure_ascii=False))
"@
    $scriptFile = "$env:TEMP\chrome_cookie_extract.py"
    $script | Out-File -Encoding UTF8 $scriptFile
    & python $scriptFile
    Remove-Item $scriptFile -Force
} else {
    Add-Type -Path $sqliteDll.FullName
    # ... SQLite 读取逻辑
}

Remove-Item $tmpDb -Force -ErrorAction SilentlyContinue
