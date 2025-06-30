#import <Foundation/Foundation.h>
@interface LFVideoFrame : NSObject
@property (nonatomic, assign) BOOL isKeyFrame;
@property (nonatomic, assign) uint32_t timestamp;
@property (nonatomic, strong) NSData *data; // 一帧包括一到多个NALU, 必须按4字节长度分割
@property (nonatomic, strong) NSData *sps;
@property (nonatomic, strong) NSData *pps;
@end