@echo off
echo 🔧 Fixing Filebeat permissions...

REM Fix Filebeat configuration permissions
echo 📝 Fixing Filebeat permissions...
icacls "elk-configs\filebeat\filebeat.yml" /inheritance:r /grant:r "%USERNAME%:(R)"
icacls "elk-configs\filebeat\filebeat.yml" /grant:r "SYSTEM:(R)"

echo ✅ Filebeat permissions fixed successfully!
echo 💡 Now you can run: run_elk.bat
pause
