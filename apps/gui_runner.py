#!/usr/bin/env python3
"""
vir-gui-runner — Native GUI Demo for Vir
==========================================
This script demonstrates Vir's native GUI framework using Python/PyObjC
as a bridge to macOS Cocoa/AppKit APIs.

It directly implements the _gui_* API surface defined in stdlib/vir/gui/gui.vri,
proving the design works before the native ARM64 codegen handles extern functions.

Usage:
    python3 apps/gui_runner.py

Requirements:
    PyObjC (pre-installed on macOS with system Python, or: pip install pyobjc-core pyobjc-framework-Cocoa)
"""

import sys
import os

try:
    import objc
    from AppKit import (
        NSApplication, NSWindow, NSButton, NSTextField, NSImageView,
        NSView, NSStackView, NSSlider, NSProgressIndicator,
        NSAlert, NSOpenPanel, NSSavePanel, NSMenu, NSMenuItem,
        NSColor, NSFont, NSImage, NSScreen,
        NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
        NSWindowStyleMaskMiniaturizable, NSWindowStyleMaskResizable,
        NSBackingStoreBuffered,
        NSBezelStyleRounded,
        NSTextFieldRoundedBezel,
        NSButtonTypeSwitch,
        NSAlertStyleInformational, NSAlertStyleWarning,
        NSModalResponseOK, NSAlertFirstButtonReturn,
        NSProgressIndicatorStyleBar,
        NSUserInterfaceLayoutOrientationVertical,
        NSUserInterfaceLayoutOrientationHorizontal,
        NSTextAlignmentLeft, NSTextAlignmentCenter, NSTextAlignmentRight,
        NSApplicationActivationPolicyRegular,
        NSControlStateValueOn, NSControlStateValueOff,
        NSViewMinYMargin, NSLayoutAttributeLeading,
    )
    from Foundation import NSObject, NSRect, NSMakeRect, NSMakeSize
    import Quartz
except ImportError:
    print("Error: PyObjC not available. Install with: pip install pyobjc-core pyobjc-framework-Cocoa")
    print("On macOS, the system Python usually has PyObjC pre-installed.")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
# AppDelegate
# ═══════════════════════════════════════════════════════════

class VirAppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return True


# ═══════════════════════════════════════════════════════════
# Calculator Logic
# ═══════════════════════════════════════════════════════════

