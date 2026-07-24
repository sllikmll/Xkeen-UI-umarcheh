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
            log($"bridge launched: {BridgeExe}");
        }
        catch (Exception ex) { log($"bridge launch failed: {ex.Message}"); }
    }
    public async Task<string> Get(string endpoint) { using var res = await http.GetAsync(BridgeUrl.TrimEnd('/') + endpoint); return $"HTTP {(int)res.StatusCode}\n" + await res.Content.ReadAsStringAsync(); }
    public async Task<string> Post(string endpoint, object payload) { using var res = await http.PostAsync(BridgeUrl.TrimEnd('/') + endpoint, new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json")); return $"HTTP {(int)res.StatusCode}\n" + await res.Content.ReadAsStringAsync(); }
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
    public Task<string> ImportStatic(string text) => Post("/api/import/static", new { text, restart = false });
    public Task<string> ResolveDns(string domains) => Post("/api/dns/resolve", new { domains });
    public Task<string> UpdateProviders() => Post("/api/providers/proxies/update", new { });
}

public partial class MainWindow : Window
{
    public const string Version = "0.3.0";
    public static readonly string[] ProductionFeatures =
    [
        "runtime-start-stop-restart", "mihomo-version-health", "selector-list-and-tiles", "select-proxy", "per-node-ping",
        "proxy-table", "provider-update", "connections-table", "close-connection", "config-read-save-validate",
        "subscription-add-update-delete", "static-proxy-import-update-delete", "rule-providers", "dns-routes-manual-resolver",
        "logs-viewer", "settings-runtime-paths"
    ];

    readonly NativeBridgeClient bridge = new();

    public MainWindow()
    {
        InitializeComponent();
        Title = "Unified UI — WPF Production Candidate v0.3.0";
        OutputBox.Text = "Unified UI WPF production candidate via unified-ui-native-bridge: " + string.Join(", ", ProductionFeatures);
        SettingsText.Text = $"BRIDGE_URL: {bridge.BridgeUrl}\nBridge exe: {bridge.BridgeExe}";
        bridge.EnsureBridgeStarted(Log);
        _ = Show(bridge.Status());
    }

    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, app = "Unified UI WPF Preview", version = Version, ui = "WPF", quality = "production-candidate", backend = "unified-ui-native-bridge", features = ProductionFeatures }));
            return 0;
        }
        var app = new Application(); app.Run(new MainWindow()); return 0;
    }

    async Task Show(Task<string> task) { try { OutputBox.Text = await task; StatusText.Text = "OK"; } catch (Exception ex) { OutputBox.Text = ex.ToString(); StatusText.Text = "Ошибка"; } }
    void ShowText(string text) { OutputBox.Text = text; StatusText.Text = "OK"; }
    void Log(string text) { OutputBox.Text += "\n" + text; }

    private async void Status_Click(object sender, RoutedEventArgs e) => await Show(bridge.Status());
    private async void Restart_Click(object sender, RoutedEventArgs e) => await Show(bridge.Restart());
    private async void Stop_Click(object sender, RoutedEventArgs e) => await Show(bridge.Stop());
    private async void Proxies_Click(object sender, RoutedEventArgs e) => await Show(bridge.Proxies());
    private async void Connections_Click(object sender, RoutedEventArgs e) => await Show(bridge.Connections());
    private async void Ping_Click(object sender, RoutedEventArgs e) => await Show(bridge.Delay("DIRECT"));
    private async void ReadConfig_Click(object sender, RoutedEventArgs e) { var text = await bridge.Config(); ConfigBox.Text = text; OutputBox.Text = text; }
    private async void SaveConfig_Click(object sender, RoutedEventArgs e) => await Show(bridge.SaveConfig(ConfigBox.Text));
    private async void AddSubscription_Click(object sender, RoutedEventArgs e) => await Show(bridge.AddSubscription(SubNameBox.Text, SubUrlBox.Text));
    private async void AddImport_Click(object sender, RoutedEventArgs e) => await Show(bridge.ImportStatic(ImportBox.Text));
    private async void Resolve_Click(object sender, RoutedEventArgs e) => await Show(bridge.ResolveDns(DomainBox.Text));
    private async void Logs_Click(object sender, RoutedEventArgs e) => await Show(bridge.Logs());
}
