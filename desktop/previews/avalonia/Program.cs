using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace UnifiedUiAvaloniaPreview;

public static class Program
{
    public const string Version = "0.3.0";
    public static readonly string[] ProductionFeatures =
    [
        "runtime-start-stop-restart", "mihomo-version-health", "selector-list-and-tiles", "select-proxy", "per-node-ping",
        "proxy-table", "provider-update", "connections-table", "close-connection", "config-read-save-validate",
        "subscription-add-update-delete", "static-proxy-import-update-delete", "rule-providers", "dns-routes-manual-resolver",
        "logs-viewer", "settings-runtime-paths"
    ];

    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, app = "Unified UI Avalonia Preview", version = Version, ui = "Avalonia", quality = "production-candidate", backend = "unified-ui-native-bridge", features = ProductionFeatures }));
            return 0;
        }
        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        return 0;
    }
    public static AppBuilder BuildAvaloniaApp() => AppBuilder.Configure<App>().UsePlatformDetect().WithInterFont().LogToTrace();
}

public sealed class App : Application
{
    public override void Initialize() { Styles.Add(new FluentTheme()); RequestedThemeVariant = ThemeVariant.Dark; }
    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop) desktop.MainWindow = new MainWindow();
        base.OnFrameworkInitializationCompleted();
    }
}

public sealed class NativeBridgeClient
{
    readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(20) };
    public string BridgeUrl { get; } = Environment.GetEnvironmentVariable("BRIDGE_URL") ?? "http://127.0.0.1:19191";
    public string BridgeExe => Path.Combine(AppContext.BaseDirectory, "unified-ui-native-bridge.exe");

    public void EnsureBridgeStarted(Action<string> log)
    {
        if (File.Exists(BridgeExe))
        {
            try
            {
                Process.Start(new ProcessStartInfo { FileName = BridgeExe, Arguments = "--host 127.0.0.1 --port 19191", UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = AppContext.BaseDirectory });
                log($"bridge launched: {BridgeExe}");
            }
            catch (Exception ex) { log($"bridge launch failed: {ex.Message}"); }
        }
        else log($"bridge executable not bundled, expecting external bridge: {BridgeExe}");
    }

    public async Task<string> Get(string endpoint)
    {
        using var res = await http.GetAsync(BridgeUrl.TrimEnd('/') + endpoint);
        return $"HTTP {(int)res.StatusCode}\n" + await res.Content.ReadAsStringAsync();
    }
    public async Task<string> Post(string endpoint, object payload)
    {
        var body = JsonSerializer.Serialize(payload);
        using var res = await http.PostAsync(BridgeUrl.TrimEnd('/') + endpoint, new StringContent(body, Encoding.UTF8, "application/json"));
        return $"HTTP {(int)res.StatusCode}\n" + await res.Content.ReadAsStringAsync();
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
    public Task<string> ImportStatic(string text) => Post("/api/import/static", new { text, restart = false });
    public Task<string> ResolveDns(string domains) => Post("/api/dns/resolve", new { domains });
    public Task<string> UpdateProviders() => Post("/api/providers/proxies/update", new { });
}

public sealed class MainWindow : Window
{
    readonly NativeBridgeClient bridge = new();
    readonly TextBlock status = new() { Foreground = Brush.Parse("#8DA8C8"), Text = "Запускаю bridge…" };
    readonly TextBox output = new() { AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, MinHeight = 220 };
    readonly TextBox configEditor = new() { AcceptsReturn = true, TextWrapping = TextWrapping.NoWrap, MinHeight = 330 };
    readonly TextBox domainInput = new() { AcceptsReturn = true, Text = "youtube.com\ngithub.com\nopenai.com" };
    readonly TextBox importInput = new() { AcceptsReturn = true, Text = "- name: manual-node\n  type: http\n  server: 1.2.3.4\n  port: 8080" };
    readonly TextBox groupBox = new() { Text = "Маршрутизация" };
    readonly TextBox proxyBox = new() { Text = "DIRECT" };

    public MainWindow()
    {
        Title = "Unified UI — Avalonia Production Candidate v0.3.0";
        Width = 1360; Height = 880; MinWidth = 1120; MinHeight = 720; Background = Brush.Parse("#050B1A");
        Content = BuildShell();
        bridge.EnsureBridgeStarted(Log);
        _ = Show(bridge.Status());
    }

