/*
 * gui_cocoa.m — macOS AppKit/Cocoa GUI Bridge for Vir
 * =====================================================
 * Provides native GUI primitives via Objective-C runtime.
 * Compiled with: clang -fobjc-arc -framework Cocoa -framework AppKit gui_cocoa.m
 *
 * All functions use the _gui_ prefix and work with opaque widget handles (void*).
 * Strings are passed as (ptr, len) pairs from the Vir runtime.
 */

#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#import <objc/runtime.h>
#include <stdint.h>

// ═══════════════════════════════════════════════════════
// Callback System
// ═══════════════════════════════════════════════════════

// Max callback slots — matches Vir's event model
#define MAX_CALLBACKS 256

typedef void (*VirCallback)(int64_t widget_id, int64_t event_type);
static VirCallback g_callbacks[MAX_CALLBACKS] = {0};
static int g_callback_count = 0;

// Widget ID tracking
static int64_t g_next_widget_id = 1;

// ═══════════════════════════════════════════════════════
// Helper: Convert (ptr, len) → NSString
// ═══════════════════════════════════════════════════════

static NSString* ns_from_vir(const char* ptr, int64_t len) {
    if (!ptr || len <= 0) return @"";
    return [[NSString alloc] initWithBytes:ptr
                                    length:(NSUInteger)len
                                  encoding:NSUTF8StringEncoding] ?: @"";
}

// ═══════════════════════════════════════════════════════
// VirButtonTarget — Objective-C target for button actions
// ═══════════════════════════════════════════════════════

@interface VirButtonTarget : NSObject
@property (assign) int64_t callback_id;
@property (assign) int64_t widget_id;
- (void)buttonClicked:(id)sender;
@end

@implementation VirButtonTarget
- (void)buttonClicked:(id)sender {
    if (self.callback_id >= 0 && self.callback_id < MAX_CALLBACKS) {
        if (g_callbacks[self.callback_id]) {
            g_callbacks[self.callback_id](self.widget_id, 1); // EventType::Click = 1
        }
    }
}
@end

// ═══════════════════════════════════════════════════════
// VirAppDelegate
// ═══════════════════════════════════════════════════════

@interface VirAppDelegate : NSObject <NSApplicationDelegate>
@property (strong) NSString* appName;
@end

@implementation VirAppDelegate
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp activateIgnoringOtherApps:YES];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}
@end

// Store references to prevent ARC from releasing
static NSMutableArray* g_retained_objects = nil;

static void ensure_retained_array(void) {
    if (!g_retained_objects) {
        g_retained_objects = [NSMutableArray array];
    }
}

// ═══════════════════════════════════════════════════════
// App Lifecycle
// ═══════════════════════════════════════════════════════

int64_t _gui_app_create(const char* name_ptr, int64_t name_len) {
    ensure_retained_array();

    [NSApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];

    VirAppDelegate* delegate = [[VirAppDelegate alloc] init];
    delegate.appName = ns_from_vir(name_ptr, name_len);
    [NSApp setDelegate:delegate];
    [g_retained_objects addObject:delegate];

    // Create default menu bar
    NSMenu* menubar = [[NSMenu alloc] init];
    NSMenuItem* appMenuItem = [[NSMenuItem alloc] init];
    [menubar addItem:appMenuItem];
    [NSApp setMainMenu:menubar];

    NSMenu* appMenu = [[NSMenu alloc] init];
    NSString* quitTitle = [NSString stringWithFormat:@"Quit %@", delegate.appName];
    NSMenuItem* quitItem = [[NSMenuItem alloc] initWithTitle:quitTitle
                                                      action:@selector(terminate:)
                                               keyEquivalent:@"q"];
    [appMenu addItem:quitItem];
    [appMenuItem setSubmenu:appMenu];

    return (int64_t)(__bridge void*)NSApp;
}

int64_t _gui_app_run(int64_t app) {
    (void)app;
    [NSApp run];
    return 0;
}

