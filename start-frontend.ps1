$nodeDir = 'C:\Program Files\nodejs'
$env:Path = "$env:Path;$nodeDir"
Set-Location 'c:\PROJECTS DEV\HH CORE\admin pannel HH\hostel-hunt-admin'
& "$nodeDir\npm.cmd" run dev -- --host 127.0.0.1 --port 5173
