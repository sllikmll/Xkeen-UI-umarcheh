@echo off
setlocal
call "C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "publish\cpp" mkdir "publish\cpp"
cl /nologo /EHsc /std:c++17 /utf-8 /DUNICODE /D_UNICODE "desktop\previews\cpp-native\windows\main.cpp" /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup /OUT:"publish\cpp\Unified UI Cpp Win32 Preview.exe" user32.lib gdi32.lib shell32.lib winhttp.lib ws2_32.lib
