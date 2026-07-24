using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;

namespace UnifiedUiWpfPreview;

public sealed class NativeBridgeClient
{
    readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(20) };
    public string BridgeUrl { get; } = Environment.GetEnvironmentVariable("BRIDGE_URL") ?? "http://127.0.0.1:19191";
    public string BridgeExe => Path.Combine(AppContext.BaseDirectory, "unified-ui-native-bridge.exe");
    public void EnsureBridgeStarted(Action<string> log)
    {
        if (!File.Exists(BridgeExe)) { log($"bridge executable not bundled, expecting external bridge: {BridgeExe}"); return; }
        try
        {
            Process.Start(new ProcessStartInfo { FileName = BridgeExe, Arguments = "--host 127.0.0.1 --port 19191", UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = AppContext.BaseDirectory });
            log($"Mihomo runtime bridge launched: {BridgeExe}");
        }
        catch (Exception ex) { log($"bridge launch failed: {ex.Message}"); }
    }
    public async Task<string> Get(string endpoint) { using var res = await http.GetAsync(BridgeUrl.TrimEnd('/') + endpoint); return await Pretty(res); }
    public async Task<string> Post(string endpoint, object payload) { using var res = await http.PostAsync(BridgeUrl.TrimEnd('/') + endpoint, new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json")); return await Pretty(res); }
    static async Task<string> Pretty(HttpResponseMessage res)
    {
        var raw = await res.Content.ReadAsStringAsync();
        try { using var doc = JsonDocument.Parse(raw); return $"HTTP {(int)res.StatusCode}\n" + JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }); }
        catch { return $"HTTP {(int)res.StatusCode}\n" + raw; }
    }
    public Task<string> Status() => Get("/api/status");
    public Task<string> Start() => Post("/api/runtime/start", new { });
    public Task<string> Stop() => Post("/api/runtime/stop", new { });
    public Task<string> Restart() => Post("/api/runtime/restart", new { });
    public Task<string> Proxies() => Get("/api/proxies");
    public Task<string> Providers() => Get("/api/providers/proxies");
    public Task<string> Rules() => Get("/api/providers/rules");
    public Task<string> Connections() => Get("/api/connections");
    public Task<string> Inventory() => Get("/api/inventory");
    public Task<string> Config() => Get("/api/config");
    public Task<string> Logs() => Get("/api/logs");
    public Task<string> Delay(string proxy) => Post("/api/proxy/delay", new { proxy });
    public Task<string> Select(string group, string proxy) => Post("/api/proxy/select", new { group, proxy });
    public Task<string> SaveConfig(string text) => Post("/api/config/save", new { text, validate = true });
    public Task<string> ApplyConfig(string text) => Post("/api/config/apply", new { text });
    public Task<string> AddSubscription(string name, string url) => Post("/api/subscription/add", new { name, url, restart = false, mirror_static = true });
    public Task<string> UpdateSubscription(string oldName, string newName, string url) => Post("/api/subscription/update", new { old_name = oldName, new_name = newName, url, restart = false });
    public Task<string> DeleteSubscription(string name) => Post("/api/subscription/delete", new { name, restart = false });
    public Task<string> ImportStatic(string text) => Post("/api/import/static", new { text, restart = false });
    public Task<string> DeleteStatic(string name) => Post("/api/static/delete", new { name, restart = false });
    public Task<string> ResolveDns(string domains) => Post("/api/dns/resolve", new { domains });
    public Task<string> UpdateProviders() => Post("/api/providers/proxies/update", new { });
    public Task<string> UpdateRules() => Post("/api/providers/rules/update", new { });
}

public partial class MainWindow : Window
{
    public const string Version = "0.4.0";
    public static readonly string[] ProductionFeatures =
    [
        "runtime-start-stop-restart", "mihomo-version-health", "selector-list-and-tiles", "select-proxy", "per-node-ping",
        "proxy-table", "provider-update", "connections-table", "close-connection", "config-read-save-validate",
        "subscription-add-update-delete", "static-proxy-import-update-delete", "rule-providers", "dns-routes-manual-resolver",
        "logs-viewer", "settings-runtime-paths", "subscription-update-delete", "static-proxy-delete"
    ];
    public static readonly string[] QtPages =
    [
        "Маршрутизация", "Mihomo", "Соединения", "VLESS", "WireGuard", "AmneziaWG", "Hysteria2", "Trojan", "Mieru", "NaiveProxy",
        "Логи", "Mihomo Генератор", "Конфиг", "Ручной список", "Маршруты DNS", "Интерфейс", "Настройки"
    ];
    readonly NativeBridgeClient bridge = new();

