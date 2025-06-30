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