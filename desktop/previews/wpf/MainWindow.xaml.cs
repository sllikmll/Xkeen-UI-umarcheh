using System;
using System.Linq;
using System.Windows;
namespace UnifiedUiWpfPreview;
public partial class MainWindow : Window
{
    public MainWindow() { InitializeComponent(); }
    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Contains("--smoke")) { Console.WriteLine("{\"ok\":true,\"app\":\"Unified UI WPF Preview\",\"version\":\"0.1.0\",\"ui\":\"WPF\"}"); return 0; }
        var app = new Application(); app.Run(new MainWindow()); return 0;
    }
}