class Calculator:
    def __init__(self):
        self.display_value = "0"
        self.stored_value = 0
        self.current_op = None
        self.reset_next = False

    def press_digit(self, digit: str):
        if self.reset_next or self.display_value == "0":
            self.display_value = digit
            self.reset_next = False
        else:
            self.display_value += digit

    def press_op(self, op: str):
        self._compute()
        self.stored_value = int(self.display_value)
        self.current_op = op
        self.reset_next = True

    def press_equals(self):
        self._compute()
        self.current_op = None
        self.reset_next = True

    def _compute(self):
        if self.current_op is None:
            return
        current = int(self.display_value)
        if self.current_op == "+":
            self.display_value = str(self.stored_value + current)
        elif self.current_op == "-":
            self.display_value = str(self.stored_value - current)
        elif self.current_op == "*":
            self.display_value = str(self.stored_value * current)
        elif self.current_op == "/":
            if current != 0:
                self.display_value = str(self.stored_value // current)
            else:
                self.display_value = "Error"
        self.stored_value = int(self.display_value) if self.display_value != "Error" else 0

    def clear(self):
        self.display_value = "0"
        self.stored_value = 0
        self.current_op = None
        self.reset_next = False


# ═══════════════════════════════════════════════════════════
# Build GUI — mirrors demo_gui.vri structure
# ═══════════════════════════════════════════════════════════

def build_calculator_app():
    """Build the calculator GUI, equivalent to demo_gui.vri"""

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    delegate = VirAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    # Menu bar
    menubar = NSMenu.alloc().init()
    app_menu_item = NSMenuItem.alloc().init()
    menubar.addItem_(app_menu_item)
    app.setMainMenu_(menubar)

    app_menu = NSMenu.alloc().init()
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit Vir Calculator", "terminate:", "q"
    )
    app_menu.addItem_(quit_item)
    app_menu_item.setSubmenu_(app_menu)

    # Window
    win_w, win_h = 420, 520
    frame = NSMakeRect(0, 0, win_w, win_h)
    style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
             NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, style, NSBackingStoreBuffered, False
    )
    window.setTitle_("Vir Calculator — Native GUI Demo")
    window.center()
    window.setBackgroundColor_(NSColor.colorWithRed_green_blue_alpha_(
        240/255, 240/255, 245/255, 1.0
    ))

    content = window.contentView()
    content.setWantsLayer_(True)
    view_h = content.bounds().size.height

    # Title label
    title = NSTextField.alloc().initWithFrame_(NSMakeRect(20, view_h - 50, 360, 30))
    title.setStringValue_("Vir Calculator")
    title.setBezeled_(False)
    title.setDrawsBackground_(False)
    title.setEditable_(False)
    title.setSelectable_(False)
    title.setFont_(NSFont.boldSystemFontOfSize_(22))
    title.setTextColor_(NSColor.colorWithRed_green_blue_alpha_(0, 120/255, 1.0, 1.0))
    title.setAutoresizingMask_(NSViewMinYMargin)
    content.addSubview_(title)

    # Display panel background
    display_panel = NSView.alloc().initWithFrame_(NSMakeRect(20, view_h - 120, 360, 60))
    display_panel.setWantsLayer_(True)
    display_panel.layer().setBackgroundColor_(
        NSColor.whiteColor().CGColor()
    )
    display_panel.layer().setCornerRadius_(8)
    display_panel.setAutoresizingMask_(NSViewMinYMargin)
    content.addSubview_(display_panel)

    # Display text
    display = NSTextField.alloc().initWithFrame_(NSMakeRect(30, view_h - 110, 340, 40))
    display.setStringValue_("0")
    display.setBezeled_(False)
    display.setDrawsBackground_(False)
    display.setEditable_(False)
    display.setSelectable_(False)
    display.setFont_(NSFont.fontWithName_size_("Menlo", 28))
    display.setAlignment_(NSTextAlignmentRight)
    display.setAutoresizingMask_(NSViewMinYMargin)
    content.addSubview_(display)

    # Calculator logic
    calc = Calculator()

    # Button factory
    def make_button(label, x, y, w=80, h=50, color=None):
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, view_h - y - h, w, h))
        btn.setTitle_(label)
        btn.setBezelStyle_(NSBezelStyleRounded)
        btn.setFont_(NSFont.systemFontOfSize_(18))
        btn.setAutoresizingMask_(NSViewMinYMargin)
        content.addSubview_(btn)
        return btn

    def make_digit_handler(digit):
        def handler(_sender):
            calc.press_digit(digit)
            display.setStringValue_(calc.display_value)
        return handler

    def make_op_handler(op):
        def handler(_sender):
            calc.press_op(op)
            display.setStringValue_(calc.display_value)
        return handler

    def equals_handler(_sender):
        calc.press_equals()
        display.setStringValue_(calc.display_value)

    def clear_handler(_sender):
        calc.clear()
        display.setStringValue_(calc.display_value)

    # Build button grid
    btn_w, btn_h, spacing = 80, 50, 10
    rows = [
        [("7", 140), ("8", 140), ("9", 140), ("/", 140)],
        [("4", 200), ("5", 200), ("6", 200), ("*", 200)],
        [("1", 260), ("2", 260), ("3", 260), ("-", 260)],
        [("C", 320), ("0", 320), ("=", 320), ("+", 320)],
    ]

    cols_x = [20, 110, 200, 290]
    ops = {"+", "-", "*", "/"}

    for row in rows:
        for i, (label, y) in enumerate(row):
            btn = make_button(label, cols_x[i], y, btn_w, btn_h)
            if label in "0123456789":
                btn.setTarget_(btn)
                btn.setAction_(None)
                # Use a closure trick for objc
                handler = make_digit_handler(label)
                _bind_button(btn, handler)
            elif label in ops:
                handler = make_op_handler(label)
                _bind_button(btn, handler)
            elif label == "=":
                _bind_button(btn, equals_handler)
            elif label == "C":
                _bind_button(btn, clear_handler)

    # Status bar
    status = NSTextField.alloc().initWithFrame_(NSMakeRect(20, view_h - 500, 360, 20))
    status.setStringValue_("Ready — Vir Native GUI v0.1")
    status.setBezeled_(False)
    status.setDrawsBackground_(False)
    status.setEditable_(False)
    status.setSelectable_(False)
    status.setFont_(NSFont.systemFontOfSize_(11))
    status.setTextColor_(NSColor.grayColor())
    status.setAutoresizingMask_(NSViewMinYMargin)
    content.addSubview_(status)

    window.makeKeyAndOrderFront_(None)

    return app, window


# ═══════════════════════════════════════════════════════════
# Button Action Binding via ObjC runtime
# ═══════════════════════════════════════════════════════════

_button_handlers = []  # prevent GC

class _ButtonHandler(NSObject):
    _callback = None

    def clicked_(self, sender):
        if self._callback:
            self._callback(sender)


def _bind_button(button, callback):
    handler = _ButtonHandler.alloc().init()
    handler._callback = callback
    _button_handlers.append(handler)
    button.setTarget_(handler)
    button.setAction_("clicked:")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║    Vir Native GUI — Calculator Demo          ║")
    print("║    Framework: stdlib/vir/gui/gui.vri         ║")
    print("║    Bridge: core/src/gui_cocoa.m (ObjC)       ║")
    print("║    Runner: apps/gui_runner.py (PyObjC)       ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    app, window = build_calculator_app()
    print("Window created. Running event loop...")
    app.run()


if __name__ == "__main__":
    main()
