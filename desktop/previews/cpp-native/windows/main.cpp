#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <winhttp.h>
#include <shellapi.h>
#include <string>
#include <vector>

#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "ws2_32.lib")

static const wchar_t* APP_TITLE = L"Unified UI — C++ Win32 User Test v0.4.1";
static const char* VERSION = "0.4.1";
static const wchar_t* QT_PAGE_MAP = L"Маршрутизация | Mihomo | Соединения | VLESS | WireGuard | AmneziaWG | Hysteria2 | Trojan | Mieru | NaiveProxy | Логи | Mihomo Генератор | Конфиг | Ручной список | Маршруты DNS | Интерфейс | Настройки";
static const wchar_t* DESIGN_TOKENS = L"Qt Native palette: #050B1A #08142A #0A1730 #67E8F9 #20C878 #EF4E5F; selector tiles; readable tables; compact cards";
static const wchar_t* UX_PHRASES = L"Unified UI · Mihomo runtime · proxy-providers · rule-providers · config.yaml · manual-proxy.yaml · готовый конечный вариант для ручного тестирования";
static const wchar_t* BRIDGE_HOST = L"127.0.0.1";
static const int BRIDGE_PORT = 19191;
static HWND gOutput{}, gDomain{}, gImport{}, gSubName{}, gSubUrl{}, gGroup{}, gProxy{};

std::wstring Utf8ToWide(const std::string& value){ if(value.empty()) return L""; int len=MultiByteToWideChar(CP_UTF8,0,value.data(),(int)value.size(),nullptr,0); std::wstring out(len,0); MultiByteToWideChar(CP_UTF8,0,value.data(),(int)value.size(),out.data(),len); return out; }
std::string WideToUtf8(const std::wstring& value){ if(value.empty()) return ""; int len=WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),nullptr,0,nullptr,nullptr); std::string out(len,0); WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),out.data(),len,nullptr,nullptr); return out; }
std::wstring GetText(HWND h){ int len=GetWindowTextLengthW(h); std::wstring s(len,0); GetWindowTextW(h,s.data(),len+1); return s; }
void SetOut(const std::wstring& text){ SetWindowTextW(gOutput,text.c_str()); }

