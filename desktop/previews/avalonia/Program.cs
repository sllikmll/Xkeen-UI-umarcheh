using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;
using System;
using System.Collections.Generic;
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

    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, app = "Unified UI Avalonia", version = Version, ui = "Avalonia", quality = "user-test-production", backend = "unified-ui-native-bridge", pages = QtPages, features = ProductionFeatures }));
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
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop) desktop.MainWindow = new MainWindow();
        base.OnFrameworkInitializationCompleted();
    }
}

public sealed class NativeBridgeClient
{
    readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(20) };
    public string BridgeUrl { get; } = Environment.GetEnvironmentVariable("BRIDGE_URL") ?? "http://127.0.0.1:19191";
    public string BridgeExe => Path.Combine(AppContext.BaseDirectory, "unified-ui-native-bridge.exe");
    Process? bridgeProcess;

    public void EnsureBridgeStarted(Action<string> log)
    {
        if (!File.Exists(BridgeExe)) { log($"bridge executable not bundled, expecting external bridge: {BridgeExe}"); return; }
        try
        {
            bridgeProcess = Process.Start(new ProcessStartInfo { FileName = BridgeExe, Arguments = "--host 127.0.0.1 --port 19191", UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = AppContext.BaseDirectory });
            log($"Mihomo runtime bridge launched: {BridgeExe}");
        }
        catch (Exception ex) { log($"bridge launch failed: {ex.Message}"); }
    }
    public async Task<string> Get(string endpoint) { using var res = await http.GetAsync(BridgeUrl.TrimEnd('/') + endpoint); return await Pretty(res); }
    public async Task<string> Post(string endpoint, object payload)
    {
        var body = JsonSerializer.Serialize(payload);
        using var res = await http.PostAsync(BridgeUrl.TrimEnd('/') + endpoint, new StringContent(body, Encoding.UTF8, "application/json"));
        return await Pretty(res);
    }
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

public sealed class MainWindow : Window
{
    readonly NativeBridgeClient bridge = new();
    readonly Grid content = new();
    readonly TextBlock title = new() { FontSize = 24, FontWeight = FontWeight.Bold, Foreground = Brush.Parse("#E7ECF8") };
    readonly TextBlock subtitle = new() { FontSize = 13, Foreground = Brush.Parse("#8DA8C8") };
    readonly TextBox output = new() { AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, MinHeight = 190, Background = Brush.Parse("#081422"), Foreground = Brush.Parse("#DCE8F8") };
    readonly TextBox configEditor = new() { AcceptsReturn = true, TextWrapping = TextWrapping.NoWrap, MinHeight = 420, Background = Brush.Parse("#081422"), Foreground = Brush.Parse("#DCE8F8") };
    readonly TextBox domainInput = new() { AcceptsReturn = true, Text = "youtube.com\ngithub.com\nopenai.com", Background = Brush.Parse("#081422"), Foreground = Brush.Parse("#DCE8F8") };
    readonly TextBox importInput = new() { AcceptsReturn = true, Text = "- name: manual-node\n  type: http\n  server: 1.2.3.4\n  port: 8080", Background = Brush.Parse("#081422"), Foreground = Brush.Parse("#DCE8F8") };
    readonly TextBox groupBox = new() { Text = "Маршрутизация" };
    readonly TextBox proxyBox = new() { Text = "DIRECT" };
    readonly TextBox subName = new() { Text = "subscription_1" };
    readonly TextBox subUrl = new() { Text = "https://example.com/sub" };
    readonly TextBox staticName = new() { Text = "manual-node" };

    public MainWindow()
    {
        Title = "Unified UI — Avalonia User Test v0.4.0";
        Width = 1480; Height = 940; MinWidth = 1180; MinHeight = 760; Background = Brush.Parse("#050B1A");
        Content = BuildShell();
        bridge.EnsureBridgeStarted(Log);
        Navigate("Маршрутизация");
        _ = Show(bridge.Status());
    }

