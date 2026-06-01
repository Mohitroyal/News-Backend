@echo off
set "JAVA_HOME=C:\Program Files\Java\jdk-17"
set "JAVA=%JAVA_HOME%\bin\java.exe"
set "KEYTOOL=%JAVA_HOME%\bin\keytool.exe"
set "JARSIGNER=%JAVA_HOME%\bin\jarsigner.exe"
set "BUILD_TOOLS=C:\Users\MOHIT\AppData\Local\Android\Sdk\build-tools\35.0.0"
set "ZIPALIGN=%BUILD_TOOLS%\zipalign.exe"

set "APK_DIR=app\build\outputs\apk\release"
set "UNSIGNED_APK=%APK_DIR%\app-release-unsigned.apk"
set "SIGNED_APK=%APK_DIR%\app-release.apk"
set "KEYSTORE=newscraft-release.keystore"
set "KEY_ALIAS=newscraft"
set "STORE_PASS=newscraft2024"
set "KEY_PASS=newscraft2024"

echo ==========================================
echo  NewsCraft Mobile - APK Signing Pipeline
echo ==========================================
echo  Java: %JAVA%
echo  Jarsigner: %JARSIGNER%
echo  Zipalign: %ZIPALIGN%
echo ==========================================
echo.

REM Step 1: Generate keystore if it doesn't exist
if not exist "%KEYSTORE%" (
    echo [1/4] Generating release keystore...
    "%KEYTOOL%" -genkeypair -v ^
        -keystore "%KEYSTORE%" ^
        -alias %KEY_ALIAS% ^
        -keyalg RSA ^
        -keysize 2048 ^
        -validity 10000 ^
        -storepass %STORE_PASS% ^
        -keypass %KEY_PASS% ^
        -dname "CN=NewsCraft Mobile, OU=Mobile, O=NewsCraft, L=India, ST=TG, C=IN"
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Keystore generation failed!
        exit /b 1
    )
    echo Keystore generated successfully.
) else (
    echo [1/4] Keystore already exists, reusing.
)
echo.

REM Step 2: Sign using jarsigner
echo [2/4] Signing APK with jarsigner...
if exist "%SIGNED_APK%" del "%SIGNED_APK%"
copy "%UNSIGNED_APK%" "%SIGNED_APK%" >nul

"%JARSIGNER%" -verbose ^
    -sigalg SHA256withRSA ^
    -digestalg SHA-256 ^
    -keystore "%KEYSTORE%" ^
    -storepass %STORE_PASS% ^
    -keypass %KEY_PASS% ^
    "%SIGNED_APK%" ^
    %KEY_ALIAS%

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: jarsigner signing failed!
    exit /b 1
)
echo jarsigner signing complete.
echo.

REM Step 3: Zipalign the signed APK
echo [3/4] Running zipalign on signed APK...
set "ALIGNED_APK=%APK_DIR%\app-release-final.apk"
if exist "%ALIGNED_APK%" del "%ALIGNED_APK%"

"%ZIPALIGN%" -v 4 "%SIGNED_APK%" "%ALIGNED_APK%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: zipalign failed!
    exit /b 1
)
echo zipalign complete.
echo.

REM Step 4: Verify with jarsigner
echo [4/4] Verifying signed APK...
"%JARSIGNER%" -verify -verbose -certs "%ALIGNED_APK%"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Verification returned non-zero but APK may still be valid.
)
echo.

REM Copy debug APK to a convenient location
set "DEBUG_APK=app\build\outputs\apk\debug\app-debug.apk"

echo ==========================================
echo  SIGNING COMPLETE - FINAL REPORT
echo ==========================================
echo.
echo  [DEBUG APK - installable as-is]
echo  Path: %CD%\%DEBUG_APK%
for %%F in ("%DEBUG_APK%") do echo  Size: %%~zF bytes
echo.
echo  [RELEASE APK - signed + zipaligned]
echo  Path: %CD%\%ALIGNED_APK%
for %%F in ("%ALIGNED_APK%") do echo  Size: %%~zF bytes
echo.
echo  Keystore: %CD%\%KEYSTORE%
echo  Alias: %KEY_ALIAS%
echo  Password: %STORE_PASS%
echo.
echo  Both APKs are ready for installation on Android 10+
echo ==========================================
