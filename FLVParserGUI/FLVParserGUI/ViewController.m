//
//  ViewController.m
//  FLVParserGUI
//
//  Created by 王贵彬 on 2025/7/10.
//

#import "ViewController.h"
#import "FLVParserService.h"


#pragma mark - Dark Mode Helpers

@interface NSColor (DarkMode)
+ (NSColor *)adaptiveBackgroundColor;
+ (NSColor *)adaptiveTextColor;
+ (NSColor *)adaptiveSecondaryTextColor;
+ (NSColor *)adaptiveTableHeaderColor;
+ (NSColor *)adaptiveTableRowColor;
+ (NSColor *)adaptiveTableAlternateRowColor;
+ (NSColor *)adaptiveBorderColor;
+ (NSColor *)adaptiveButtonColor;
@end

@implementation NSColor (DarkMode)

+ (NSColor *)adaptiveBackgroundColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor controlBackgroundColor];
    } else {
        return [NSColor colorWithCalibratedWhite:0.95 alpha:1.0];
    }
}

+ (NSColor *)adaptiveTextColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor textColor];
    } else {
        return [NSColor blackColor];
    }
}

+ (NSColor *)adaptiveSecondaryTextColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor secondaryLabelColor];
    } else {
        return [NSColor grayColor];
    }
}

+ (NSColor *)adaptiveTableHeaderColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor gridColor];
    } else {
        return [NSColor colorWithCalibratedWhite:0.85 alpha:1.0];
    }
}

+ (NSColor *)adaptiveTableRowColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor controlBackgroundColor];
    } else {
        return [NSColor whiteColor];
    }
}

+ (NSColor *)adaptiveTableAlternateRowColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor windowBackgroundColor];
    } else {
        return [NSColor colorWithCalibratedWhite:0.97 alpha:1.0];
    }
}

+ (NSColor *)adaptiveBorderColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor separatorColor];
    } else {
        return [NSColor colorWithCalibratedWhite:0.7 alpha:1.0];
    }
}

+ (NSColor *)adaptiveButtonColor {
    if (@available(macOS 10.14, *)) {
        return [NSColor controlColor];
    } else {
        return [NSColor colorWithCalibratedWhite:0.85 alpha:1.0];
    }
}

@end


#pragma mark - Adaptive TextView

@interface AdaptiveTextView : NSTextView
@end

@implementation AdaptiveTextView

- (void)viewDidChangeEffectiveAppearance {
    [super viewDidChangeEffectiveAppearance];
    [self updateColorsForCurrentAppearance];
}

- (void)awakeFromNib {
    [super awakeFromNib];
    [self updateColorsForCurrentAppearance];
}

- (void)updateColorsForCurrentAppearance {
    NSAppearance *appearance = self.effectiveAppearance ?: [NSApp effectiveAppearance];
    
    if (@available(macOS 10.14, *)) {
        BOOL isDark = [appearance.name containsString:@"Dark"];
        
        self.backgroundColor = isDark ? [NSColor colorWithCalibratedWhite:0.12 alpha:1.0] :
                                      [NSColor colorWithCalibratedWhite:0.98 alpha:1.0];
        
        self.textColor = isDark ? [NSColor colorWithCalibratedWhite:0.9 alpha:1.0] :
                                 [NSColor colorWithCalibratedWhite:0.1 alpha:1.0];
    } else {
        self.backgroundColor = [NSColor colorWithCalibratedWhite:0.98 alpha:1.0];
        self.textColor = [NSColor blackColor];
    }
    
    [self setNeedsDisplay:YES];
}

@end

#pragma mark - Adaptive Table View

@interface AdaptiveTableView : NSTableView
@end

@implementation AdaptiveTableView

- (void)viewDidChangeEffectiveAppearance {
    [super viewDidChangeEffectiveAppearance];
    [self updateColorsForCurrentAppearance];
    [self reloadData];
}

- (void)awakeFromNib {
    [super awakeFromNib];
    [self updateColorsForCurrentAppearance];
}

- (void)updateColorsForCurrentAppearance {
    if (@available(macOS 10.14, *)) {
        self.backgroundColor = [NSColor controlBackgroundColor];
        self.gridColor = [NSColor gridColor];
    } else {
        self.backgroundColor = [NSColor whiteColor];
        self.gridColor = [NSColor colorWithCalibratedWhite:0.85 alpha:1.0];
    }
    [self setNeedsDisplay:YES];
}

@end




@interface ViewController ()<NSTableViewDataSource, NSTableViewDelegate>

