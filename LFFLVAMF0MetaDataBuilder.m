#import "LFFLVAMF0MetaDataBuilder.h"
#import "LFFLVMetaDataConfig.h"

@implementation LFFLVAMF0MetaDataBuilder

+ (NSData *)buildMetaDataWithConfig:(LFFLVMetaDataConfig *)cfg {
    NSMutableData *meta = [NSMutableData data];
    [self appendAMF0String:@"onMetaData" toData:meta];
    NSMutableArray *fields = [NSMutableArray array];
    [fields addObject:@[@"duration", @(cfg.duration)]];
    if (cfg.streamType == LFFLVStreamTypeAV || cfg.streamType == LFFLVStreamTypeVideo) {
        [fields addObject:@[@"width", @(cfg.width)]];
        [fields addObject:@[@"height", @(cfg.height)]];
        [fields addObject:@[@"framerate", @(cfg.framerate)]];
        [fields addObject:@[@"videocodecid", @(cfg.videoCodecId)]];
    }
    if (cfg.streamType == LFFLVStreamTypeAV || cfg.streamType == LFFLVStreamTypeAudio) {
        [fields addObject:@[@"audiosamplerate", @(cfg.audioSampleRate)]];
        [fields addObject:@[@"audiosamplesize", @(cfg.audioSampleSize)]];
        [fields addObject:@[@"audiocodecid", @(cfg.audioCodecId)]];
        [fields addObject:@[@"channels", @(cfg.channels)]];
        [fields addObject:@[@"stereo", @(cfg.stereo)]];
    }
    for (NSString *key in cfg.customMetaFields) {
        id val = cfg.customMetaFields[key];
        [fields addObject:@[key, val]];
    }
    [meta appendBytes:"\x08" length:1];
    uint32_t count = htonl((uint32_t)fields.count);
    [meta appendBytes:&count length:4];
    for (NSArray *field in fields) {
        NSString *key = field[0];
        id value = field[1];
        if ([value isKindOfClass:[NSNumber class]]) {
            const char *type = [value objCType];
            if (strcmp(type, @encode(BOOL)) == 0 || [key.lowercaseString isEqualToString:@"stereo"]) {
                [self appendAMF0StringKey:key toData:meta];
                [meta appendBytes:"\x01" length:1];
                uint8_t boolValue = [value boolValue] ? 1 : 0;
                [meta appendBytes:&boolValue length:1];
            } else {
                [self appendAMF0Key:key doubleValue:[value doubleValue] toData:meta];
            }
        } else if ([value isKindOfClass:[NSString class]]) {
            [self appendAMF0StringKey:key toData:meta];
            [self appendAMF0StringValue:value toData:meta];
        }
    }
    [meta appendBytes:"\x00\x00\x09" length:3];
    return meta;
}

+ (NSData *)patchMetaData:(NSData *)oriMetaData withConfig:(LFFLVMetaDataConfig *)cfg {
    return [self buildMetaDataWithConfig:cfg];
}

+ (void)appendAMF0String:(NSString *)str toData:(NSMutableData *)data {
    [data appendBytes:"\x02" length:1];
    uint16_t len = htons((uint16_t)str.length);
    [data appendBytes:&len length:2];
    [data appendData:[str dataUsingEncoding:NSUTF8StringEncoding]];
}

+ (void)appendAMF0Key:(NSString *)key doubleValue:(double)value toData:(NSMutableData *)data {
    [self appendAMF0StringKey:key toData:data];
    [self appendAMF0Double:value toData:data];
}

+ (void)appendAMF0StringKey:(NSString *)key toData:(NSMutableData *)data {
    uint16_t len = htons((uint16_t)key.length);
    [data appendBytes:&len length:2];
    [data appendData:[key dataUsingEncoding:NSUTF8StringEncoding]];
}

+ (void)appendAMF0Double:(double)value toData:(NSMutableData *)data {
    [data appendBytes:"\x00" length:1];
    uint64_t v;
    memcpy(&v, &value, sizeof(double));
    v = CFSwapInt64HostToBig(v);
    [data appendBytes:&v length:8];
}

+ (void)appendAMF0StringValue:(NSString *)value toData:(NSMutableData *)data {
    [data appendBytes:"\x02" length:1];
    uint16_t len = htons((uint16_t)value.length);
    [data appendBytes:&len length:2];
    [data appendData:[value dataUsingEncoding:NSUTF8StringEncoding]];
}

@end