int64_t _gui_app_quit(int64_t app) {
    (void)app;
    [NSApp terminate:nil];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Window
// ═══════════════════════════════════════════════════════

int64_t _gui_window_create(int64_t app, const char* title_ptr, int64_t title_len,
                            int64_t w, int64_t h) {
    (void)app;
    ensure_retained_array();

    NSRect frame = NSMakeRect(0, 0, (CGFloat)w, (CGFloat)h);
    NSUInteger style = NSWindowStyleMaskTitled |
                       NSWindowStyleMaskClosable |
                       NSWindowStyleMaskMiniaturizable |
                       NSWindowStyleMaskResizable;

    NSWindow* window = [[NSWindow alloc] initWithContentRect:frame
                                                   styleMask:style
                                                     backing:NSBackingStoreBuffered
                                                       defer:NO];

    [window setTitle:ns_from_vir(title_ptr, title_len)];
    [window center];

    // Enable layer-backed views for custom drawing
    [[window contentView] setWantsLayer:YES];

    [window makeKeyAndOrderFront:nil];
    [g_retained_objects addObject:window];

    return (int64_t)(__bridge void*)window;
}

int64_t _gui_window_show(int64_t win) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    [window makeKeyAndOrderFront:nil];
    return 0;
}

int64_t _gui_window_hide(int64_t win) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    [window orderOut:nil];
    return 0;
}

int64_t _gui_window_close(int64_t win) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    [window close];
    return 0;
}

int64_t _gui_window_set_title(int64_t win, const char* title_ptr, int64_t title_len) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    [window setTitle:ns_from_vir(title_ptr, title_len)];
    return 0;
}

int64_t _gui_window_set_size(int64_t win, int64_t w, int64_t h) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    NSRect frame = [window frame];
    frame.size = NSMakeSize((CGFloat)w, (CGFloat)h);
    [window setFrame:frame display:YES animate:YES];
    return 0;
}

int64_t _gui_window_center(int64_t win) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    [window center];
    return 0;
}