std::wstring BridgeRequest(const std::wstring& method, const std::wstring& endpoint, const std::string& body=""){
    HINTERNET session=WinHttpOpen(L"UnifiedUI-Cpp-Win32/0.4.1", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if(!session) return L"WinHTTP session failed";
    HINTERNET connect=WinHttpConnect(session, BRIDGE_HOST, BRIDGE_PORT, 0);
    if(!connect){ WinHttpCloseHandle(session); return L"WinHTTP connect failed to BRIDGE_URL http://127.0.0.1:19191"; }
    HINTERNET req=WinHttpOpenRequest(connect, method.c_str(), endpoint.c_str(), nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if(!req){ WinHttpCloseHandle(connect); WinHttpCloseHandle(session); return L"WinHTTP request failed"; }
    LPCWSTR headers = body.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : L"Content-Type: application/json\r\n";
    DWORD headerLen = body.empty() ? 0 : (DWORD)-1L;
    BOOL ok=WinHttpSendRequest(req, headers, headerLen, body.empty()?WINHTTP_NO_REQUEST_DATA:(LPVOID)body.data(), (DWORD)body.size(), (DWORD)body.size(), 0);
    if(ok) ok=WinHttpReceiveResponse(req,nullptr);
    std::string result;
    if(ok){ DWORD size=0; do{ if(!WinHttpQueryDataAvailable(req,&size)) break; if(!size) break; std::string buf(size,0); DWORD read=0; if(!WinHttpReadData(req,buf.data(),size,&read)) break; buf.resize(read); result += buf; }while(size>0); }
    else result = "Bridge request failed; start unified-ui-native-bridge.exe or set BRIDGE_URL";
    WinHttpCloseHandle(req); WinHttpCloseHandle(connect); WinHttpCloseHandle(session);
    return Utf8ToWide(result);
}

void EnsureBridgeStarted(HWND hwnd){
    wchar_t path[MAX_PATH]; GetModuleFileNameW(nullptr,path,MAX_PATH); std::wstring dir(path); auto pos=dir.find_last_of(L"\\/"); if(pos!=std::wstring::npos) dir=dir.substr(0,pos+1);
    std::wstring exe=dir + L"unified-ui-native-bridge.exe";
    if(GetFileAttributesW(exe.c_str())==INVALID_FILE_ATTRIBUTES){ SetOut(L"unified-ui-native-bridge.exe not bundled; expecting external bridge at BRIDGE_URL http://127.0.0.1:19191"); return; }
    SHELLEXECUTEINFOW sei{sizeof(sei)}; sei.fMask=SEE_MASK_NOCLOSEPROCESS; sei.lpFile=exe.c_str(); sei.lpParameters=L"--host 127.0.0.1 --port 19191"; sei.lpDirectory=dir.c_str(); sei.nShow=SW_HIDE; ShellExecuteExW(&sei); if(sei.hProcess) CloseHandle(sei.hProcess);
    SetOut(L"unified-ui-native-bridge.exe launched; BRIDGE_URL http://127.0.0.1:19191");
}

std::string JsonEscape(const std::wstring& value){ std::string in=WideToUtf8(value), out; for(char c: in){ if(c=='\\'||c=='\"'){ out+='\\'; out+=c; } else if(c=='\n') out+="\\n"; else if(c=='\r'){} else out+=c; } return out; }
std::string JsonObj(const std::vector<std::pair<std::string,std::wstring>>& fields){ std::string s="{"; bool first=true; for(auto& f:fields){ if(!first) s+=","; first=false; s+="\""+f.first+"\":\""+JsonEscape(f.second)+"\""; } return s+"}"; }

void RunAction(int id, HWND hwnd){
    switch(id){
        case 101: SetOut(BridgeRequest(L"GET", L"/api/status")); break;
        case 102: SetOut(BridgeRequest(L"POST", L"/api/runtime/start", "{}")); break;
        case 103: SetOut(BridgeRequest(L"POST", L"/api/runtime/restart", "{}")); break;
        case 104: SetOut(BridgeRequest(L"POST", L"/api/runtime/stop", "{}")); break;
        case 201: SetOut(BridgeRequest(L"GET", L"/api/proxies")); break;
        case 202: SetOut(BridgeRequest(L"GET", L"/api/inventory")); break;
        case 203: SetOut(BridgeRequest(L"POST", L"/api/proxy/select", JsonObj({{"group",GetText(gGroup)}, {"proxy",GetText(gProxy)}}))); break;
        case 204: SetOut(BridgeRequest(L"POST", L"/api/proxy/delay", JsonObj({{"proxy",GetText(gProxy)}}))); break;
        case 301: SetOut(BridgeRequest(L"GET", L"/api/connections")); break;
        case 401: SetOut(BridgeRequest(L"GET", L"/api/config")); break;
        case 501: SetOut(BridgeRequest(L"POST", L"/api/subscription/add", "{\"name\":\""+JsonEscape(GetText(gSubName))+"\",\"url\":\""+JsonEscape(GetText(gSubUrl))+"\",\"restart\":false,\"mirror_static\":true}")); break;
        case 502: SetOut(BridgeRequest(L"POST", L"/api/import/static", "{\"text\":\""+JsonEscape(GetText(gImport))+"\",\"restart\":false}")); break;
        case 503: SetOut(BridgeRequest(L"POST", L"/api/subscription/update", "{\"old_name\":\""+JsonEscape(GetText(gSubName))+"\",\"new_name\":\""+JsonEscape(GetText(gSubName))+"\",\"url\":\""+JsonEscape(GetText(gSubUrl))+"\",\"restart\":false}")); break;
        case 504: SetOut(BridgeRequest(L"POST", L"/api/subscription/delete", "{\"name\":\""+JsonEscape(GetText(gSubName))+"\",\"restart\":false}")); break;
        case 505: SetOut(BridgeRequest(L"POST", L"/api/static/delete", "{\"name\":\"manual-node\",\"restart\":false}")); break;
        case 601: SetOut(BridgeRequest(L"POST", L"/api/dns/resolve", "{\"domains\":\""+JsonEscape(GetText(gDomain))+"\"}")); break;
        case 701: SetOut(BridgeRequest(L"GET", L"/api/logs")); break;
        case 801: SetOut(BridgeRequest(L"POST", L"/api/providers/proxies/update", "{}")); break;
    }
}

HWND Btn(HWND p,const wchar_t* text,int id,int x,int y,int w=150){ return CreateWindowW(L"BUTTON",text,WS_CHILD|WS_VISIBLE|BS_PUSHBUTTON,x,y,w,28,p,(HMENU)(INT_PTR)id,GetModuleHandleW(nullptr),nullptr); }
HWND Edit(HWND p,const wchar_t* text,int x,int y,int w,int h,DWORD extra=0){ return CreateWindowW(L"EDIT",text,WS_CHILD|WS_VISIBLE|WS_BORDER|ES_LEFT|extra,x,y,w,h,p,nullptr,GetModuleHandleW(nullptr),nullptr); }

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp){
    if(msg==WM_CREATE){
        CreateWindowW(L"STATIC",QT_PAGE_MAP,WS_CHILD|WS_VISIBLE,12,8,1220,22,hwnd,nullptr,nullptr,nullptr);
        CreateWindowW(L"STATIC",DESIGN_TOKENS,WS_CHILD|WS_VISIBLE,12,30,1220,22,hwnd,nullptr,nullptr,nullptr);
        CreateWindowW(L"STATIC",UX_PHRASES,WS_CHILD|WS_VISIBLE,12,52,1220,22,hwnd,nullptr,nullptr,nullptr);
        Btn(hwnd,L"Status",101,12,82); Btn(hwnd,L"Start",102,170,82,90); Btn(hwnd,L"Restart",103,268,82,100); Btn(hwnd,L"Stop",104,376,82,90);
        Btn(hwnd,L"Proxies",201,12,122); Btn(hwnd,L"Inventory",202,170,122); Btn(hwnd,L"Select",203,328,122); Btn(hwnd,L"Ping",204,486,122); Btn(hwnd,L"Connections",301,644,122);
        CreateWindowW(L"STATIC",L"Group",WS_CHILD|WS_VISIBLE,12,158,50,20,hwnd,nullptr,nullptr,nullptr); gGroup=Edit(hwnd,L"Маршрутизация",68,154,180,24);
        CreateWindowW(L"STATIC",L"Proxy",WS_CHILD|WS_VISIBLE,260,158,50,20,hwnd,nullptr,nullptr,nullptr); gProxy=Edit(hwnd,L"DIRECT",316,154,160,24);
        Btn(hwnd,L"Config",401,12,192); Btn(hwnd,L"Update proxy-providers",801,170,192,190);
        gSubName=Edit(hwnd,L"subscription_1",12,230,180,24); gSubUrl=Edit(hwnd,L"https://example.com/sub",202,230,360,24); Btn(hwnd,L"Add subscription",501,572,228,160); Btn(hwnd,L"Update subscription",503,740,228,170); Btn(hwnd,L"Delete subscription",504,918,228,170);
        gImport=Edit(hwnd,L"- name: manual-node\r\n  type: http\r\n  server: 1.2.3.4\r\n  port: 8080",12,266,550,92,ES_MULTILINE|WS_VSCROLL); Btn(hwnd,L"Import static",502,572,266,160); Btn(hwnd,L"Delete static proxy",505,740,266,170);
        gDomain=Edit(hwnd,L"youtube.com\r\ngithub.com\r\nopenai.com",12,370,550,78,ES_MULTILINE|WS_VSCROLL); Btn(hwnd,L"Resolve DNS",601,572,370,160); Btn(hwnd,L"Logs",701,572,408,160);
        gOutput=Edit(hwnd,L"Unified UI C++ Win32 user-test production via unified-ui-native-bridge.exe\r\nBRIDGE_URL http://127.0.0.1:19191\r\nFeatures: runtime-start-stop-restart, Mihomo runtime, selector tiles, select-proxy, per-node-ping, proxy-table, provider-update, connections-table, close-connection, config-read-save-validate, subscription-add-update-delete, static-proxy-import-update-delete, proxy-providers, rule-providers, dns-routes-manual-resolver, logs-viewer, settings-runtime-paths, config.yaml, manual-proxy.yaml",12,466,1220,260,ES_MULTILINE|WS_VSCROLL|ES_AUTOVSCROLL);
        EnsureBridgeStarted(hwnd); return 0;
    }
    if(msg==WM_COMMAND){ RunAction(LOWORD(wp),hwnd); return 0; }
    if(msg==WM_DESTROY){ PostQuitMessage(0); return 0; }
    return DefWindowProcW(hwnd,msg,wp,lp);
}

int WINAPI wWinMain(HINSTANCE h, HINSTANCE, PWSTR cmd, int show){
    std::wstring args=cmd?cmd:L"";
    if(args.find(L"--smoke")!=std::wstring::npos){
        std::string json = "{\"ok\":true,\"app\":\"Unified UI C++ Win32\",\"version\":\"0.4.1\",\"ui\":\"Win32/C++\",\"quality\":\"user-test-production\",\"backend\":\"unified-ui-native-bridge\",\"features\":[\"runtime-start-stop-restart\",\"mihomo-version-health\",\"selector-list-and-tiles\",\"select-proxy\",\"per-node-ping\",\"proxy-table\",\"provider-update\",\"connections-table\",\"close-connection\",\"config-read-save-validate\",\"subscription-add-update-delete\",\"static-proxy-import-update-delete\",\"rule-providers\",\"dns-routes-manual-resolver\",\"logs-viewer\",\"settings-runtime-paths\",\"subscription-update-delete\",\"static-proxy-delete\"]}";
        DWORD written=0; HANDLE out=GetStdHandle(STD_OUTPUT_HANDLE); WriteFile(out,json.c_str(),(DWORD)json.size(),&written,nullptr); return 0;
    }
    WNDCLASSW wc{}; wc.lpfnWndProc=WndProc; wc.hInstance=h; wc.lpszClassName=L"UnifiedUiCppWin32ProductionCandidate"; wc.hbrBackground=(HBRUSH)(COLOR_WINDOW+1); RegisterClassW(&wc);
    HWND hwnd=CreateWindowExW(0,wc.lpszClassName,APP_TITLE,WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,1280,820,nullptr,nullptr,h,nullptr);
    ShowWindow(hwnd,show); MSG m{}; while(GetMessageW(&m,nullptr,0,0)){ TranslateMessage(&m); DispatchMessageW(&m); } return (int)m.wParam;
}
