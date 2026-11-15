/*
 * [INPUT]: 依赖 Win32 进程接口与同目录的内置 Python。
 * [OUTPUT]: 启动隐藏后台助手、独立设置或退出命令。
 * [POS]: tools 的 Windows 免安装入口；不依赖终端或系统 Python。
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>

#ifndef ACTION
#define ACTION L""
#endif

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show) {
    wchar_t root[32768], executable[32768], script[32768], command[65536];
    DWORD length = GetModuleFileNameW(NULL, root, 32768);
    if (!length || length >= 32768) return 1;
    wchar_t *separator = wcsrchr(root, L'\\');
    if (!separator) return 1;
    *separator = L'\0';
    if (swprintf(executable, 32768, L"%ls\\runtime\\pythonw.exe", root) < 0 ||
        swprintf(script, 32768, L"%ls\\app\\main.py", root) < 0 ||
        swprintf(command, 65536, L"\"%ls\" \"%ls\" %ls", executable, script, ACTION) < 0) return 1;
    if (GetFileAttributesW(executable) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"请先完整解压整个运行包，再打开三级助手。", L"三级助手", MB_OK | MB_ICONERROR);
        return 1;
    }
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;
    if (!CreateProcessW(executable, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, root, &startup, &process)) {
        MessageBoxW(NULL, L"运行环境无法启动。请确认所有文件均已解压，并查看本机安全软件是否阻止运行。", L"三级助手", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