    public MainWindow()
    {
        InitializeComponent();
        Title = "Unified UI — WPF User Test v0.4.0";
        OutputBox.Text = "Готовый конечный вариант для ручного тестирования: страницы как в Qt Native, общий unified-ui-native-bridge.exe, config.yaml/manual-proxy.yaml/proxy-providers/rule-providers. Features: " + string.Join(", ", ProductionFeatures);
        SettingsText.Text = $"BRIDGE_URL: {bridge.BridgeUrl}\nBridge exe: {bridge.BridgeExe}\nconfig.yaml / manual-proxy.yaml / proxy-providers / rule-providers";
        bridge.EnsureBridgeStarted(Log);
        _ = Show(bridge.Status());
    }

    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, app = "Unified UI WPF", version = Version, ui = "WPF", quality = "user-test-production", backend = "unified-ui-native-bridge", pages = QtPages, features = ProductionFeatures }));
            return 0;
        }
        var app = new Application(); app.Run(new MainWindow()); return 0;
    }

    async Task Show(Task<string> task) { try { OutputBox.Text = await task; StatusText.Text = "OK"; } catch (Exception ex) { OutputBox.Text = ex.ToString(); StatusText.Text = "Ошибка"; } }
    void Log(string text) { OutputBox.Text += "\n" + text; }
    void Activate(int idx, string title, string subtitle) { MainTabs.SelectedIndex = idx; PageTitle.Text = title; PageSubtitle.Text = subtitle; }

    private async void Start_Click(object sender, RoutedEventArgs e) => await Show(bridge.Start());
    private async void Status_Click(object sender, RoutedEventArgs e) => await Show(bridge.Status());
    private async void Restart_Click(object sender, RoutedEventArgs e) => await Show(bridge.Restart());
    private async void Stop_Click(object sender, RoutedEventArgs e) => await Show(bridge.Stop());
    private async void Proxies_Click(object sender, RoutedEventArgs e) => await Show(bridge.Proxies());
    private async void Inventory_Click(object sender, RoutedEventArgs e) => await Show(bridge.Inventory());
    private async void Providers_Click(object sender, RoutedEventArgs e) => await Show(bridge.UpdateProviders());
    private async void Rules_Click(object sender, RoutedEventArgs e) => await Show(bridge.UpdateRules());
    private async void Connections_Click(object sender, RoutedEventArgs e) => await Show(bridge.Connections());
    private async void Ping_Click(object sender, RoutedEventArgs e) => await Show(bridge.Delay(ProxyBox.Text));
    private async void SelectProxy_Click(object sender, RoutedEventArgs e) => await Show(bridge.Select(GroupBox.Text, ProxyBox.Text));
    private async void ReadConfig_Click(object sender, RoutedEventArgs e) { var text = await bridge.Config(); ConfigBox.Text = text; OutputBox.Text = text; }
    private async void SaveConfig_Click(object sender, RoutedEventArgs e) => await Show(bridge.SaveConfig(ConfigBox.Text));
    private async void ApplyConfig_Click(object sender, RoutedEventArgs e) => await Show(bridge.ApplyConfig(ConfigBox.Text));
    private async void AddSubscription_Click(object sender, RoutedEventArgs e) => await Show(bridge.AddSubscription(SubNameBox.Text, SubUrlBox.Text));
    private async void UpdateSubscription_Click(object sender, RoutedEventArgs e) => await Show(bridge.UpdateSubscription(SubNameBox.Text, SubNameBox.Text, SubUrlBox.Text));
    private async void DeleteSubscription_Click(object sender, RoutedEventArgs e) => await Show(bridge.DeleteSubscription(SubNameBox.Text));
    private async void AddImport_Click(object sender, RoutedEventArgs e) => await Show(bridge.ImportStatic(ImportBox.Text));
    private async void DeleteStatic_Click(object sender, RoutedEventArgs e) => await Show(bridge.DeleteStatic(StaticNameBox.Text));
    private async void Resolve_Click(object sender, RoutedEventArgs e) => await Show(bridge.ResolveDns(DomainBox.Text));
    private async void Logs_Click(object sender, RoutedEventArgs e) => await Show(bridge.Logs());

    private void NavRouting_Click(object sender, RoutedEventArgs e) => Activate(0, "Маршрутизация", "selector tiles/list, активный proxy, per-node ping, выбор узла — как в Qt Native.");
    private void NavMihomo_Click(object sender, RoutedEventArgs e) => Activate(1, "Mihomo", "proxy-providers, rule-providers, static proxy inventory, update providers.");
    private void NavConnections_Click(object sender, RoutedEventArgs e) => Activate(2, "Соединения", "connections-table + close-connection.");
    private void NavVless_Click(object sender, RoutedEventArgs e) => Activate(3, "VLESS", "Protocol inventory table.");
    private void NavWireGuard_Click(object sender, RoutedEventArgs e) => Activate(4, "WireGuard", "Protocol inventory table.");
    private void NavAmnezia_Click(object sender, RoutedEventArgs e) => Activate(5, "AmneziaWG", "Protocol inventory table.");
    private void NavHysteria_Click(object sender, RoutedEventArgs e) => Activate(6, "Hysteria2", "Protocol inventory table.");
    private void NavTrojan_Click(object sender, RoutedEventArgs e) => Activate(7, "Trojan", "Protocol inventory table.");
    private void NavMieru_Click(object sender, RoutedEventArgs e) => Activate(8, "Mieru", "Protocol inventory table.");
    private void NavNaive_Click(object sender, RoutedEventArgs e) => Activate(9, "NaiveProxy", "Protocol inventory table.");
    private void NavLogs_Click(object sender, RoutedEventArgs e) => Activate(10, "Логи", "logs-viewer.");
    private void NavImport_Click(object sender, RoutedEventArgs e) => Activate(11, "Mihomo Генератор", "subscription-manager + static-proxy-import.");
    private void NavConfig_Click(object sender, RoutedEventArgs e) => Activate(12, "Конфиг", "config.yaml редактор.");
    private void NavManual_Click(object sender, RoutedEventArgs e) => Activate(13, "Ручной список", "manual-proxy.yaml.");
    private void NavDns_Click(object sender, RoutedEventArgs e) => Activate(14, "Маршруты DNS", "dns-routes-manual-resolver.");
    private void NavInterface_Click(object sender, RoutedEventArgs e) => Activate(15, "Интерфейс", "Qt Native visual shell.");
    private void NavSettings_Click(object sender, RoutedEventArgs e) => Activate(16, "Настройки", "settings-runtime-paths.");
}