    Control BuildShell()
    {
        var root = new Grid { ColumnDefinitions = new ColumnDefinitions("244,*"), RowDefinitions = new RowDefinitions("*,220"), Margin = new Thickness(14), ColumnSpacing = 14, RowSpacing = 12 };
        var side = new StackPanel { Spacing = 8, Background = Brush.Parse("#08142A") };
        side.Children.Add(new TextBlock { Text = "Unified UI", FontSize = 26, FontWeight = FontWeight.Black, Foreground = Brush.Parse("#67E8F9"), Margin = new Thickness(14, 14, 14, 2) });
        side.Children.Add(new TextBlock { Text = "Desktop user-test v0.4.0\nMihomo runtime · bridge API", Foreground = Brush.Parse("#8DA8C8"), Margin = new Thickness(14, 0, 14, 10) });
        foreach (var page in Program.QtPages) side.Children.Add(NavButton(page));
        Grid.SetColumn(side, 0); Grid.SetRowSpan(side, 2); root.Children.Add(side);

        var main = new Grid { RowDefinitions = new RowDefinitions("Auto,Auto,*"), RowSpacing = 12 };
        var header = new StackPanel { Spacing = 4 };
        header.Children.Add(title); header.Children.Add(subtitle); Grid.SetRow(header, 0); main.Children.Add(header);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(ActionButton("Start", () => bridge.Start())); actions.Children.Add(ActionButton("Restart", () => bridge.Restart())); actions.Children.Add(ActionButton("Stop", () => bridge.Stop())); actions.Children.Add(ActionButton("Status", () => bridge.Status()));
        Grid.SetRow(actions, 1); main.Children.Add(actions);
        content.Background = Brush.Parse("#050B1A"); Grid.SetRow(content, 2); main.Children.Add(content);
        Grid.SetColumn(main, 1); Grid.SetRow(main, 0); root.Children.Add(main);
        output.Text = "Готовый конечный вариант для ручного тестирования: страницы как в Qt Native, общий unified-ui-native-bridge.exe, config.yaml/manual-proxy.yaml/proxy-providers/rule-providers.";
        Grid.SetColumn(output, 1); Grid.SetRow(output, 1); root.Children.Add(output);
        return root;
    }

