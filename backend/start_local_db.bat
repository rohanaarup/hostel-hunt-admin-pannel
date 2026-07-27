@echo off
REM Start local PostgreSQL via Docker for HH Core backend
REM Requires Docker Desktop to be running

echo.
echo ============================================
echo  Starting local PostgreSQL (Docker)
echo ============================================
echo.

REM Check if container is already running
docker ps -a --filter "name=hh-core-pg" --format "{{.Names}}" | findstr /i "hh-core-pg" >nul
if %errorlevel%==0 (
    echo Container hh-core-pg already exists. Starting it...
    docker start hh-core-pg
) else (
    echo Creating new PostgreSQL container...
    docker run -d ^
        --name hh-core-pg ^
        -e POSTGRES_USER=postgres ^
        -e POSTGRES_PASSWORD=postgres ^
        -e POSTGRES_DB=hh_core ^
        -p 5432:5432 ^
        --restart unless-stopped ^
        postgres:16-alpine
)

if %errorlevel%==0 (
    echo.
    echo Waiting for PostgreSQL to be ready...
    timeout /t 3 /nobreak >nul

    REM Test connection
    docker exec hh-core-pg pg_isready -U postgres >nul
    if %errorlevel%==0 (
        echo.
        echo ============================================
        echo  PostgreSQL is running on localhost:5432
        echo  User: postgres
        echo  Password: postgres
        echo  Database: hh_core
        echo ============================================
        echo.
        echo Next step: set USE_DB=local in your .env file
        echo.
    ) else (
        echo PostgreSQL container started but not ready yet. Wait a few seconds.
    )
) else (
    echo.
    echo ERROR: Failed to start PostgreSQL.
    echo Make sure Docker Desktop is running.
)

pause
