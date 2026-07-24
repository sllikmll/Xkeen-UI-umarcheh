#import <Cocoa/Cocoa.h>

@interface AppDelegate : NSObject <NSApplicationDelegate>
@end

static NSButton* Button(NSString* title, BOOL active) {
    NSButton* b = [NSButton buttonWithTitle:title target:nil action:nil];
    b.bezelStyle = NSBezelStyleRegularSquare;
    b.wantsLayer = YES;
    b.layer.cornerRadius = 8;
    b.layer.backgroundColor = active ? [NSColor colorWithCalibratedRed:0.14 green:0.39 blue:0.92 alpha:1].CGColor : [NSColor colorWithCalibratedRed:0.06 green:0.11 blue:0.20 alpha:1].CGColor;
    b.contentTintColor = NSColor.whiteColor;
    return b;
}
static NSTextField* Label(NSString* text, CGFloat size, NSColor* color) {
    NSTextField* l = [NSTextField labelWithString:text];
    l.font = [NSFont systemFontOfSize:size weight:NSFontWeightBold];
    l.textColor = color;
    return l;
}

@implementation AppDelegate
- (void)applicationDidFinishLaunching:(NSNotification*)n {
    NSWindow* win = [[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,1240,760) styleMask:(NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskResizable|NSWindowStyleMaskMiniaturizable) backing:NSBackingStoreBuffered defer:NO];
    win.title = @"Unified UI — C++ Native Preview";
    win.backgroundColor = [NSColor colorWithCalibratedRed:0.02 green:0.04 blue:0.10 alpha:1];
    [win center];
    NSView* root = win.contentView; root.wantsLayer = YES; root.layer.backgroundColor = win.backgroundColor.CGColor;
    NSArray* tabs = @[@"Маршрутизация",@"Mihomo",@"Соединения",@"WireGuard",@"VLESS",@"Маршруты DNS",@"Логи"];
    CGFloat x=14, y=710, w=(1240-28-6*6)/7.0;
    for(NSUInteger i=0;i<tabs.count;i++){ NSButton* b=Button(tabs[i], i==0); b.frame=NSMakeRect(x+i*(w+6), y, w, 30); [root addSubview:b]; }
    NSButton* stop=Button(@"Stop unified", NO); stop.layer.backgroundColor=[NSColor colorWithCalibratedRed:0.35 green:0.08 blue:0.15 alpha:1].CGColor; stop.frame=NSMakeRect(14,665,120,32); [root addSubview:stop];
    NSButton* restart=Button(@"Restart unified", NO); restart.layer.backgroundColor=[NSColor colorWithCalibratedRed:0.48 green:0.27 blue:0.08 alpha:1].CGColor; restart.frame=NSMakeRect(144,665,140,32); [root addSubview:restart];
    [root addSubview:({ NSTextField* t=Label(@"Objective-C++/Cocoa native shell · fastest path candidate",13,[NSColor colorWithCalibratedRed:0.55 green:0.66 blue:0.78 alpha:1]); t.frame=NSMakeRect(304,672,520,20); t; })];
    NSBox* left=[[NSBox alloc] initWithFrame:NSMakeRect(14,24,430,620)]; left.boxType=NSBoxCustom; left.fillColor=[NSColor colorWithCalibratedRed:0.03 green:0.08 blue:0.16 alpha:1]; left.borderColor=[NSColor colorWithCalibratedRed:0.12 green:0.26 blue:0.39 alpha:1]; left.cornerRadius=20; [root addSubview:left];
    [root addSubview:({ NSTextField* t=Label(@"Selector overview",28,NSColor.whiteColor); t.frame=NSMakeRect(38,590,360,40); t; })];
    [root addSubview:({ NSTextField* t=Label(@"AI, Telegram, YouTube, GitHub",17,[NSColor colorWithCalibratedRed:0.40 green:0.91 blue:0.98 alpha:1]); t.frame=NSMakeRect(38,552,360,24); t; })];
    [root addSubview:({ NSTextField* t=Label(@"C++ native — самый быстрый, но самый дорогой путь: больше ручной работы, меньше runtime-маги.",15,[NSColor colorWithCalibratedRed:0.85 green:0.91 blue:1 alpha:1]); t.frame=NSMakeRect(38,500,360,50); t.lineBreakMode=NSLineBreakByWordWrapping; t; })];
    NSBox* right=[[NSBox alloc] initWithFrame:NSMakeRect(462,24,764,620)]; right.boxType=NSBoxCustom; right.fillColor=left.fillColor; right.borderColor=left.borderColor; right.cornerRadius=20; [root addSubview:right];
    [root addSubview:({ NSTextField* t=Label(@"Маршруты DNS",28,NSColor.whiteColor); t.frame=NSMakeRect(486,590,360,40); t; })];
    [root addSubview:({ NSTextField* t=Label(@"Ручной ввод доменов",17,[NSColor colorWithCalibratedRed:0.40 green:0.91 blue:0.98 alpha:1]); t.frame=NSMakeRect(486,552,360,24); t; })];
    NSTextView* tv=[[NSTextView alloc] initWithFrame:NSMakeRect(486,360,700,170)]; tv.string=@"example.com\nyoutube.com\napi.service.io"; tv.backgroundColor=[NSColor colorWithCalibratedRed:0.03 green:0.09 blue:0.15 alpha:1]; tv.textColor=NSColor.whiteColor; [root addSubview:tv];
    NSButton* gen=Button(@"Собрать адреса", NO); gen.frame=NSMakeRect(486,314,700,34); [root addSubview:gen];
    [win makeKeyAndOrderFront:nil];
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication*)sender { return YES; }
@end

int main(int argc, const char * argv[]) {
    for(int i=1;i<argc;i++){ if(strcmp(argv[i], "--smoke")==0){ printf("{\"ok\":true,\"app\":\"Unified UI C++ Native Preview\",\"version\":\"0.1.0\",\"ui\":\"Cocoa/C++\"}\n"); return 0; } }
    @autoreleasepool { NSApplication* app = [NSApplication sharedApplication]; AppDelegate* delegate=[AppDelegate new]; app.delegate=delegate; [app run]; }
    return 0;
}
