#import "LFFLVMetaDataConfig.h"

@implementation LFFLVMetaDataConfig

- (instancetype)init {
    if (self = [super init]) {
        _streamType = LFFLVStreamTypeAV;
        _customMetaFields = [NSMutableDictionary dictionary];
    }
    return self;
}

- (void)setCustomMetaField:(NSString *)fieldName value:(id)value {
    if (fieldName.length == 0 || value == nil) return;
    self.customMetaFields[fieldName] = value;
}

@end