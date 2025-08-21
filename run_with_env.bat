@echo off
echo Loading environment variables from env.example...

REM Load environment variables from env.example
for /f "tokens=1,2 delims==" %%a in ('findstr /v "^#" "sre\compose\env.example"') do (
    set "%%a=%%b"
)

echo Starting Django development server...
python manage.py runserver
