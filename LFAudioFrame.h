#import <Foundation/Foundation.h>
@interface LFAudioFrame : NSObject
@property (nonatomic, assign) uint32_t timestamp;
@property (nonatomic, strong) NSData *data; // AAC帧数据
@property (nonatomic, strong) NSData *audioInfo; // AAC Sequence header
@end