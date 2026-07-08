@echo off
set "NODE_DIR=C:\Program Files\nodejs"
set "PATH=%PATH%;%NODE_DIR%"
cd /d "c:\PROJECTS DEV\HH CORE\admin pannel HH\hostel-hunt-admin"
npm run dev -- --host 127.0.0.1 --port 5173
