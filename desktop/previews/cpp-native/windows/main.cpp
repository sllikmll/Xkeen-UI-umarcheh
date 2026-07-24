#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <vector>
#include <iostream>

static const wchar_t* kClassName = L"UnifiedUiCppNativePreviewWindow";

static bool HasArg(int argc, wchar_t** argv, const wchar_t* needle) {
    for (int i = 1; i < argc; ++i) if (wcscmp(argv[i], needle) == 0) return true;
    return false;
}

static HWND AddButton(HWND parent, const wchar_t* text, int x, int y, int w, int h, int id) {
    return CreateWindowExW(0, L"BUTTON", text, WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
        x, y, w, h, parent, (HMENU)(INT_PTR)id, GetModuleHandleW(nullptr), nullptr);
}
static HWND AddLabel(HWND parent, const wchar_t* text, int x, int y, int w, int h, int size = 18) {
    HWND label = CreateWindowExW(0, L"STATIC", text, WS_CHILD | WS_VISIBLE,
        x, y, w, h, parent, nullptr, GetModuleHandleW(nullptr), nullptr);
    HFONT font = CreateFontW(size, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    SendMessageW(label, WM_SETFONT, (WPARAM)font, TRUE);
    return label;
}

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        const wchar_t* tabs[] = {L"Маршрутизация", L"Mihomo", L"Соединения", L"WireGuard", L"VLESS", L"Маршруты DNS", L"Логи"};
        int left = 14, top = 14, gap = 6, width = 166;
        for (int i = 0; i < 7; ++i) AddButton(hwnd, tabs[i], left + i * (width + gap), top, width, 32, 100 + i);
        AddButton(hwnd, L"Stop unified", 14, 58, 130, 34, 210);
        AddButton(hwnd, L"Restart unified", 154, 58, 150, 34, 211);
        AddLabel(hwnd, L"Win32/C++ native shell · fastest Windows-native candidate", 326, 65, 600, 24, 16);
        AddLabel(hwnd, L"Selector overview", 40, 140, 390, 40, 28);
        AddLabel(hwnd, L"AI, Telegram, YouTube, GitHub", 40, 184, 390, 28, 18);
        AddLabel(hwnd, L"C++ native: максимально быстрый путь, но дороже по разработке и UI-полировке.", 40, 226, 470, 60, 16);
        AddLabel(hwnd, L"Маршруты DNS", 560, 140, 390, 40, 28);
        AddLabel(hwnd, L"Ручной ввод доменов", 560, 184, 390, 28, 18);
        HWND edit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"example.com\r\nyoutube.com\r\napi.service.io",
            WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_AUTOVSCROLL | WS_VSCROLL,
            560, 225, 560, 180, hwnd, (HMENU)300, GetModuleHandleW(nullptr), nullptr);
        SendMessageW(edit, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), TRUE);
        AddButton(hwnd, L"Собрать адреса", 560, 420, 560, 36, 301);
        return 0;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdc = (HDC)wp; SetTextColor(hdc, RGB(231,236,248)); SetBkColor(hdc, RGB(5,11,26));
        static HBRUSH bg = CreateSolidBrush(RGB(5,11,26)); return (LRESULT)bg;
    }
    case WM_COMMAND: return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

int wmain(int argc, wchar_t** argv) {
    if (HasArg(argc, argv, L"--smoke")) {
        std::cout << "{\"ok\":true,\"app\":\"Unified UI C++ Win32 Preview\",\"version\":\"0.1.0\",\"ui\":\"Win32/C++\"}\n";
        return 0;
    }
    FreeConsole();
    HINSTANCE inst = GetModuleHandleW(nullptr);
    WNDCLASSW wc{}; wc.lpfnWndProc = WndProc; wc.hInstance = inst; wc.lpszClassName = kClassName;
    wc.hbrBackground = CreateSolidBrush(RGB(5,11,26)); wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    RegisterClassW(&wc);
    HWND hwnd = CreateWindowExW(0, kClassName, L"Unified UI — C++ Win32 Preview", WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 1240, 760, nullptr, nullptr, inst, nullptr);
    ShowWindow(hwnd, SW_SHOW); UpdateWindow(hwnd);
    MSG msg{}; while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    return (int)msg.wParam;
}