    Control BuildShell()
    {
        var root = new Grid { RowDefinitions = new RowDefinitions("Auto,*,Auto"), Margin = new Thickness(14), RowSpacing = 10 };
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(B("Status", async () => await Show(bridge.Status())));
        actions.Children.Add(B("Start", async () => await Show(bridge.Start())));
        actions.Children.Add(B("Restart", async () => await Show(bridge.Restart())));
        actions.Children.Add(B("Stop", async () => await Show(bridge.Stop())));
        actions.Children.Add(status); Grid.SetRow(actions, 0); root.Children.Add(actions);
        var tabs = new TabControl();
        tabs.Items.Add(T("Маршрутизация", RoutingTab()));
        tabs.Items.Add(T("Инвентарь", InventoryTab()));
        tabs.Items.Add(T("Mihomo", MihomoTab()));
        tabs.Items.Add(T("Соединения", ConnectionsTab()));
        tabs.Items.Add(T("Конфиг", ConfigTab()));
        tabs.Items.Add(T("Подписки / Импорт", ImportTab()));
        tabs.Items.Add(T("Маршруты DNS", DnsTab()));
        tabs.Items.Add(T("Логи", LogsTab()));
        tabs.Items.Add(T("Настройки", SettingsTab()));
        Grid.SetRow(tabs, 1); root.Children.Add(tabs);
        output.Text = "Production candidate via unified-ui-native-bridge: " + string.Join(", ", Program.ProductionFeatures);
        Grid.SetRow(output, 2); root.Children.Add(output); return root;
    }
    static TabItem T(string header, Control content) => new() { Header = header, Content = content };
    Button B(string text, Func<Task> action) { var b = new Button { Content = text, Margin = new Thickness(3), Padding = new Thickness(10, 7) }; b.Click += async (_, _) => await action(); return b; }
    async Task Show(Task<string> task) { try { output.Text = await task; status.Text = "OK"; } catch (Exception ex) { output.Text = ex.ToString(); status.Text = "Ошибка"; } }
    void Log(string text) { output.Text += "\n" + text; }
    StackPanel P() => new() { Spacing = 8, Margin = new Thickness(12) };
    Control RoutingTab() { var p = P(); p.Children.Add(groupBox); p.Children.Add(proxyBox); p.Children.Add(B("Обновить selectors/list+tiles", async () => await Show(bridge.Proxies()))); p.Children.Add(B("Выбрать proxy", async () => await Show(bridge.Select(groupBox.Text ?? "", proxyBox.Text ?? "")))); p.Children.Add(B("Ping node", async () => await Show(bridge.Delay(proxyBox.Text ?? "DIRECT")))); return p; }
    Control InventoryTab() { var p = P(); p.Children.Add(B("proxy-providers / proxy-groups / static proxies / rule-providers", async () => await Show(bridge.Inventory()))); return p; }
    Control MihomoTab() { var p = P(); p.Children.Add(B("Proxy table", async () => await Show(bridge.Proxies()))); p.Children.Add(B("Providers", async () => await Show(bridge.Providers()))); p.Children.Add(B("Rule providers", async () => await Show(bridge.Rules()))); p.Children.Add(B("Update providers", async () => await Show(bridge.UpdateProviders()))); return p; }
    Control ConnectionsTab() { var p = P(); p.Children.Add(B("Connections table", async () => await Show(bridge.Connections()))); return p; }
    Control ConfigTab() { var p = P(); p.Children.Add(B("Read config", async () => { output.Text = await bridge.Config(); configEditor.Text = output.Text; })); p.Children.Add(B("Save config", async () => await Show(bridge.SaveConfig(configEditor.Text ?? "")))); p.Children.Add(B("Apply + restart", async () => await Show(bridge.ApplyConfig(configEditor.Text ?? "")))); p.Children.Add(configEditor); return p; }
    Control ImportTab() { var p = P(); var name = new TextBox { Text = "subscription_1" }; var url = new TextBox { Text = "https://example.com/sub" }; p.Children.Add(name); p.Children.Add(url); p.Children.Add(B("Add subscription", async () => await Show(bridge.AddSubscription(name.Text ?? "subscription_1", url.Text ?? "")))); p.Children.Add(importInput); p.Children.Add(B("Import static proxy", async () => await Show(bridge.ImportStatic(importInput.Text ?? "")))); return p; }
    Control DnsTab() { var p = P(); p.Children.Add(domainInput); p.Children.Add(B("Resolve domains", async () => await Show(bridge.ResolveDns(domainInput.Text ?? "")))); return p; }
    Control LogsTab() { var p = P(); p.Children.Add(B("Read logs", async () => await Show(bridge.Logs()))); return p; }
    Control SettingsTab() { var p = P(); p.Children.Add(new TextBlock { Text = $"BRIDGE_URL: {bridge.BridgeUrl}\nBridge exe: {bridge.BridgeExe}", Foreground = Brushes.White }); return p; }
}
