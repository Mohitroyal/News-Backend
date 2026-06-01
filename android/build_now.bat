@echo off
set "JAVA_HOME=C:\Program Files\Java\jdk-17"
echo JAVA_HOME set to: %JAVA_HOME%
echo.

echo === Verifying Java ===
"%JAVA_HOME%\bin\java.exe" -version
echo.

echo === Running Gradle Clean + assembleDebug ===
call gradlew.bat clean assembleDebug
if %ERRORLEVEL% NEQ 0 (
    echo DEBUG BUILD FAILED with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo === Running assembleRelease ===
call gradlew.bat assembleRelease
if %ERRORLEVEL% NEQ 0 (
    echo RELEASE BUILD FAILED with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo === BUILD COMPLETE ===
echo Checking for APKs...
dir /s /b app\build\outputs\apk\*.apk
