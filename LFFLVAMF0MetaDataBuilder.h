#import <Foundation/Foundation.h>
@class LFFLVMetaDataConfig;

@interface LFFLVAMF0MetaDataBuilder : NSObject

+ (NSData *)buildMetaDataWithConfig:(LFFLVMetaDataConfig *)config;
+ (NSData *)patchMetaData:(NSData *)oriMetaData withConfig:(LFFLVMetaDataConfig *)config;

@end