@property (strong) NSString *logContent;
@property (strong) NSArray<NSString *> *logLines;
@property (strong) NSMutableArray<NSDictionary *> *parsedTags;

// UI Elements
@property (strong) NSScrollView *logScrollView;
@property (strong) AdaptiveTextView *logTextView;
@property (strong) AdaptiveTableView *tableView;
@property (strong) NSButton *openButton;
@property (strong) NSButton *myCopyButton;
@property (strong) NSButton *exportButton;
@property (strong) NSProgressIndicator *progressIndicator;

@end


@implementation ViewController

- (void)loadView {
    self.view = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 1000, 700)];
    self.view.wantsLayer = YES;
    self.view.layer.backgroundColor = [NSColor adaptiveBackgroundColor].CGColor;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    
    // 监听外观变化
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(updateAppearance)
                                                 name:NSControlTintDidChangeNotification
                                               object:nil];
    
    // 创建控件
    [self createControls];
    [self layoutControls];
    
    // 初始外观更新
    [self updateAppearance];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)updateAppearance {
    // 更新视图背景
    self.view.layer.backgroundColor = [NSColor adaptiveBackgroundColor].CGColor;
    
    // 更新表格外观
    [self.tableView updateColorsForCurrentAppearance];
    
    // 更新文本视图外观
    [self.logTextView updateColorsForCurrentAppearance];
    
    // 更新按钮颜色
    self.openButton.bezelColor = [NSColor adaptiveButtonColor];
    self.myCopyButton.bezelColor = [NSColor adaptiveButtonColor];
    self.exportButton.bezelColor = [NSColor adaptiveButtonColor];
}

- (void)createControls {
    // 表格视图 (用于显示解析结果)
    self.tableView = [[AdaptiveTableView alloc] init];
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    self.tableView.rowHeight = 22;
    self.tableView.gridStyleMask = NSTableViewSolidHorizontalGridLineMask;
    
    // 表格列
    NSTableColumn *typeColumn = [[NSTableColumn alloc] initWithIdentifier:@"Type"];
    typeColumn.title = @"Type";
    typeColumn.width = 80;
    [self.tableView addTableColumn:typeColumn];
    
    NSTableColumn *sizeColumn = [[NSTableColumn alloc] initWithIdentifier:@"Size"];
    sizeColumn.title = @"Size (bytes)";
    sizeColumn.width = 120;
    [self.tableView addTableColumn:sizeColumn];
    
    NSTableColumn *timestampColumn = [[NSTableColumn alloc] initWithIdentifier:@"Timestamp"];
    timestampColumn.title = @"Timestamp";
    timestampColumn.width = 100;
    [self.tableView addTableColumn:timestampColumn];
    
    NSTableColumn *detailsColumn = [[NSTableColumn alloc] initWithIdentifier:@"Details"];
    detailsColumn.title = @"Details";
    detailsColumn.width = 400;
    [self.tableView addTableColumn:detailsColumn];
    
    // 表格滚动视图
    NSScrollView *tableScrollView = [[NSScrollView alloc] init];
    tableScrollView.documentView = self.tableView;
    tableScrollView.hasVerticalScroller = YES;
    tableScrollView.hasHorizontalScroller = YES;
    [self.view addSubview:tableScrollView];
    
    // 日志文本视图
    self.logTextView = [[AdaptiveTextView alloc] init];
    self.logTextView.font = [NSFont fontWithName:@"Menlo" size:12];
    self.logTextView.editable = NO;
    self.logTextView.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    [self.logTextView updateColorsForCurrentAppearance];
    
    self.logScrollView = [[NSScrollView alloc] init];
    self.logScrollView.documentView = self.logTextView;
    self.logScrollView.hasVerticalScroller = YES;
    self.logScrollView.hasHorizontalScroller = YES;
    [self.view addSubview:self.logScrollView];
    
    // 按钮
    self.openButton = [NSButton buttonWithTitle:@"Open FLV File" target:self action:@selector(openFile:)];
    self.openButton.bezelStyle = NSBezelStyleRounded;
    self.openButton.bezelColor = [NSColor adaptiveButtonColor];
    
    self.myCopyButton = [NSButton buttonWithTitle:@"Copy Log" target:self action:@selector(copyLog:)];
    self.myCopyButton.bezelStyle = NSBezelStyleRounded;
    self.myCopyButton.bezelColor = [NSColor adaptiveButtonColor];
    self.myCopyButton.enabled = NO;
    
    self.exportButton = [NSButton buttonWithTitle:@"Export Log" target:self action:@selector(exportLog:)];
    self.exportButton.bezelStyle = NSBezelStyleRounded;
    self.exportButton.bezelColor = [NSColor adaptiveButtonColor];
    self.exportButton.enabled = NO;
    
    [self.view addSubview:self.openButton];
    [self.view addSubview:self.myCopyButton];
    [self.view addSubview:self.exportButton];
    
    // 进度指示器
    self.progressIndicator = [[NSProgressIndicator alloc] init];
    self.progressIndicator.style = NSProgressIndicatorStyleSpinning;
    self.progressIndicator.controlSize = NSControlSizeSmall;
    self.progressIndicator.hidden = YES;
    [self.view addSubview:self.progressIndicator];
}