int64_t _gui_window_set_bg(int64_t win, int64_t r, int64_t g, int64_t b, int64_t a) {
    NSWindow* window = (__bridge NSWindow*)(void*)win;
    NSColor* color = [NSColor colorWithRed:r/255.0 green:g/255.0 blue:b/255.0 alpha:a/255.0];
    [window setBackgroundColor:color];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Button
// ═══════════════════════════════════════════════════════

int64_t _gui_button_create(int64_t parent, const char* label_ptr, int64_t label_len,
                            int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSButton* button = [[NSButton alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [button setTitle:ns_from_vir(label_ptr, label_len)];
    [button setBezelStyle:NSBezelStyleRounded];
    [button setAutoresizingMask:NSViewMinYMargin];

    VirButtonTarget* target = [[VirButtonTarget alloc] init];
    target.widget_id = g_next_widget_id++;
    target.callback_id = -1;
    [button setTarget:target];
    [button setAction:@selector(buttonClicked:)];

    [contentView addSubview:button];
    [g_retained_objects addObject:button];
    [g_retained_objects addObject:target];

    // Store target reference on button using associated objects
    objc_setAssociatedObject(button, "vir_target", target, OBJC_ASSOCIATION_RETAIN);

    return (int64_t)(__bridge void*)button;
}

int64_t _gui_button_set_label(int64_t btn, const char* label_ptr, int64_t label_len) {
    NSButton* button = (__bridge NSButton*)(void*)btn;
    [button setTitle:ns_from_vir(label_ptr, label_len)];
    return 0;
}

int64_t _gui_button_set_action(int64_t btn, int64_t callback_id) {
    NSButton* button = (__bridge NSButton*)(void*)btn;
    VirButtonTarget* target = objc_getAssociatedObject(button, "vir_target");
    if (target) {
        target.callback_id = callback_id;
    }
    return 0;
}

// ═══════════════════════════════════════════════════════
// Label
// ═══════════════════════════════════════════════════════

int64_t _gui_label_create(int64_t parent, const char* text_ptr, int64_t text_len,
                           int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSTextField* label = [[NSTextField alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [label setStringValue:ns_from_vir(text_ptr, text_len)];
    [label setBezeled:NO];
    [label setDrawsBackground:NO];
    [label setEditable:NO];
    [label setSelectable:NO];
    [label setAutoresizingMask:NSViewMinYMargin];
    [label setFont:[NSFont systemFontOfSize:14]];

    [contentView addSubview:label];
    [g_retained_objects addObject:label];

    return (int64_t)(__bridge void*)label;
}

int64_t _gui_label_set_text(int64_t lbl, const char* text_ptr, int64_t text_len) {
    NSTextField* label = (__bridge NSTextField*)(void*)lbl;
    [label setStringValue:ns_from_vir(text_ptr, text_len)];
    return 0;
}

int64_t _gui_label_set_font(int64_t lbl, const char* name_ptr, int64_t name_len, int64_t size) {
    NSTextField* label = (__bridge NSTextField*)(void*)lbl;
    NSString* fontName = ns_from_vir(name_ptr, name_len);
    NSFont* font = nil;
    if ([fontName length] > 0) {
        font = [NSFont fontWithName:fontName size:(CGFloat)size];
    }
    if (!font) {
        font = [NSFont systemFontOfSize:(CGFloat)size];
    }
    [label setFont:font];
    return 0;
}

int64_t _gui_label_set_color(int64_t lbl, int64_t r, int64_t g, int64_t b, int64_t a) {
    NSTextField* label = (__bridge NSTextField*)(void*)lbl;
    NSColor* color = [NSColor colorWithRed:r/255.0 green:g/255.0 blue:b/255.0 alpha:a/255.0];
    [label setTextColor:color];
    return 0;
}

int64_t _gui_label_set_align(int64_t lbl, int64_t align) {
    NSTextField* label = (__bridge NSTextField*)(void*)lbl;
    NSTextAlignment alignment;
    switch (align) {
        case 0: alignment = NSTextAlignmentLeft; break;
        case 1: alignment = NSTextAlignmentCenter; break;
        case 2: alignment = NSTextAlignmentRight; break;
        default: alignment = NSTextAlignmentLeft; break;
    }
    [label setAlignment:alignment];
    return 0;
}

// ═══════════════════════════════════════════════════════
// TextField (editable)
// ═══════════════════════════════════════════════════════

int64_t _gui_textfield_create(int64_t parent, const char* ph_ptr, int64_t ph_len,
                               int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSTextField* tf = [[NSTextField alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [tf setPlaceholderString:ns_from_vir(ph_ptr, ph_len)];
    [tf setBezeled:YES];
    [tf setBezelStyle:NSTextFieldRoundedBezel];
    [tf setEditable:YES];
    [tf setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:tf];
    [g_retained_objects addObject:tf];

    return (int64_t)(__bridge void*)tf;
}

int64_t _gui_textfield_get_text(int64_t tf, char* buf, int64_t buf_len) {
    NSTextField* field = (__bridge NSTextField*)(void*)tf;
    NSString* text = [field stringValue];
    const char* utf8 = [text UTF8String];
    NSUInteger len = [text lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
    if ((int64_t)len > buf_len - 1) len = (NSUInteger)(buf_len - 1);
    memcpy(buf, utf8, len);
    buf[len] = '\0';
    return (int64_t)len;
}

int64_t _gui_textfield_set_text(int64_t tf, const char* text_ptr, int64_t text_len) {
    NSTextField* field = (__bridge NSTextField*)(void*)tf;
    [field setStringValue:ns_from_vir(text_ptr, text_len)];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Image View
// ═══════════════════════════════════════════════════════

int64_t _gui_image_create(int64_t parent, const char* path_ptr, int64_t path_len,
                           int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSImageView* iv = [[NSImageView alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    NSString* path = ns_from_vir(path_ptr, path_len);
    NSImage* image = [[NSImage alloc] initWithContentsOfFile:path];
    if (image) {
        [iv setImage:image];
    }
    [iv setImageScaling:NSImageScaleProportionallyUpOrDown];
    [iv setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:iv];
    [g_retained_objects addObject:iv];

    return (int64_t)(__bridge void*)iv;
}

// ═══════════════════════════════════════════════════════
// Panel (container view)
// ═══════════════════════════════════════════════════════

int64_t _gui_panel_create(int64_t parent, int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSView* panel = [[NSView alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [panel setWantsLayer:YES];
    [panel setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:panel];
    [g_retained_objects addObject:panel];

    return (int64_t)(__bridge void*)panel;
}

int64_t _gui_panel_set_bg(int64_t panel, int64_t r, int64_t g, int64_t b, int64_t a) {
    NSView* view = (__bridge NSView*)(void*)panel;
    [view setWantsLayer:YES];
    view.layer.backgroundColor = [NSColor colorWithRed:r/255.0 green:g/255.0 blue:b/255.0 alpha:a/255.0].CGColor;
    return 0;
}

// ═══════════════════════════════════════════════════════
// Stack Layout
// ═══════════════════════════════════════════════════════

int64_t _gui_stack_create(int64_t parent, int64_t vertical,
                           int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSStackView* stack = [[NSStackView alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [stack setOrientation:vertical ? NSUserInterfaceLayoutOrientationVertical
                                   : NSUserInterfaceLayoutOrientationHorizontal];
    [stack setSpacing:8];
    [stack setAlignment:NSLayoutAttributeLeading];
    [stack setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:stack];
    [g_retained_objects addObject:stack];

    return (int64_t)(__bridge void*)stack;
}

int64_t _gui_stack_add(int64_t stack, int64_t child) {
    NSStackView* s = (__bridge NSStackView*)(void*)stack;
    NSView* v = (__bridge NSView*)(void*)child;
    [s addArrangedSubview:v];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Slider
// ═══════════════════════════════════════════════════════

int64_t _gui_slider_create(int64_t parent, int64_t min_val, int64_t max_val,
                            int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSSlider* slider = [[NSSlider alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [slider setMinValue:(double)min_val];
    [slider setMaxValue:(double)max_val];
    [slider setDoubleValue:(double)min_val];
    [slider setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:slider];
    [g_retained_objects addObject:slider];

    return (int64_t)(__bridge void*)slider;
}

int64_t _gui_slider_get_value(int64_t slider) {
    NSSlider* s = (__bridge NSSlider*)(void*)slider;
    return (int64_t)[s doubleValue];
}

int64_t _gui_slider_set_value(int64_t slider, int64_t val) {
    NSSlider* s = (__bridge NSSlider*)(void*)slider;
    [s setDoubleValue:(double)val];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Checkbox
// ═══════════════════════════════════════════════════════

int64_t _gui_checkbox_create(int64_t parent, const char* label_ptr, int64_t label_len,
                              int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSButton* cb = [[NSButton alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [cb setButtonType:NSButtonTypeSwitch];
    [cb setTitle:ns_from_vir(label_ptr, label_len)];
    [cb setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:cb];
    [g_retained_objects addObject:cb];

    return (int64_t)(__bridge void*)cb;
}

int64_t _gui_checkbox_is_checked(int64_t cb) {
    NSButton* button = (__bridge NSButton*)(void*)cb;
    return [button state] == NSControlStateValueOn ? 1 : 0;
}

int64_t _gui_checkbox_set_checked(int64_t cb, int64_t val) {
    NSButton* button = (__bridge NSButton*)(void*)cb;
    [button setState:val ? NSControlStateValueOn : NSControlStateValueOff];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Progress Bar
// ═══════════════════════════════════════════════════════

int64_t _gui_progress_create(int64_t parent, int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSProgressIndicator* prog = [[NSProgressIndicator alloc]
                                  initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [prog setStyle:NSProgressIndicatorStyleBar];
    [prog setIndeterminate:NO];
    [prog setMinValue:0];
    [prog setMaxValue:100];
    [prog setDoubleValue:0];
    [prog setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:prog];
    [g_retained_objects addObject:prog];

    return (int64_t)(__bridge void*)prog;
}

int64_t _gui_progress_set_value(int64_t prog, int64_t val) {
    NSProgressIndicator* p = (__bridge NSProgressIndicator*)(void*)prog;
    [p setDoubleValue:(double)val];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Canvas (Custom Drawing via NSBezierPath)
// ═══════════════════════════════════════════════════════

// Simple canvas using layer drawing
int64_t _gui_canvas_create(int64_t parent, int64_t x, int64_t y, int64_t w, int64_t h) {
    ensure_retained_array();
    NSWindow* window = (__bridge NSWindow*)(void*)parent;
    NSView* contentView = [window contentView];
    CGFloat viewH = [contentView bounds].size.height;

    NSView* canvas = [[NSView alloc] initWithFrame:NSMakeRect(x, viewH - y - h, w, h)];
    [canvas setWantsLayer:YES];
    canvas.layer.backgroundColor = [NSColor whiteColor].CGColor;
    [canvas setAutoresizingMask:NSViewMinYMargin];

    [contentView addSubview:canvas];
    [g_retained_objects addObject:canvas];

    return (int64_t)(__bridge void*)canvas;
}

int64_t _gui_canvas_draw_rect(int64_t canvas, int64_t x, int64_t y, int64_t w, int64_t h,
                               int64_t r, int64_t g, int64_t b, int64_t a) {
    NSView* view = (__bridge NSView*)(void*)canvas;
    CALayer* rect = [CALayer layer];
    rect.frame = CGRectMake(x, [view bounds].size.height - y - h, w, h);
    rect.backgroundColor = [NSColor colorWithRed:r/255.0 green:g/255.0 blue:b/255.0 alpha:a/255.0].CGColor;
    [view.layer addSublayer:rect];
    return 0;
}

int64_t _gui_canvas_draw_line(int64_t canvas, int64_t x1, int64_t y1,
                               int64_t x2, int64_t y2,
                               int64_t r, int64_t g, int64_t b) {
    NSView* view = (__bridge NSView*)(void*)canvas;
    CGFloat viewH = [view bounds].size.height;
    CAShapeLayer* line = [CAShapeLayer layer];
    CGMutablePathRef path = CGPathCreateMutable();
    CGPathMoveToPoint(path, NULL, x1, viewH - y1);
    CGPathAddLineToPoint(path, NULL, x2, viewH - y2);
    line.path = path;
    line.strokeColor = [NSColor colorWithRed:r/255.0 green:g/255.0 blue:b/255.0 alpha:1.0].CGColor;
    line.lineWidth = 2.0;
    [view.layer addSublayer:line];
    CGPathRelease(path);
    return 0;
}

int64_t _gui_canvas_draw_circle(int64_t canvas, int64_t cx, int64_t cy, int64_t radius,
                                 int64_t r, int64_t g, int64_t b) {
    NSView* view = (__bridge NSView*)(void*)canvas;
    CGFloat viewH = [view bounds].size.height;
    CAShapeLayer* circle = [CAShapeLayer layer];
    CGMutablePathRef path = CGPathCreateMutable();
    CGPathAddArc(path, NULL, cx, viewH - cy, radius, 0, 2 * M_PI, NO);
    circle.path = path;
    circle.fillColor = [NSColor colorWithRed:r/255.0 green:g/255.0 blue:b/255.0 alpha:1.0].CGColor;
    [view.layer addSublayer:circle];
    CGPathRelease(path);
    return 0;
}

int64_t _gui_canvas_draw_text(int64_t canvas, const char* text_ptr, int64_t text_len,
                               int64_t x, int64_t y, int64_t size) {
    NSView* view = (__bridge NSView*)(void*)canvas;
    CGFloat viewH = [view bounds].size.height;
    CATextLayer* textLayer = [CATextLayer layer];
    textLayer.string = ns_from_vir(text_ptr, text_len);
    textLayer.fontSize = (CGFloat)size;
    textLayer.foregroundColor = [NSColor blackColor].CGColor;
    textLayer.frame = CGRectMake(x, viewH - y - size - 4, 500, size + 8);
    textLayer.contentsScale = [[NSScreen mainScreen] backingScaleFactor];
    [view.layer addSublayer:textLayer];
    return 0;
}

int64_t _gui_canvas_clear(int64_t canvas) {
    NSView* view = (__bridge NSView*)(void*)canvas;
    NSArray* sublayers = [view.layer.sublayers copy];
    for (CALayer* layer in sublayers) {
        [layer removeFromSuperlayer];
    }
    return 0;
}

int64_t _gui_canvas_flush(int64_t canvas) {
    NSView* view = (__bridge NSView*)(void*)canvas;
    [view setNeedsDisplay:YES];
    return 0;
}

// ═══════════════════════════════════════════════════════
// Event Handling
// ═══════════════════════════════════════════════════════

int64_t _gui_set_callback(int64_t widget, int64_t event_type, int64_t callback_id) {
    // For buttons, set action callback
    if (event_type == 1) { // Click
        NSView* view = (__bridge NSView*)(void*)widget;
        if ([view isKindOfClass:[NSButton class]]) {
            VirButtonTarget* target = objc_getAssociatedObject(view, "vir_target");
            if (target) {
                target.callback_id = callback_id;
            }
        }
    }
    return 0;
}

int64_t _gui_poll_event(void* event_out) {
    // Non-blocking event poll — returns 0 if no event
    NSEvent* event = [NSApp nextEventMatchingMask:NSEventMaskAny
                                        untilDate:nil
                                           inMode:NSDefaultRunLoopMode
                                          dequeue:YES];
    if (event) {
        [NSApp sendEvent:event];
        return 1;
    }
    return 0;
}

// ═══════════════════════════════════════════════════════
// Dialog Boxes
// ═══════════════════════════════════════════════════════

int64_t _gui_alert(const char* title_ptr, int64_t title_len,
                    const char* msg_ptr, int64_t msg_len) {
    NSAlert* alert = [[NSAlert alloc] init];
    [alert setMessageText:ns_from_vir(title_ptr, title_len)];
    [alert setInformativeText:ns_from_vir(msg_ptr, msg_len)];
    [alert setAlertStyle:NSAlertStyleInformational];
    [alert addButtonWithTitle:@"OK"];
    [alert runModal];
    return 0;
}

int64_t _gui_confirm(const char* title_ptr, int64_t title_len,
                      const char* msg_ptr, int64_t msg_len) {
    NSAlert* alert = [[NSAlert alloc] init];
    [alert setMessageText:ns_from_vir(title_ptr, title_len)];
    [alert setInformativeText:ns_from_vir(msg_ptr, msg_len)];
    [alert setAlertStyle:NSAlertStyleWarning];
    [alert addButtonWithTitle:@"OK"];
    [alert addButtonWithTitle:@"Cancel"];
    NSModalResponse resp = [alert runModal];
    return resp == NSAlertFirstButtonReturn ? 1 : 0;
}

int64_t _gui_file_open(char* buf, int64_t buf_len) {
    NSOpenPanel* panel = [NSOpenPanel openPanel];
    [panel setCanChooseFiles:YES];
    [panel setCanChooseDirectories:NO];
    [panel setAllowsMultipleSelection:NO];

    if ([panel runModal] == NSModalResponseOK) {
        NSString* path = [[panel URL] path];
        const char* utf8 = [path UTF8String];
        NSUInteger len = [path lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
        if ((int64_t)len > buf_len - 1) len = (NSUInteger)(buf_len - 1);
        memcpy(buf, utf8, len);
        buf[len] = '\0';
        return (int64_t)len;
    }
    return 0;
}

int64_t _gui_file_save(char* buf, int64_t buf_len) {
    NSSavePanel* panel = [NSSavePanel savePanel];

    if ([panel runModal] == NSModalResponseOK) {
        NSString* path = [[panel URL] path];
        const char* utf8 = [path UTF8String];
        NSUInteger len = [path lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
        if ((int64_t)len > buf_len - 1) len = (NSUInteger)(buf_len - 1);
        memcpy(buf, utf8, len);
        buf[len] = '\0';
        return (int64_t)len;
    }
    return 0;
}
