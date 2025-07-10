//
//  MainWindow.m
//  FLVParserGUI
//
//  Created by 王贵彬 on 2025/7/10.
//

#import "MainWindow.h"

@implementation MainWindow
- (instancetype)init {
    self = [super initWithContentRect:NSMakeRect(0, 0, 1000, 700)
                            styleMask:(NSWindowStyleMaskTitled |
                                      NSWindowStyleMaskClosable |
                                      NSWindowStyleMaskMiniaturizable 
                                      )
                              backing:NSBackingStoreBuffered
                                defer:NO];
    if (self) {
        self.title = @"FLV File Parser";
        self.minSize = NSMakeSize(1000, 700);
        self.maxSize = NSMakeSize(1000, 700);
        [self center];
        
        // 启用标题栏透明效果（适配暗黑模式）
        if (@available(macOS 10.14, *)) {
            self.titlebarAppearsTransparent = YES;
            self.backgroundColor = [NSColor windowBackgroundColor];
        }
    }
    return self;
}

- (void)awakeFromNib {
    [super awakeFromNib];
    [self updateWindowAppearance];
}

- (void)viewDidChangeEffectiveAppearance {
    [self updateWindowAppearance];
}

- (void)updateWindowAppearance {
    if (@available(macOS 10.14, *)) {
        if ([self.effectiveAppearance.name containsString:@"Dark"]) {
            self.backgroundColor = [NSColor colorWithCalibratedWhite:0.12 alpha:1.0];
        } else {
            self.backgroundColor = [NSColor colorWithCalibratedWhite:0.98 alpha:1.0];
        }
    }
}

@end
