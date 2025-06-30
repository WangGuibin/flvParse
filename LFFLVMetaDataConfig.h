#import <Foundation/Foundation.h>

typedef NS_ENUM(NSUInteger, LFFLVStreamType) {
    LFFLVStreamTypeAV,
    LFFLVStreamTypeVideo,
    LFFLVStreamTypeAudio
};

@interface LFFLVMetaDataConfig : NSObject

@property (nonatomic, assign) LFFLVStreamType streamType;
@property (nonatomic, assign) double duration;
@property (nonatomic, assign) NSInteger width;
@property (nonatomic, assign) NSInteger height;
@property (nonatomic, assign) NSInteger framerate;
@property (nonatomic, assign) NSInteger videoCodecId;
@property (nonatomic, assign) NSInteger audioSampleRate;
@property (nonatomic, assign) NSInteger audioSampleSize;
@property (nonatomic, assign) NSInteger audioCodecId;
@property (nonatomic, assign) NSInteger channels;
@property (nonatomic, assign) BOOL stereo;
@property (nonatomic, strong) NSMutableDictionary<NSString *, id> *customMetaFields;

- (void)setCustomMetaField:(NSString *)fieldName value:(id)value;

@end