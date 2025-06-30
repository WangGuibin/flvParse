# flvParse
一个python实现的flv文件解析工具
![FLV文件解析器 2025_6_10 20_13_09](https://github.com/user-attachments/assets/e2b4a3dc-5ed4-412b-838d-1c590ff5854c)


`LFFLVWriter.h/LFFLVWriter.m`

```objc
#import <Foundation/Foundation.h>
@class LFFLVMetaDataConfig;
@class LFVideoFrame;
@class LFAudioFrame;

NS_ASSUME_NONNULL_BEGIN

typedef void (^LFFLVWriterErrorBlock)(NSError *error);

@interface LFFLVWriterStats : NSObject
@property (nonatomic, assign, readonly) NSUInteger videoFrameCount;
@property (nonatomic, assign, readonly) NSUInteger audioFrameCount;
@property (nonatomic, assign, readonly) NSUInteger tagCount;
@property (nonatomic, assign, readonly) uint64_t   fileSize;
@property (nonatomic, assign, readonly) NSTimeInterval lastVideoTimestamp;
@property (nonatomic, assign, readonly) NSTimeInterval lastAudioTimestamp;
@end

@interface LFFLVWriter : NSObject

@property (nonatomic, strong, readonly) LFFLVWriterStats *stats;

/// 自动帧时间戳，YES则自动递增帧时间戳，NO则用传入帧的timestamp
@property (nonatomic, assign) BOOL enableAutoTimestamp;
@property (nonatomic, assign) NSTimeInterval videoFrameInterval; // ms，默认40=25fps
@property (nonatomic, assign) NSTimeInterval audioFrameInterval; // ms，默认23=44100Hz AAC

- (instancetype)initWithFilePath:(NSString *)filePath
                      metaConfig:(LFFLVMetaDataConfig *)metaConfig
                   flushInterval:(NSTimeInterval)flushInterval
                      errorBlock:(LFFLVWriterErrorBlock)errorBlock;

/// 写入metadata（可多次写入，回填duration可用）
- (void)writeMetaData;

/// 重写metadata（回填duration等，seek到0重新写meta tag）
- (void)rewriteMetaDataWithConfig:(LFFLVMetaDataConfig *)metaConfig;

/// 写入视频SPS+PPS为FLV Video Sequence Header
- (void)writeVideoSequenceHeaderWithSPS:(NSData *)sps pps:(NSData *)pps timestamp:(uint32_t)timestamp;

/// 写入音频AAC Sequence Header
- (void)writeAudioSequenceHeaderWithAudioInfo:(NSData *)audioInfo timestamp:(uint32_t)timestamp;

/// 写入视频帧（支持多NALU）
- (void)writeVideoFrame:(LFVideoFrame *)frame;

/// 写入音频帧
- (void)writeAudioFrame:(LFAudioFrame *)frame;

/// 异步写入视频帧（线程安全）
- (void)asyncWriteVideoFrame:(LFVideoFrame *)frame;

/// 异步写入音频帧（线程安全）
- (void)asyncWriteAudioFrame:(LFAudioFrame *)frame;

/// 手动刷新文件
- (void)flush;

/// 关闭写入器
- (void)closeFile;

@end

NS_ASSUME_NONNULL_END

#import "LFFLVWriter.h"
#import "LFFLVMetaDataConfig.h"
#import "LFFLVAMF0MetaDataBuilder.h"
#import "LFVideoFrame.h"
#import "LFAudioFrame.h"

#define LFFLV_TAG_TYPE_AUDIO  0x08
#define LFFLV_TAG_TYPE_VIDEO  0x09
#define LFFLV_TAG_TYPE_SCRIPT 0x12

@interface LFFLVWriterStats ()
@property (nonatomic, assign) NSUInteger videoFrameCount;
@property (nonatomic, assign) NSUInteger audioFrameCount;
@property (nonatomic, assign) NSUInteger tagCount;
@property (nonatomic, assign) uint64_t   fileSize;
@property (nonatomic, assign) NSTimeInterval lastVideoTimestamp;
@property (nonatomic, assign) NSTimeInterval lastAudioTimestamp;
@end
@implementation LFFLVWriterStats
@end

@interface LFFLVWriter ()
@property (nonatomic, strong) NSFileHandle *fileHandle;
@property (nonatomic, copy) NSString *filePath;
@property (nonatomic, strong) LFFLVMetaDataConfig *metaConfig;
@property (nonatomic, copy) LFFLVWriterErrorBlock errorBlock;
@property (nonatomic, strong) LFFLVWriterStats *stats;
@property (nonatomic, assign) NSTimeInterval flushInterval;
@property (nonatomic, strong) NSTimer *flushTimer;
@property (nonatomic, strong) dispatch_queue_t flvWriterQueue;
@property (nonatomic, assign) uint32_t nextVideoTimestamp;
@property (nonatomic, assign) uint32_t nextAudioTimestamp;
@end

@implementation LFFLVWriter

- (instancetype)initWithFilePath:(NSString *)filePath
                      metaConfig:(LFFLVMetaDataConfig *)metaConfig
                   flushInterval:(NSTimeInterval)flushInterval
                      errorBlock:(LFFLVWriterErrorBlock)errorBlock
{
    if (self = [super init]) {
        _filePath = [filePath copy];
        _metaConfig = metaConfig;
        _errorBlock = errorBlock;
        _stats = [LFFLVWriterStats new];
        _flushInterval = flushInterval;
        _flvWriterQueue = dispatch_queue_create("com.lfflvwriter.queue", DISPATCH_QUEUE_SERIAL);
        _enableAutoTimestamp = NO;
        _videoFrameInterval = 40;
        _audioFrameInterval = 23;
        _nextVideoTimestamp = 0;
        _nextAudioTimestamp = 0;

        if (![[NSFileManager defaultManager] createFileAtPath:_filePath contents:nil attributes:nil]) {
            if (_errorBlock) _errorBlock([NSError errorWithDomain:@"LFFLVWriter" code:1 userInfo:@{NSLocalizedDescriptionKey: @"创建文件失败"}]);
            return nil;
        }
        _fileHandle = [NSFileHandle fileHandleForWritingAtPath:_filePath];
        if (!_fileHandle) {
            if (_errorBlock) _errorBlock([NSError errorWithDomain:@"LFFLVWriter" code:2 userInfo:@{NSLocalizedDescriptionKey: @"打开文件失败"}]);
            return nil;
        }
        [self writeFLVHeader];
        if (_flushInterval > 0) {
            _flushTimer = [NSTimer scheduledTimerWithTimeInterval:_flushInterval target:self selector:@selector(flush) userInfo:nil repeats:YES];
        }
    }
    return self;
}

- (void)dealloc {
    [self.flushTimer invalidate];
    [self closeFile];
}

- (void)writeFLVHeader {
    if (!self.fileHandle) return;
    uint8_t flvHeader[] = {'F','L','V',0x01,0x00,0x00,0x00,0x00,0x09};
    if (self.metaConfig.streamType == LFFLVStreamTypeAV)
        flvHeader[4] = 0x05;
    else if (self.metaConfig.streamType == LFFLVStreamTypeVideo)
        flvHeader[4] = 0x01;
    else if (self.metaConfig.streamType == LFFLVStreamTypeAudio)
        flvHeader[4] = 0x04;
    [self.fileHandle writeData:[NSData dataWithBytes:flvHeader length:9]];
    uint8_t firstPrevTagSize[] = {0x00,0x00,0x00,0x00};
    [self.fileHandle writeData:[NSData dataWithBytes:firstPrevTagSize length:4]];
    [self updateStats];
}

- (void)writeMetaData {
    dispatch_sync(_flvWriterQueue, ^{
        if (!self.fileHandle) return;
        NSData *metaData = [LFFLVAMF0MetaDataBuilder buildMetaDataWithConfig:self.metaConfig];
        [self writeTagWithType:LFFLV_TAG_TYPE_SCRIPT timestamp:0 data:metaData];
    });
}

- (void)rewriteMetaDataWithConfig:(LFFLVMetaDataConfig *)metaConfig {
    dispatch_sync(_flvWriterQueue, ^{
        if (!self.fileHandle) return;
        NSData *metaData = [LFFLVAMF0MetaDataBuilder buildMetaDataWithConfig:metaConfig];
        [self.fileHandle seekToFileOffset:0];
        [self writeFLVHeader];
        [self writeTagWithType:LFFLV_TAG_TYPE_SCRIPT timestamp:0 data:metaData];
    });
}

- (void)writeVideoSequenceHeaderWithSPS:(NSData *)sps pps:(NSData *)pps timestamp:(uint32_t)timestamp {
    dispatch_sync(_flvWriterQueue, ^{
        if (!self.fileHandle || !sps || !pps || sps.length < 4) return;
        NSMutableData *tagData = [NSMutableData data];
        uint8_t header[5] = {0x17, 0x00, 0x00, 0x00, 0x00};
        [tagData appendBytes:header length:5];
        [tagData appendBytes:"\x01" length:1];
        [tagData appendData:[sps subdataWithRange:NSMakeRange(1, 3)]];
        [tagData appendBytes:"\xff" length:1];
        uint8_t numOfSPS = 0xE1;
        [tagData appendBytes:&numOfSPS length:1];
        uint16_t spsLen = htons((uint16_t)sps.length);
        [tagData appendBytes:&spsLen length:2];
        [tagData appendData:sps];
        uint8_t numOfPPS = 0x01;
        [tagData appendBytes:&numOfPPS length:1];
        uint16_t ppsLen = htons((uint16_t)pps.length);
        [tagData appendBytes:&ppsLen length:2];
        [tagData appendData:pps];
        [self writeTagWithType:LFFLV_TAG_TYPE_VIDEO timestamp:timestamp data:tagData];
    });
}

- (void)writeAudioSequenceHeaderWithAudioInfo:(NSData *)audioInfo timestamp:(uint32_t)timestamp {
    dispatch_sync(_flvWriterQueue, ^{
        if (!self.fileHandle || !audioInfo) return;
        NSMutableData *tagData = [NSMutableData data];
        uint8_t audioHeader = [self audioHeaderByConfig];
        [tagData appendBytes:&audioHeader length:1];
        uint8_t aacPacketType = 0x00;
        [tagData appendBytes:&aacPacketType length:1];
        [tagData appendData:audioInfo];
        [self writeTagWithType:LFFLV_TAG_TYPE_AUDIO timestamp:timestamp data:tagData];
    });
}

- (void)writeVideoFrame:(LFVideoFrame *)frame {
    dispatch_sync(_flvWriterQueue, ^{
        if (!self.fileHandle || !frame.data) return;
        if (self.enableAutoTimestamp) {
            frame.timestamp = self.nextVideoTimestamp;
            self.nextVideoTimestamp += (uint32_t)self.videoFrameInterval;
        }
        NSMutableData *tagData = [NSMutableData data];
        uint8_t header[5];
        header[0] = frame.isKeyFrame ? 0x17 : 0x27;
        header[1] = 0x01;
        header[2] = header[3] = header[4] = 0;
        [tagData appendBytes:header length:5];
        // 支持多NALU
        const uint8_t *bytes = frame.data.bytes;
        NSUInteger offset = 0, len = frame.data.length;
        while (offset + 4 <= len) {
            uint32_t naluLen = (bytes[offset] << 24) | (bytes[offset+1] << 16) | (bytes[offset+2] << 8) | bytes[offset+3];
            if (offset + 4 + naluLen > len) break;
            uint32_t beNaluLen = htonl(naluLen);
            [tagData appendBytes:&beNaluLen length:4];
            [tagData appendBytes:bytes + offset + 4 length:naluLen];
            offset += 4 + naluLen;
            if (naluLen == 0) break;
        }
        [self writeTagWithType:LFFLV_TAG_TYPE_VIDEO timestamp:frame.timestamp data:tagData];
        self.stats.videoFrameCount++;
        self.stats.lastVideoTimestamp = frame.timestamp;
        [self updateStats];
    });
}

- (void)writeAudioFrame:(LFAudioFrame *)frame {
    dispatch_sync(_flvWriterQueue, ^{
        if (!self.fileHandle || !frame.data) return;
        if (self.enableAutoTimestamp) {
            frame.timestamp = self.nextAudioTimestamp;
            self.nextAudioTimestamp += (uint32_t)self.audioFrameInterval;
        }
        NSMutableData *tagData = [NSMutableData data];
        uint8_t audioHeader = [self audioHeaderByConfig];
        [tagData appendBytes:&audioHeader length:1];
        uint8_t aacPacketType = 0x01;
        [tagData appendBytes:&aacPacketType length:1];
        [tagData appendData:frame.data];
        [self writeTagWithType:LFFLV_TAG_TYPE_AUDIO timestamp:frame.timestamp data:tagData];
        self.stats.audioFrameCount++;
        self.stats.lastAudioTimestamp = frame.timestamp;
        [self updateStats];
    });
}

- (void)asyncWriteVideoFrame:(LFVideoFrame *)frame {
    dispatch_async(_flvWriterQueue, ^{
        [self writeVideoFrame:frame];
    });
}

- (void)asyncWriteAudioFrame:(LFAudioFrame *)frame {
    dispatch_async(_flvWriterQueue, ^{
        [self writeAudioFrame:frame];
    });
}

- (void)writeTagWithType:(uint8_t)tagType timestamp:(uint32_t)timestamp data:(NSData *)data {
    if (!self.fileHandle || !data) return;
    uint8_t tagHeader[11];
    tagHeader[0] = tagType;
    tagHeader[1] = (data.length >> 16) & 0xFF;
    tagHeader[2] = (data.length >> 8) & 0xFF;
    tagHeader[3] = data.length & 0xFF;
    tagHeader[4] = (timestamp >> 16) & 0xFF;
    tagHeader[5] = (timestamp >> 8) & 0xFF;
    tagHeader[6] = timestamp & 0xFF;
    tagHeader[7] = (timestamp >> 24) & 0xFF;
    tagHeader[8] = tagHeader[9] = tagHeader[10] = 0;
    @try {
        [self.fileHandle writeData:[NSData dataWithBytes:tagHeader length:11]];
        [self.fileHandle writeData:data];
        uint32_t prevTagSize = (uint32_t)(11 + data.length);
        uint8_t prevTagSizeBytes[4] = {
            (prevTagSize >> 24) & 0xFF,
            (prevTagSize >> 16) & 0xFF,
            (prevTagSize >> 8) & 0xFF,
            prevTagSize & 0xFF
        };
        [self.fileHandle writeData:[NSData dataWithBytes:prevTagSizeBytes length:4]];
        self.stats.tagCount++;
        [self updateStats];
    } @catch (NSException *ex) {
        if (self.errorBlock) self.errorBlock([NSError errorWithDomain:@"LFFLVWriter" code:3 userInfo:@{NSLocalizedDescriptionKey: @"文件写入异常"}]);
    }
}

- (uint8_t)audioHeaderByConfig {
    uint8_t soundFormat = 10 << 4;
    uint8_t soundRate = 3 << 2;
    switch (self.metaConfig.audioSampleRate) {
        case 5500: case 5512: case 8000:
            soundRate = 0 << 2; break;
        case 11025:
            soundRate = 1 << 2; break;
        case 22050:
            soundRate = 2 << 2; break;
        case 44100:
        default:
            soundRate = 3 << 2; break;
    }
    uint8_t soundSize = (self.metaConfig.audioSampleSize == 16 ? 1 : 0) << 1;
    uint8_t soundType = (self.metaConfig.channels == 2 ? 1 : 0);
    uint8_t audioHeader = soundFormat | soundRate | soundSize | soundType;
    return audioHeader;
}

- (void)updateStats {
    self.stats.fileSize = [[[NSFileManager defaultManager] attributesOfItemAtPath:self.filePath error:nil][NSFileSize] unsignedLongLongValue];
}

- (void)flush {
    dispatch_sync(_flvWriterQueue, ^{
        if (self.fileHandle) {
            [self.fileHandle synchronizeFile];
            [self updateStats];
        }
    });
}

- (void)closeFile {
    [self.flushTimer invalidate]; self.flushTimer = nil;
    dispatch_sync(_flvWriterQueue, ^{
        if (self.fileHandle) {
            [self.fileHandle closeFile];
            self.fileHandle = nil;
        }
    });
}

@end

```

iOS开发中结合[【LFLiveKit】](https://github.com/LaiFengiOS/LFLiveKit)来写`flv`文件 

这里给出线程安全、自动时间戳、完整带注释的 Objective-C FLV 录制器头文件和实现文件，并附上详细的使用示例。
本实现集成了：

* 多NALU、回调、自动flush
* 实时进度统计
* 自动帧时间戳
* 线程安全（串行队列封装所有写操作）
* 全部头/实现文件规范分离

```objc
#import "LFFLVWriter.h"
#import "LFFLVMetaDataConfig.h"
#import "LFVideoFrame.h"
#import "LFAudioFrame.h"

// 1. 配置meta
LFFLVMetaDataConfig *cfg = [LFFLVMetaDataConfig new];
cfg.streamType = LFFLVStreamTypeAV;
cfg.duration = 0;
cfg.width = 1920;
cfg.height = 1080;
cfg.framerate = 25;
cfg.videoCodecId = 7;
cfg.audioSampleRate = 44100;
cfg.audioSampleSize = 16;
cfg.audioCodecId = 10;
cfg.channels = 2;
cfg.stereo = YES;

// 2. 初始化writer，2秒flush，错误回调
LFFLVWriter *writer = [[LFFLVWriter alloc] initWithFilePath:@"/tmp/test.flv"
                                                 metaConfig:cfg
                                              flushInterval:2.0
                                                 errorBlock:^(NSError *error) {
    NSLog(@"FLV写入错误: %@", error.localizedDescription);
}];
writer.enableAutoTimestamp = YES;
writer.videoFrameInterval = 40; // 25fps
writer.audioFrameInterval = 23; // 44100Hz AAC

[writer writeMetaData];
[writer writeVideoSequenceHeaderWithSPS:vframe.sps pps:vframe.pps timestamp:0];
[writer writeAudioSequenceHeaderWithAudioInfo:aframe.audioInfo timestamp:0];

// 3. 异步写入帧（线程安全，适合采集多线程）
[writer asyncWriteVideoFrame:vframe];
[writer asyncWriteAudioFrame:aframe];

// 4. 查询进度
NSLog(@"视频帧:%lu, 音频帧:%lu, 文件字节:%llu",
      (unsigned long)writer.stats.videoFrameCount,
      (unsigned long)writer.stats.audioFrameCount,
      writer.stats.fileSize);

// 5. 录制结束回填duration
cfg.duration = writer.stats.lastVideoTimestamp / 1000.0;
[writer rewriteMetaDataWithConfig:cfg];
[writer closeFile];
```
