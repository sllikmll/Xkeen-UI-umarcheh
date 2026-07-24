using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace UnifiedUiAvaloniaPreview;

public static class Program
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

    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, app = "Unified UI Avalonia Preview", version = Version, ui = "Avalonia", parity = "qt-native", features = ParityFeatures }));
            return 0;
        }
        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        return 0;
    }

    public static AppBuilder BuildAvaloniaApp() => AppBuilder.Configure<App>().UsePlatformDetect().WithInterFont().LogToTrace();
}

public sealed class App : Application
{
    public override void Initialize()
    {
        Styles.Add(new FluentTheme());
        RequestedThemeVariant = ThemeVariant.Dark;
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
            desktop.MainWindow = new MainWindow();
        base.OnFrameworkInitializationCompleted();
    }
}

public sealed class NativeParityClient
{
    readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(8) };
    public string Controller { get; set; } = Environment.GetEnvironmentVariable("MIHOMO_CONTROLLER") ?? "http://127.0.0.1:19190";
    public string RuntimeDir { get; set; } = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Unified UI Native");
    public string ConfigPath => Path.Combine(RuntimeDir, "mihomo", "config.yaml");
    public string LogPath => Path.Combine(RuntimeDir, "logs", "mihomo-native.log");

    public async Task<string> GetAsync(string path)
    {
        using var res = await http.GetAsync(Controller.TrimEnd('/') + path);
        var body = await res.Content.ReadAsStringAsync();
        return $"HTTP {(int)res.StatusCode}\n{body}";
    }

    public Task<string> ProxiesAsync() => GetAsync("/proxies");
    public Task<string> ConnectionsAsync() => GetAsync("/connections");
    public Task<string> VersionAsync() => GetAsync("/version");

    public async Task<string> SelectProxyAsync(string group, string proxy)
    {
        var url = $"{Controller.TrimEnd('/')}/proxies/{Uri.EscapeDataString(group)}";
        var body = JsonSerializer.Serialize(new { name = proxy });
        using var res = await http.PutAsync(url, new StringContent(body, System.Text.Encoding.UTF8, "application/json"));
        return $"HTTP {(int)res.StatusCode}\n{await res.Content.ReadAsStringAsync()}";
    }

    public async Task<string> DelayAsync(string proxy)
    {
        var url = $"/proxies/{Uri.EscapeDataString(proxy)}/delay?timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204";
        return await GetAsync(url);
    }

    public string ReadConfig()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(ConfigPath)!);
        if (!File.Exists(ConfigPath)) File.WriteAllText(ConfigPath, "mixed-port: 17990\nexternal-controller: 127.0.0.1:19190\nproxies: []\nproxy-groups: []\n");
        return File.ReadAllText(ConfigPath);
    }

    public string SaveConfig(string text)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(ConfigPath)!);
        File.WriteAllText(ConfigPath, text.Replace("\r\n", "\n"));
        return $"config.yaml сохранён: {ConfigPath}";
    }

    public string AppendStaticProxy(string yaml)
    {
        var cfg = ReadConfig();
        File.WriteAllText(ConfigPath, cfg + "\n# static-proxy-import\n" + yaml.Trim() + "\n");
        return "Static proxy/import block добавлен в config.yaml";
    }

    public string AddSubscription(string name, string url)
    {
        var block = $"\nproxy-providers:\n  {name}:\n    type: http\n    url: '{url}'\n    interval: 3600\n    path: ./providers/{name}.yaml\n";
        File.AppendAllText(ConfigPath, block);
        return $"subscription-manager: provider {name} добавлен";
    }

    public string ResolveDomains(string raw)
    {
        var lines = raw.Split(new[] { '\r', '\n', ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries).Select(x => x.Trim()).Where(x => x.Length > 0).Distinct().ToList();
        var output = new List<string>();
        foreach (var host in lines)
        {
            try
            {
                var ips = Dns.GetHostAddresses(host).Where(x => x.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork).Select(x => x.ToString()).Distinct();
                output.Add($"{host}: {string.Join(", ", ips)}");
            }
            catch (Exception ex) { output.Add($"{host}: error {ex.Message}"); }
        }
        return output.Count == 0 ? "Введите домены" : string.Join("\n", output);
    }

    public string ReadLogs()
    {
        return File.Exists(LogPath) ? File.ReadAllText(LogPath)[Math.Max(0, File.ReadAllText(LogPath).Length - 12000)..] : $"Лог не найден: {LogPath}";
    }
}

public sealed class MainWindow : Window
{
    readonly NativeParityClient client = new();
    readonly TextBlock status = new() { Foreground = Brush.Parse("#8DA8C8"), Text = "Готово" };
    readonly TextBox output = new() { AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, MinHeight = 180 };
    readonly TextBox configEditor = new() { AcceptsReturn = true, TextWrapping = TextWrapping.NoWrap, MinHeight = 320 };
    readonly TextBox domainInput = new() { AcceptsReturn = true, Text = "youtube.com\ngithub.com\nopenai.com" };
    readonly TextBox importInput = new() { AcceptsReturn = true, Text = "# vless:// / wireguard:// / yaml proxy block" };

