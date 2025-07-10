//
//  FLVParserService.h
//  FLVParserGUI
//
//  Created by 王贵彬 on 2025/7/10.
//

#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface FLVParserService : NSObject

+ (NSString *)parseFLVFileAtPath:(NSString *)path;

@end

NS_ASSUME_NONNULL_END
