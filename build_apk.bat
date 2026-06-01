@echo off
rem -------------------------------------------------------------------
rem Build script for NewsCraft Mobile Android APK
rem -------------------------------------------------------------------

rem Set project root
set "PROJECT_ROOT=%~dp0"

rem Ensure JAVA_HOME points to a valid JDK (adjust if needed)
rem You may need to modify this path to your actual JDK installation.
set "JAVA_HOME=C:\\Program Files\\Java\\jdk-17"
set "PATH=%JAVA_HOME%\\bin;%PATH%"

rem Verify Java installation
java -version
if errorlevel 1 (
  echo [ERROR] Java not found. Please install JDK 17 and set JAVA_HOME.
  exit /b 1
)

rem Change to project directory
pushd "%PROJECT_ROOT%"

rem Enter Android subdirectory
cd android

rem Clean previous builds (optional)
call gradlew.bat clean

rem Build debug APK
call gradlew.bat assembleDebug

rem Return to project root
cd ..

if errorlevel 1 (
  echo [ERROR] Gradle build failed.
  popd
  exit /b 1
)

rem Locate the generated APK
set "APK_PATH=%PROJECT_ROOT%android\app\build\outputs\apk\debug\app-debug.apk"
if exist "%APK_PATH%" (
  echo [INFO] APK built successfully: "%APK_PATH%"
) else (
  echo [ERROR] APK not found after build.
)

popd
exit /b 0