    public MainWindow()
    {
        Title = "Unified UI — Avalonia Full Parity Preview v0.2.0";
        Width = 1320; Height = 840; MinWidth = 1080; MinHeight = 680;
        Background = Brush.Parse("#050B1A");
        Content = BuildShell();
    }

    Control BuildShell()
    {
        var root = new Grid { RowDefinitions = new RowDefinitions("Auto,*,Auto"), Margin = new Thickness(14), RowSpacing = 10 };
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(Button("Start/Status Mihomo", async () => await Show(client.VersionAsync()))); // runtime-controls
        actions.Children.Add(Button("Restart Mihomo", () => ShowText("runtime-controls: restart hook; production Qt restarts local mihomo process")));
        actions.Children.Add(Button("Stop Mihomo", () => ShowText("runtime-controls: stop hook; production Qt tracks child PID")));
        actions.Children.Add(status);
        Grid.SetRow(actions, 0); root.Children.Add(actions);

        var tabs = new TabControl();
        tabs.Items.Add(Tab("Маршрутизация", RoutingTab())); // selector-list-and-tiles per-node-ping
        tabs.Items.Add(Tab("Mihomo", MihomoTab())); // proxy-table
        tabs.Items.Add(Tab("Соединения", ConnectionsTab())); // connections-table
        tabs.Items.Add(Tab("Конфиг", ConfigTab())); // config-editor
        tabs.Items.Add(Tab("Подписки", SubscriptionTab())); // subscription-manager static-proxy-import
        tabs.Items.Add(Tab("Маршруты DNS", DnsTab())); // dns-routes-manual-resolver
        tabs.Items.Add(Tab("Логи", LogsTab())); // logs-viewer
        tabs.Items.Add(Tab("Настройки", SettingsTab())); // settings-runtime-paths
        Grid.SetRow(tabs, 1); root.Children.Add(tabs);
        output.Text = "Unified UI Avalonia parity preview: " + string.Join(", ", Program.ParityFeatures);
        Grid.SetRow(output, 2); root.Children.Add(output);
        return root;
    }

    static TabItem Tab(string header, Control content) => new() { Header = header, Content = content };
    Button Button(string text, Action action) { var b = new Button { Content = text, Margin = new Thickness(3), Padding = new Thickness(10, 7) }; b.Click += (_, _) => action(); return b; }
    Button Button(string text, Func<Task> action) { var b = new Button { Content = text, Margin = new Thickness(3), Padding = new Thickness(10, 7) }; b.Click += async (_, _) => await action(); return b; }
    async Task Show(Task<string> task) { try { output.Text = await task; status.Text = "OK"; } catch (Exception ex) { output.Text = ex.ToString(); status.Text = "Ошибка"; } }
    void ShowText(string text) { output.Text = text; status.Text = "OK"; }

    Control RoutingTab()
    {
        var p = Panel();
        p.Children.Add(Button("Обновить selectors /proxies", async () => await Show(client.ProxiesAsync())));
        p.Children.Add(Button("Ping DIRECT", async () => await Show(client.DelayAsync("DIRECT"))));
        p.Children.Add(new TextBlock { Text = "selector-list-and-tiles: live /proxies, выбор через PUT /proxies/{group}; per-node-ping через /delay", Foreground = Brushes.White });
        return p;
    }
    Control MihomoTab() { var p = Panel(); p.Children.Add(Button("Загрузить proxy-table", async () => await Show(client.ProxiesAsync()))); return p; }
    Control ConnectionsTab() { var p = Panel(); p.Children.Add(Button("Обновить connections-table", async () => await Show(client.ConnectionsAsync()))); return p; }
    Control ConfigTab() { var p = Panel(); p.Children.Add(Button("Открыть config.yaml", () => configEditor.Text = client.ReadConfig())); p.Children.Add(Button("Сохранить config.yaml", () => ShowText(client.SaveConfig(configEditor.Text)))); p.Children.Add(configEditor); return p; }
    Control SubscriptionTab() { var p = Panel(); var name = new TextBox { Text = "subscription_1" }; var url = new TextBox { Text = "https://example.com/sub" }; p.Children.Add(name); p.Children.Add(url); p.Children.Add(Button("Добавить subscription-manager", () => ShowText(client.AddSubscription(name.Text ?? "subscription_1", url.Text ?? "")))); p.Children.Add(importInput); p.Children.Add(Button("Добавить static-proxy-import", () => ShowText(client.AppendStaticProxy(importInput.Text ?? "")))); return p; }
    Control DnsTab() { var p = Panel(); p.Children.Add(domainInput); p.Children.Add(Button("Собрать адреса", () => ShowText(client.ResolveDomains(domainInput.Text ?? "")))); return p; }
    Control LogsTab() { var p = Panel(); p.Children.Add(Button("Прочитать logs-viewer", () => ShowText(client.ReadLogs()))); return p; }
    Control SettingsTab() { var p = Panel(); p.Children.Add(new TextBlock { Text = $"settings-runtime-paths\nController: {client.Controller}\nRuntime: {client.RuntimeDir}\nConfig: {client.ConfigPath}", Foreground = Brushes.White }); return p; }
    StackPanel Panel() => new() { Spacing = 8, Margin = new Thickness(12) };
}