- (void)layoutControls {
    NSRect viewBounds = self.view.bounds;
    CGFloat padding = 20;
    CGFloat buttonHeight = 30;
    CGFloat buttonWidth = 120;
    CGFloat tableHeight = 50;
    
    // 表格视图
    NSRect tableFrame = NSMakeRect(
        padding,
        viewBounds.size.height - tableHeight - padding,
        viewBounds.size.width - 2 * padding,
        tableHeight - padding / 2
    );
    self.tableView.enclosingScrollView.frame = tableFrame;
    
    // 日志视图
    NSRect logFrame = NSMakeRect(
        padding,
        padding * 2 + buttonHeight,
        viewBounds.size.width - 2 * padding,
        viewBounds.size.height - tableHeight - buttonHeight - padding * 3
    );
    self.logScrollView.frame = logFrame;
    
    // 按钮
    CGFloat buttonY = padding;
    CGFloat buttonSpacing = 20;
    
    self.openButton.frame = NSMakeRect(
        padding,
        buttonY,
        buttonWidth,
        buttonHeight
    );
    
    self.myCopyButton.frame = NSMakeRect(
        padding * 2 + buttonWidth,
        buttonY,
        buttonWidth,
        buttonHeight
    );
    
    self.exportButton.frame = NSMakeRect(
        padding * 3 + buttonWidth * 2,
        buttonY,
        buttonWidth,
        buttonHeight
    );
    
    // 进度指示器
    self.progressIndicator.frame = NSMakeRect(
        viewBounds.size.width - padding - 30,
        buttonY,
        30,
        30
    );
}

- (void)openFile:(id)sender {
    NSOpenPanel *openPanel = [NSOpenPanel openPanel];
    openPanel.allowedFileTypes = @[@"flv"];
    openPanel.allowsMultipleSelection = NO;
    
    __weak typeof(self) weakSelf = self;
    [openPanel beginWithCompletionHandler:^(NSInteger result) {
        if (result == NSModalResponseOK) {
            NSURL *fileURL = openPanel.URLs.firstObject;
            [weakSelf parseFLVFileAtURL:fileURL];
        }
    }];
}

- (void)parseFLVFileAtURL:(NSURL *)fileURL {
    // 禁用按钮并显示进度指示器
    self.openButton.enabled = NO;
    self.myCopyButton.enabled = NO;
    self.exportButton.enabled = NO;
    self.progressIndicator.hidden = NO;
    [self.progressIndicator startAnimation:nil];
    
    // 在后台线程执行解析
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        NSString *logOutput = [FLVParserService parseFLVFileAtPath:fileURL.path];
        
        // 在主线程更新UI
        dispatch_async(dispatch_get_main_queue(), ^{
            self.logContent = logOutput;
            self.logLines = [logOutput componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]];
            [self processLogLines];
            
            self.logTextView.string = logOutput;
            [self.tableView reloadData];
            
            // 启用按钮并隐藏进度指示器
            self.openButton.enabled = YES;
            self.myCopyButton.enabled = YES;
            self.exportButton.enabled = YES;
            self.progressIndicator.hidden = YES;
            [self.progressIndicator stopAnimation:nil];
            
            // 重新应用当前的外观设置
            [self updateAppearance];
        });
    });
}

