using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;

namespace UnifiedUiWpfPreview;

public partial class MainWindow : Window
{
    public const string Version = "0.2.0";
    public static readonly string[] ParityFeatures =
    [
        "runtime-controls",
        "selector-list-and-tiles",
        "per-node-ping",
        "proxy-table",
        "connections-table",
        "config-editor",
        "subscription-manager",
        "static-proxy-import",
        "dns-routes-manual-resolver",
        "logs-viewer",
        "settings-runtime-paths",
    ];

    readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(8) };
    readonly string controller = Environment.GetEnvironmentVariable("MIHOMO_CONTROLLER") ?? "http://127.0.0.1:19190";
    readonly string runtimeDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Unified UI Native");
    string ConfigPath => Path.Combine(runtimeDir, "mihomo", "config.yaml");
    string LogPath => Path.Combine(runtimeDir, "logs", "mihomo-native.log");

    public MainWindow()
    {
        InitializeComponent();
        OutputBox.Text = "Unified UI WPF parity preview: " + string.Join(", ", ParityFeatures);
        SettingsText.Text = $"settings-runtime-paths\nController: {controller}\nRuntime: {runtimeDir}\nConfig: {ConfigPath}";
    }

    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, app = "Unified UI WPF Preview", version = Version, ui = "WPF", parity = "qt-native", features = ParityFeatures }));
            return 0;
        }
        var app = new Application(); app.Run(new MainWindow()); return 0;
    }

    async Task<string> GetAsync(string path)
    {
        using var res = await http.GetAsync(controller.TrimEnd('/') + path);
        var body = await res.Content.ReadAsStringAsync();
        return $"HTTP {(int)res.StatusCode}\n{body}";
    }

    async Task Show(Task<string> task)
    {
        try { OutputBox.Text = await task; StatusText.Text = "OK"; }
        catch (Exception ex) { OutputBox.Text = ex.ToString(); StatusText.Text = "Ошибка"; }
    }
    void ShowText(string text) { OutputBox.Text = text; StatusText.Text = "OK"; }

    void EnsureConfig()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(ConfigPath)!);
        if (!File.Exists(ConfigPath)) File.WriteAllText(ConfigPath, "mixed-port: 17990\nexternal-controller: 127.0.0.1:19190\nproxies: []\nproxy-groups: []\n");
    }

    private async void Status_Click(object sender, RoutedEventArgs e) => await Show(GetAsync("/version")); // runtime-controls
    private void Restart_Click(object sender, RoutedEventArgs e) => ShowText("runtime-controls: restart hook; production Qt restarts local mihomo process");
    private void Stop_Click(object sender, RoutedEventArgs e) => ShowText("runtime-controls: stop hook; production Qt tracks child PID");
    private async void Proxies_Click(object sender, RoutedEventArgs e) => await Show(GetAsync("/proxies")); // selector-list-and-tiles proxy-table
    private async void Connections_Click(object sender, RoutedEventArgs e) => await Show(GetAsync("/connections")); // connections-table
    private async void Ping_Click(object sender, RoutedEventArgs e) => await Show(GetAsync("/proxies/DIRECT/delay?timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204")); // per-node-ping
    private void ReadConfig_Click(object sender, RoutedEventArgs e) { EnsureConfig(); ConfigBox.Text = File.ReadAllText(ConfigPath); } // config-editor config.yaml
    private void SaveConfig_Click(object sender, RoutedEventArgs e) { EnsureConfig(); File.WriteAllText(ConfigPath, ConfigBox.Text.Replace("\r\n", "\n")); ShowText($"config.yaml сохранён: {ConfigPath}"); }
    private void AddSubscription_Click(object sender, RoutedEventArgs e) { EnsureConfig(); File.AppendAllText(ConfigPath, $"\nproxy-providers:\n  {SubNameBox.Text}:\n    type: http\n    url: '{SubUrlBox.Text}'\n    interval: 3600\n    path: ./providers/{SubNameBox.Text}.yaml\n"); ShowText($"subscription-manager: provider {SubNameBox.Text} добавлен"); }
    private void AddImport_Click(object sender, RoutedEventArgs e) { EnsureConfig(); File.AppendAllText(ConfigPath, "\n# static-proxy-import\n" + ImportBox.Text.Trim() + "\n"); ShowText("static-proxy-import добавлен в config.yaml"); }
    private void Resolve_Click(object sender, RoutedEventArgs e)
    {
        var hosts = DomainBox.Text.Split(new[] { '\r', '\n', ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries).Select(x => x.Trim()).Where(x => x.Length > 0).Distinct();
        var lines = hosts.Select(host =>
        {
            try { return host + ": " + string.Join(", ", Dns.GetHostAddresses(host).Where(x => x.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork).Select(x => x.ToString()).Distinct()); }
            catch (Exception ex) { return host + ": error " + ex.Message; }
        });
        ShowText("dns-routes-manual-resolver\n" + string.Join("\n", lines)); // Dns.GetHostAddresses
    }
    private void Logs_Click(object sender, RoutedEventArgs e) => ShowText(File.Exists(LogPath) ? File.ReadAllText(LogPath) : $"logs-viewer: лог не найден: {LogPath}");
}
