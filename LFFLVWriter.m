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