- (void)processLogLines {
    self.parsedTags = [NSMutableArray array];
    
    // 解析日志行提取结构化数据
    for (NSString *line in self.logLines) {
        if ([line containsString:@"["] && [line containsString:@"]"]) {
            NSArray *components = [line componentsSeparatedByString:@"|"];
            if (components.count >= 1) {
                NSString *headerPart = components[0];
                
                // 解析标签类型、数据大小和时间戳
                NSRegularExpression *regex = [NSRegularExpression regularExpressionWithPattern:@"\
$$\
(\\w+)\
$$\
\\s+(\\d+)\\s+(\\d+)"
                                                                                      options:0
                                                                                        error:nil];
                NSTextCheckingResult *match = [regex firstMatchInString:headerPart
                                                               options:0
                                                                 range:NSMakeRange(0, headerPart.length)];
                
                if (match && match.numberOfRanges >= 4) {
                    NSMutableDictionary *tagInfo = [NSMutableDictionary dictionary];
                    
                    // 标签类型
                    NSString *tagType = [headerPart substringWithRange:[match rangeAtIndex:1]];
                    tagInfo[@"Type"] = tagType;
                    
                    // 数据大小
                    NSString *dataSize = [headerPart substringWithRange:[match rangeAtIndex:2]];
                    tagInfo[@"Size"] = dataSize;
                    
                    // 时间戳
                    NSString *timestamp = [headerPart substringWithRange:[match rangeAtIndex:3]];
                    tagInfo[@"Timestamp"] = timestamp;
                    
                    // 标签详细信息
                    if (components.count >= 2) {
                        tagInfo[@"Details"] = components[1];
                    } else {
                        tagInfo[@"Details"] = @"";
                    }
                    
                    [self.parsedTags addObject:tagInfo];
                }
            }
        }
    }
}

- (void)copyLog:(id)sender {
    if (self.logContent) {
        NSPasteboard *pasteboard = [NSPasteboard generalPasteboard];
        [pasteboard clearContents];
        [pasteboard setString:self.logContent forType:NSPasteboardTypeString];
    }
}

- (void)exportLog:(id)sender {
    if (!self.logContent) return;
    
    NSSavePanel *savePanel = [NSSavePanel savePanel];
    savePanel.allowedFileTypes = @[@"log"];
    savePanel.nameFieldStringValue = @"flv_parser.log";
    
    [savePanel beginWithCompletionHandler:^(NSInteger result) {
        if (result == NSModalResponseOK) {
            NSURL *fileURL = savePanel.URL;
            [self.logContent writeToURL:fileURL atomically:YES encoding:NSUTF8StringEncoding error:nil];
        }
    }];
}

#pragma mark - NSTableViewDataSource

- (NSInteger)numberOfRowsInTableView:(NSTableView *)tableView {
    return self.parsedTags.count;
}

- (NSView *)tableView:(NSTableView *)tableView viewForTableColumn:(NSTableColumn *)tableColumn row:(NSInteger)row {
    NSDictionary *tagInfo = self.parsedTags[row];
    NSString *identifier = tableColumn.identifier;
    NSTableCellView *cell = [tableView makeViewWithIdentifier:identifier owner:self];
    
    if (!cell) {
        cell = [[NSTableCellView alloc] init];
        NSTextField *textField = [[NSTextField alloc] initWithFrame:NSZeroRect];
        textField.bezeled = NO;
        textField.drawsBackground = NO;
        textField.editable = NO;
        textField.font = [NSFont systemFontOfSize:13];
        textField.autoresizingMask = NSViewWidthSizable;
        
        // 使用自适应文本颜色
        textField.textColor = [NSColor adaptiveTextColor];
        
        cell.textField = textField;
        [cell addSubview:textField];
        cell.identifier = identifier;
    }
        
    if ([identifier isEqualToString:@"Type"]) {
        cell.textField.stringValue = tagInfo[@"Type"];
    } else if ([identifier isEqualToString:@"Size"]) {
        cell.textField.stringValue = tagInfo[@"Size"];
    } else if ([identifier isEqualToString:@"Timestamp"]) {
        cell.textField.stringValue = tagInfo[@"Timestamp"];
    } else if ([identifier isEqualToString:@"Details"]) {
        cell.textField.stringValue = tagInfo[@"Details"];
    }
    
    return cell;
}

- (void)tableView:(NSTableView *)tableView didAddRowView:(NSTableRowView *)rowView forRow:(NSInteger)row {
    // 更新行视图背景色
    if (@available(macOS 10.14, *)) {
        if (row % 2 == 0) {
            rowView.backgroundColor = [NSColor adaptiveTableRowColor];
        } else {
            rowView.backgroundColor = [NSColor adaptiveTableAlternateRowColor];
        }
    } else {
        if (row % 2 == 0) {
            rowView.backgroundColor = [NSColor whiteColor];
        } else {
            rowView.backgroundColor = [NSColor colorWithCalibratedWhite:0.97 alpha:1.0];
        }
    }
}

@end
