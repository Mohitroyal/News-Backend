@echo off
rem -------------------------------------------------------------------
rem Build script for NewsCraft Mobile Android APK
rem -------------------------------------------------------------------

set "PROJECT_ROOT=%~dp0"
pushd "%PROJECT_ROOT%"

rem Add Node.js to PATH if not already in PATH
if exist "C:\Users\maham\node-v22.13.0-win-x64" (
  set "PATH=C:\Users\maham\node-v22.13.0-win-x64;%PATH%"
) else if exist "C:\Users\maham\node-v20.11.1-win-x64" (
  set "PATH=C:\Users\maham\node-v20.11.1-win-x64;%PATH%"
)

rem Set ANDROID_HOME
if exist "C:\Users\maham\AppData\Local\Android\Sdk" (
  set "ANDROID_HOME=C:\Users\maham\AppData\Local\Android\Sdk"
  set "ANDROID_SDK_ROOT=C:\Users\maham\AppData\Local\Android\Sdk"
)

rem Set JAVA_HOME if not already set or invalid
if exist "C:\Program Files\Android\Android Studio\jbr" (
  set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
) else if exist "C:\Program Files\Java\jdk-17" (
  set "JAVA_HOME=C:\Program Files\Java\jdk-17"
) else if exist "C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot" (
  set "JAVA_HOME=C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot"
)

echo [1/3] Building frontend assets...
call npm run build
if errorlevel 1 (
  echo [ERROR] Frontend build failed.
  popd
  exit /b 1
)

echo [2/3] Syncing Capacitor assets...
call node .\node_modules\@capacitor\cli\bin\capacitor copy android
if errorlevel 1 (
  echo [ERROR] Capacitor copy failed.
  popd
  exit /b 1
)

echo [3/3] Building Android APK...
cd android
call gradlew.bat assembleDebug assembleRelease
cd ..

set "APK_PATH=%PROJECT_ROOT%android\app\build\outputs\apk\debug\app-debug.apk"
set "RELEASE_APK_PATH=%PROJECT_ROOT%android\app\build\outputs\apk\release\app-release.apk"
if exist "%APK_PATH%" (
  echo.
  echo ===================================================
  echo [SUCCESS] APK built successfully!
  echo Location: "%APK_PATH%"
  echo ===================================================
  copy /y "%APK_PATH%" "%PROJECT_ROOT%NewsCraft-Mobile-Updated.apk" >nul
  copy /y "%APK_PATH%" "%PROJECT_ROOT%NewsCraft-v1.56-debug.apk" >nul
  copy /y "%APK_PATH%" "%PROJECT_ROOT%..\..\..\NewsCraft-Mobile-Updated.apk" >nul
) else (
  echo [ERROR] APK not found after build.
)
if exist "%RELEASE_APK_PATH%" (
  copy /y "%RELEASE_APK_PATH%" "%PROJECT_ROOT%app-release.apk" >nul
  copy /y "%RELEASE_APK_PATH%" "%PROJECT_ROOT%newscraft-v1.56.apk" >nul
)

popd
exit /b 0