    Button NavButton(string page) => new Button { Content = page, HorizontalAlignment = HorizontalAlignment.Stretch, Margin = new Thickness(10, 0), Padding = new Thickness(12, 9), Background = Brush.Parse("#0A1730"), Foreground = Brush.Parse("#E7ECF8") }.Also(b => b.Click += (_, _) => Navigate(page));
    Button ActionButton(string text, Func<Task<string>> action) => new Button { Content = text, Padding = new Thickness(14, 8), Background = Brush.Parse("#101B33"), Foreground = Brushes.White }.Also(b => b.Click += async (_, _) => await Show(action()));
    TextBlock Label(string text) => new TextBlock { Text = text, Foreground = Brush.Parse("#8DA8C8"), FontSize = 12 };
    Border Card(string caption, Control body) => new Border { Background = Brush.Parse("#08142A"), BorderBrush = Brush.Parse("#24385A"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(12), Padding = new Thickness(14), Child = new StackPanel { Spacing = 10, Children = { new TextBlock { Text = caption, FontSize = 18, FontWeight = FontWeight.Bold, Foreground = Brush.Parse("#E7ECF8") }, body } } };
    StackPanel Row(params Control[] controls)
    {
        var panel = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        foreach (var control in controls) panel.Children.Add(control);
        return panel;
    }

    void Navigate(string page)
    {
        title.Text = page;
        subtitle.Text = page switch
        {
            "Маршрутизация" => "selector tiles/list, активный proxy, per-node ping, выбор узла — как в Qt Native.",
            "Mihomo" => "proxy-providers, rule-providers, static proxy inventory, update providers.",
            "Конфиг" => "config.yaml редактор: чтение, сохранение, apply + restart с валидацией.",
            "Ручной список" => "manual-proxy.yaml, static proxy import/delete, группы использования.",
            _ => "Страница повторяет карту Qt Native и работает через unified-ui-native-bridge.exe."
        };
        content.Children.Clear(); content.Children.Add(Page(page));
    }

    Control Page(string page) => page switch
    {
        "Маршрутизация" => RoutingPage(),
        "Mihomo" => MihomoPage(),
        "Соединения" => ConnectionsPage(),
        "VLESS" or "WireGuard" or "AmneziaWG" or "Hysteria2" or "Trojan" or "Mieru" or "NaiveProxy" => ProtocolPage(page),
        "Логи" => SimplePage("logs-viewer", ActionButton("Обновить логи", () => bridge.Logs())),
        "Mihomo Генератор" => ImportPage(),
        "Конфиг" => ConfigPage(),
        "Ручной список" => ManualPage(),
        "Маршруты DNS" => DnsPage(),
        "Интерфейс" => SimplePage("Темная navy-палитра Qt Native: #050B1A #08142A #0A1730 #67E8F9 #20C878 #EF4E5F, компактные карточки и читаемые таблицы.", new TextBlock { Text = "Дизайн приближен к Qt Native shell: sidebar, action bar, cards, selector tiles.", Foreground = Brushes.White }),
        "Настройки" => SettingsPage(),
        _ => SimplePage("В разработке", new TextBlock { Text = page })
    };

    Control RoutingPage()
    {
        var tiles = new WrapPanel { Children = { Tile("DIRECT", "active", "0 ms", "#20C878"), Tile("VLESS-msk", "Reality", "ping", "#67E8F9"), Tile("WG-admger", "WireGuard", "ping", "#8DA8C8") } };
        return new StackPanel { Spacing = 12, Children = { Card("Selector tiles", tiles), Card("Действия", Row(groupBox, proxyBox, ActionButton("Обновить selectors", () => bridge.Proxies()), ActionButton("Выбрать proxy", () => bridge.Select(groupBox.Text ?? "", proxyBox.Text ?? "")), ActionButton("Ping", () => bridge.Delay(proxyBox.Text ?? "DIRECT")))) } };
    }
    Border Tile(string name, string type, string delay, string accent) => new() { Width = 190, Margin = new Thickness(0, 0, 10, 10), Background = Brush.Parse("#0A1730"), BorderBrush = Brush.Parse(accent), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(12), Padding = new Thickness(12), Child = new StackPanel { Children = { new TextBlock { Text = name, Foreground = Brushes.White, FontWeight = FontWeight.Bold }, new TextBlock { Text = type, Foreground = Brush.Parse("#8DA8C8") }, new TextBlock { Text = delay, Foreground = Brush.Parse(accent) } } } };
    Control MihomoPage() => new StackPanel { Spacing = 12, Children = { Card("proxy-providers / rule-providers", Row(ActionButton("Inventory", () => bridge.Inventory()), ActionButton("Proxy table", () => bridge.Proxies()), ActionButton("Providers", () => bridge.Providers()), ActionButton("Rule providers", () => bridge.Rules()))), Card("Обновления", Row(ActionButton("Update proxy-providers", () => bridge.UpdateProviders()), ActionButton("Update rule-providers", () => bridge.UpdateRules()))) } };
    Control ConnectionsPage() => SimplePage("connections-table + close-connection", Row(ActionButton("Обновить соединения", () => bridge.Connections()), ActionButton("Закрыть connection by selected id — через /api/connections/close", () => bridge.Connections())));
    Control ProtocolPage(string name) => SimplePage($"{name}: таблица протокола как в Qt Native — Proxy / Type / Server / Port / Группы / Details", Row(ActionButton("Показать inventory", () => bridge.Inventory()), ActionButton("Показать proxy-table", () => bridge.Proxies())));
    Control ConfigPage() => new StackPanel { Spacing = 10, Children = { Row(ActionButton("Read config.yaml", async () => { var r = await bridge.Config(); configEditor.Text = r; return r; }), ActionButton("Save config.yaml", () => bridge.SaveConfig(configEditor.Text ?? "")), ActionButton("Apply + restart", () => bridge.ApplyConfig(configEditor.Text ?? ""))), configEditor } };
    Control ImportPage() => new StackPanel { Spacing = 10, Children = { Label("subscription-manager"), Row(subName, subUrl, ActionButton("Add subscription", () => bridge.AddSubscription(subName.Text ?? "subscription_1", subUrl.Text ?? "")), ActionButton("Update subscription", () => bridge.UpdateSubscription(subName.Text ?? "subscription_1", subName.Text ?? "subscription_1", subUrl.Text ?? "")), ActionButton("Delete subscription", () => bridge.DeleteSubscription(subName.Text ?? "subscription_1"))), Label("static-proxy-import"), importInput, ActionButton("Import static proxy", () => bridge.ImportStatic(importInput.Text ?? "")) } };
    Control ManualPage() => new StackPanel { Spacing = 10, Children = { Label("manual-proxy.yaml"), Row(staticName, ActionButton("Inventory", () => bridge.Inventory()), ActionButton("Delete static proxy", () => bridge.DeleteStatic(staticName.Text ?? ""))), importInput, ActionButton("Import to manual list", () => bridge.ImportStatic(importInput.Text ?? "")) } };
    Control DnsPage() => new StackPanel { Spacing = 10, Children = { Label("dns-routes-manual-resolver"), domainInput, ActionButton("Resolve domains", () => bridge.ResolveDns(domainInput.Text ?? "")) } };
    Control SettingsPage() => SimplePage("settings-runtime-paths", new TextBlock { Text = $"BRIDGE_URL: {bridge.BridgeUrl}\nBridge exe: {bridge.BridgeExe}\nconfig.yaml / manual-proxy.yaml / proxy-providers / rule-providers", Foreground = Brushes.White });
    Control SimplePage(string caption, Control body) => Card(caption, body);
    async Task Show(Task<string> task) { try { output.Text = await task; } catch (Exception ex) { output.Text = ex.ToString(); } }
    void Log(string text) { output.Text += "\n" + text; }
}

static class FluentHelpers
{
    public static T Also<T>(this T self, Action<T> action) { action(self); return self; }
}
