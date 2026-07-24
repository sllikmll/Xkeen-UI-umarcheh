using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;
using System;
using System.Diagnostics;
using System.Linq;

namespace UnifiedUiAvaloniaPreview;

public static class Program
{
    public static int Main(string[] args)
    {
        if (args.Contains("--smoke"))
        {
            Console.WriteLine("{\"ok\":true,\"app\":\"Unified UI Avalonia Preview\",\"version\":\"0.1.0\",\"ui\":\"Avalonia\"}");
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

public sealed class MainWindow : Window
{
    readonly string[] tabs = ["Маршрутизация", "Mihomo", "Соединения", "WireGuard", "VLESS", "Маршруты DNS", "Логи"];

    public MainWindow()
    {
        Title = "Unified UI — Avalonia Preview";
        Width = 1240;
        Height = 760;
        MinWidth = 980;
        MinHeight = 620;
        Background = Brush.Parse("#050B1A");
        Content = BuildShell();
    }

    Control BuildShell()
    {
        var root = new Grid { RowDefinitions = new RowDefinitions("Auto,Auto,*"), Margin = new Thickness(14), RowSpacing = 10 };
        var nav = new Grid { ColumnDefinitions = new ColumnDefinitions(string.Join(",", tabs.Select(_ => "*"))) };
        for (var i = 0; i < tabs.Length; i++)
        {
            var button = Pill(tabs[i], tabs[i] == "Маршрутизация");
            Grid.SetColumn(button, i);
            nav.Children.Add(button);
        }
        Grid.SetRow(nav, 0);
        root.Children.Add(nav);

        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(Danger("Stop unified"));
        actions.Children.Add(Warn("Restart unified"));
        actions.Children.Add(Text("Avalonia cross-platform shell · premium desktop candidate", "#8DA8C8", 13));
        Grid.SetRow(actions, 1);
        root.Children.Add(actions);

        var body = new Grid { ColumnDefinitions = new ColumnDefinitions("1.15*,1.85*"), ColumnSpacing = 12 };
        body.Children.Add(Card("Selector overview", "AI, Telegram, YouTube, GitHub", "Плитки selector-групп, ping-state и быстрый switch. Это макет shell-архитектуры Avalonia без backend-магии."));
        var right = Card("Маршруты DNS", "Ручной ввод доменов", "example.com\nyoutube.com\napi.service.io\n\nСобрать адреса → normalize + resolve + merge/dedupe");
        Grid.SetColumn(right, 1);
        body.Children.Add(right);
        Grid.SetRow(body, 2);
        root.Children.Add(body);
        return root;
    }

    Button Pill(string text, bool active=false)
    {
        var b = new Button { Content = text, HorizontalAlignment = HorizontalAlignment.Stretch, HorizontalContentAlignment = HorizontalAlignment.Center, Margin = new Thickness(3), Padding = new Thickness(10,7), FontWeight = FontWeight.SemiBold, Foreground = Brushes.White, Background = Brush.Parse(active ? "#2563EB" : "#101B33"), BorderBrush = Brush.Parse(active ? "#67E8F9" : "#24385A"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(9) };
        return b;
    }
    Button Danger(string text) => new() { Content = text, Background = Brush.Parse("#5A1425"), Foreground = Brushes.White, BorderBrush = Brush.Parse("#FB7185"), CornerRadius = new CornerRadius(9), Padding = new Thickness(12,7) };
    Button Warn(string text) => new() { Content = text, Background = Brush.Parse("#7A4614"), Foreground = Brushes.White, BorderBrush = Brush.Parse("#FBBF24"), CornerRadius = new CornerRadius(9), Padding = new Thickness(12,7) };
    TextBlock Text(string text, string color, double size=14) => new() { Text = text, Foreground = Brush.Parse(color), FontSize = size, VerticalAlignment = VerticalAlignment.Center };
    Border Card(string title, string subtitle, string body) => new() { Background = Brush.Parse("#08142A"), BorderBrush = Brush.Parse("#1F4263"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(20), Padding = new Thickness(20), Child = new StackPanel { Spacing = 12, Children = { Text(title, "#F8FBFF", 27), Text(subtitle, "#67E8F9", 17), new TextBlock { Text = body, Foreground = Brush.Parse("#D9E8FF"), TextWrapping = TextWrapping.Wrap, FontSize = 15 } } } };
}
