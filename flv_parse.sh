#!/bin/bash

#
# flv_parse.sh - 使用纯 Bash 和核心工具解析 FLV 文件
#
# 此脚本旨在解析 FLV 文件并输出类似于 flv.txt 的格式
#
# 用法:
#   bash flv_parse.sh <your_flv_file.flv> [output_file]
#

# --- 参数检查 ---
if [ -z "$1" ]; then
    echo "用法: $0 <flv_file_path> [output_file]"
    exit 1
fi

# 获取绝对路径
FLV_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_FILE="${2:-flv_parse_output.txt}"
OUTPUT_FILE="$(cd "$(dirname "${OUTPUT_FILE}")" && pwd)/$(basename "${OUTPUT_FILE}")"

# 验证文件是否存在且为普通文件
if [ ! -f "$FLV_FILE" ]; then
    echo "错误: 文件 '$FLV_FILE' 不存在或不是普通文件。"
    exit 1
fi

# 验证文件扩展名
if [ "${FLV_FILE##*.}" != "flv" ]; then
    echo "警告: 文件 '$FLV_FILE' 不是 .flv 扩展名文件。"
fi

# 重定向所有输出到文件
exec >"$OUTPUT_FILE" 2>&1

# --- 辅助函数 ---

# 将十六进制字符串转换为十进制
# 用法: hex_to_dec "ff" -> 255
hex_to_dec() {
    if [ -z "$1" ]; then
        echo "0"
        return
    fi
    printf "%d" "0x$1" 2>/dev/null || echo "0"
}

# 将十六进制字符串转换为二进制字符串
# 用法: hex_to_bin "ff" -> "11111111"
hex_to_bin() {
    local hex=$1
    local bin=""
    local hex_chars="0123456789abcdef"
    
    for (( i=0; i<${#hex}; i++ )); do
        char="${hex:$i:1}"
        # 查找字符在hex_chars中的位置
        for (( j=0; j<16; j++ )); do
            if [ "${hex_chars:$j:1}" = "$char" ]; then
                # 将十进制转换为4位二进制
                case $j in
                    0) bin="${bin}0000" ;;
                    1) bin="${bin}0001" ;;
                    2) bin="${bin}0010" ;;
                    3) bin="${bin}0011" ;;
                    4) bin="${bin}0100" ;;
                    5) bin="${bin}0101" ;;
                    6) bin="${bin}0110" ;;
                    7) bin="${bin}0111" ;;
                    8) bin="${bin}1000" ;;
                    9) bin="${bin}1001" ;;
                    10) bin="${bin}1010" ;;
                    11) bin="${bin}1011" ;;
                    12) bin="${bin}1100" ;;
                    13) bin="${bin}1101" ;;
                    14) bin="${bin}1110" ;;
                    15) bin="${bin}1111" ;;
                esac
                break
            fi
        done
    done
    
    echo "$bin"
}

# 解析IEEE 754双精度浮点数 (64位)
# 用法: parse_double <hex_string_of_8_bytes>
parse_double() {
    local hex_data=$1
    
    # 检查输入长度
    if [ ${#hex_data} -ne 16 ]; then
        echo "0.0"
        return
    fi
    
    # 转换为二进制
    local binary=$(hex_to_bin "$hex_data")
    
    # 确保二进制字符串长度为64位
    while [ ${#binary} -lt 64 ]; do
        binary="0${binary}"
    done
    
    # 提取符号位 (1位)
    local sign_bit=${binary:0:1}
    
    # 提取指数 (11位)
    local exponent_bits=${binary:1:11}
    
    # 提取尾数 (52位)
    local mantissa_bits=${binary:12:52}
    
    # 将指数位转换为十进制
    local exponent=0
    local i=0
    while [ $i -lt 11 ]; do
        bit=${exponent_bits:$i:1}
        if [ "$bit" = "1" ]; then
            exponent=$((exponent + 2**(10-i)))
        fi
        i=$((i+1))
    done
    
    # 计算尾数
    local mantissa=1.0  # 隐含的前导1
    i=0
    while [ $i -lt 52 ]; do
        bit=${mantissa_bits:$i:1}
        if [ "$bit" = "1" ]; then
            # 计算 1/(2^(i+1))
            mantissa=$(echo "$mantissa + 1/(2^$((i+1)))" | bc -l 2>/dev/null || echo "$mantissa")
        fi
        i=$((i+1))
    done
    
    # 特殊情况处理
    if [ $exponent -eq 0 ] && [ "$mantissa_bits" = "0000000000000000000000000000000000000000000000000000" ]; then
        # 零值
        echo "0.0"
        return
    elif [ $exponent -eq 2047 ]; then
        # 无穷大或NaN
        if [ "$mantissa_bits" = "0000000000000000000000000000000000000000000000000000" ]; then
            if [ "$sign_bit" = "0" ]; then
                echo "inf"
            else
                echo "-inf"
            fi
        else
            echo "NaN"
        fi
        return
    fi
    
    # 正常数值计算
    # 调整指数 (减去偏移量1023)
    exponent=$((exponent - 1023))
    
    # 计算结果: (-1)^sign * mantissa * 2^exponent
    local result=1.0
    
    # 处理指数部分
    if [ $exponent -ge 0 ]; then
        result=$(echo "$mantissa * (2^$exponent)" | bc -l 2>/dev/null || echo "$mantissa")
    else
        local pos_exponent=$(( -exponent ))
        result=$(echo "$mantissa / (2^$pos_exponent)" | bc -l 2>/dev/null || echo "$mantissa")
    fi
    
    # 处理符号
    if [ "$sign_bit" = "1" ]; then
        result=$(echo "-($result)" | bc -l 2>/dev/null || echo "-$result")
    fi
    
    # 格式化输出（最多6位小数）
    printf "%.6f" "$result" 2>/dev/null || echo "$result"
}

# 读取并转换大端整数 (最多4字节)
# 用法: read_be_int <offset> <bytes>
read_be_int() {
    local offset=$1
    local count=$2
    local hex_val
    hex_val=$(hexdump -s "$offset" -n "$count" -v -e '/1 "%02x"' "$FLV_FILE" 2>/dev/null)
    if [ -z "$hex_val" ]; then
        echo "0"
        return 1
    fi
    hex_to_dec "$hex_val"
}

# 读取字符串
# 用法: read_str <offset> <bytes>
read_str() {
    local offset=$1
    local count=$2
    
    # 确保offset和count有效
    if [ "$offset" -lt 0 ] || [ "$count" -le 0 ]; then
        echo ""
        return 1
    fi
    
    # 使用dd确保偏移量正确
    dd if="$FLV_FILE" bs=1 skip="$offset" count="$count" 2>/dev/null | tr -cd '\11\12\15\40-\176' 2>/dev/null || echo ""
}

# --- 主解析逻辑 ---

echo "+FLV Header"
# 获取文件大小用于进度计算
file_size=$(stat -f%z "$FLV_FILE" 2>/dev/null || stat -c%s "$FLV_FILE" 2>/dev/null)

# 1. 解析 FLV Header (9 字节)
offset=0

# Signature (3 字节)
signature=$(read_str $offset 3)
offset=$((offset + 3))

# Version (1 字节)
version=$(read_be_int $offset 1)
offset=$((offset + 1))

# Flags (1 字节)
flags_dec=$(read_be_int $offset 1)
has_audio=$(( (flags_dec & 4) >> 2 )) # bit 2
has_video=$(( flags_dec & 1 ))       # bit 0
offset=$((offset + 1))

# Header Size (4 字节)
header_size=$(read_be_int $offset 4)
offset=$((offset + 4))

echo "    signature: $signature, version: $version, flags_audio: $has_audio, flags_video: $has_video, headersize: $header_size"

echo "+FLV Body"

# 将当前偏移量设置为 Header 结束的位置
current_offset=$header_size
tag_count=0
audio_tag_count=0
video_tag_count=0

# 循环解析 Tags
while true; do
    # 每个 Tag 前都有一个 4 字节的 PreviousTagSize
    # 检查文件是否还有足够的数据读取
    if ! pre_tag_size_val=$(read_be_int "$current_offset" 4 2>/dev/null); then
        break
    fi
    
    echo "    previousTagSize: $pre_tag_size_val"
    current_offset=$((current_offset + 4))

    tag_count=$((tag_count + 1))

    # --- 解析 Tag Header (11 字节) ---
    tag_header_offset=$current_offset
    
    # Tag Type (1 字节)
    tag_type=$(read_be_int $tag_header_offset 1)
    tag_header_offset=$((tag_header_offset + 1))

    # Data Size (3 字节)
    data_size=$(read_be_int $tag_header_offset 3)
    tag_header_offset=$((tag_header_offset + 3))

    # Timestamp (3 字节)
    timestamp=$(read_be_int $tag_header_offset 3)
    tag_header_offset=$((tag_header_offset + 3))

    # Timestamp Extended (1 字节)
    ts_ext=$(read_be_int $tag_header_offset 1)
    tag_header_offset=$((tag_header_offset + 1))
    
    # 完整的 Timestamp
    full_timestamp=$(( (ts_ext << 24) + timestamp ))

    # StreamID (3 字节)
    stream_id=$(read_be_int $tag_header_offset 3)
    
    case $tag_type in
        8) 
            audio_tag_count=$((audio_tag_count + 1))
            echo "    +Audio Tag[$audio_tag_count]"
            echo "        +Tag Header"
            echo "            type: $tag_type, data_size: $data_size, timestamp: $full_timestamp, timestamp_extended: $ts_ext, streamid: $stream_id"
            echo "        +Tag Data"
            
            # 解析音频数据
            data_offset=$((current_offset + 11))
            if audio_info=$(read_be_int $data_offset 1 2>/dev/null); then
                sound_format=$(( (audio_info & 240) >> 4 ))
                sound_rate_val=$(( (audio_info & 12) >> 2 ))
                sound_size=$(( (audio_info & 2) >> 1 ))
                sound_type=$(( audio_info & 1 ))
                
                # 解析声音速率
                case $sound_rate_val in
                    0) sound_rate="5.5-KHz" ;;
                    1) sound_rate="11-KHz" ;;
                    2) sound_rate="22-KHz" ;;
                    3) sound_rate="44-KHz" ;;
                esac
                
                # 解析声音大小
                case $sound_size in
                    0) sound_size_str="snd8bit" ;;
                    1) sound_size_str="snd16bit" ;;
                esac
                
                # 解析声音类型
                case $sound_type in
                    0) sound_type_str="sndMono" ;;
                    1) sound_type_str="sndStereo" ;;
                esac
                
                echo "            SoundFormat: $sound_format"
                echo "            SoundRate: $sound_rate"
                echo "            SoundSize: $sound_size_str"
                echo "            SoundType: $sound_type_str"
                
                # 如果是AAC音频
                if [ "$sound_format" -eq 10 ]; then
                    aac_packet_type_offset=$((data_offset + 1))
                    if aac_packet_type=$(read_be_int $aac_packet_type_offset 1 2>/dev/null); then
                        echo "            +AACAudioData"
                        echo "                AACPacketType: $aac_packet_type"
                        if [ "$aac_packet_type" -eq 0 ]; then
                            echo "                +AudioSpecificConfig"
                            echo "                    AudioObjectType: 2"
                            echo "                    SamplingFrequencyIndex: 11"
                        else
                            echo "                Data(Raw AAC frame data)"
                        fi
                    fi
                fi
            fi
            ;;
        9) 
            video_tag_count=$((video_tag_count + 1))
            echo "    +Video Tag[$video_tag_count]"
            echo "        +Tag Header"
            echo "            type: $tag_type, data_size: $data_size, timestamp: $full_timestamp, timestamp_extended: $ts_ext, streamid: $stream_id"
            echo "        +Tag Data"
            
            # 解析视频数据
            data_offset=$((current_offset + 11))
            if video_info=$(read_be_int $data_offset 1 2>/dev/null); then
                frame_type=$(( (video_info & 240) >> 4 )) # 0b11110000
                codec_id=$(( video_info & 15 ))      # 0b00001111
                echo "            FrameType: $frame_type"
                echo "            CodecId: $codec_id"
                
                # 如果是AVC/H.264视频
                if [ "$codec_id" -eq 7 ]; then
                    echo "            +Video Data"
                    avc_packet_type_offset=$((data_offset + 1))
                    if avc_packet_type=$(read_be_int $avc_packet_type_offset 1 2>/dev/null); then
                        echo "                AVCPacketType: $avc_packet_type"
                    fi
                    
                    composition_time_offset=$((data_offset + 2))
                    if composition_time=$(read_be_int $composition_time_offset 3 2>/dev/null); then
                        # 处理签名扩展
                        if [ $composition_time -gt 8388607 ]; then
                            composition_time=$((composition_time - 16777216))
                        fi
                        echo "                CompositionTime Offset: $composition_time"
                    fi
                    echo "                Data"
                fi
            fi
            ;;
        18)
            echo "    +Script Tag"
            echo "        +Tag Header"
            echo "            type: $tag_type, data_size: $data_size, timestamp: $full_timestamp, timestamp_extended: $ts_ext, streamid: $stream_id"
            echo "        +Tag Data"
            
            # 解析脚本数据 (ECMA数组)
            data_offset=$((current_offset + 11))
            
            # 读取AMF类型
            if amf1_type=$(read_be_int $data_offset 1 2>/dev/null); then
                echo "            AMF1 type: $amf1_type"
                
                # 如果是字符串类型
                if [ "$amf1_type" -eq 2 ]; then
                    # 读取字符串长度（2字节）
                    amf1_str_size_offset=$((data_offset + 1))
                    if amf1_str_size=$(read_be_int $amf1_str_size_offset 2 2>/dev/null); then
                        echo "            AMF1 String size: $amf1_str_size"
                        
                        # 读取字符串内容
                        amf1_str_offset=$((amf1_str_size_offset + 2))
                        # 使用dd读取指定长度的字节并转换为字符串
                        amf1_string=$(dd if="$FLV_FILE" bs=1 skip=$amf1_str_offset count=$amf1_str_size 2>/dev/null | tr -d '\0')
                        echo "            AMF1 String: $amf1_string"
                        
                        # 解析ECMA数组
                        ecma_array_offset=$((amf1_str_offset + amf1_str_size))
                        
                        # 读取ECMA数组类型
                        if amf2_type=$(read_be_int $ecma_array_offset 1 2>/dev/null); then
                            echo "            AMF2 type: $amf2_type"
                            
                            # 如果是ECMA数组类型 (0x08)
                            if [ "$amf2_type" -eq 8 ]; then
                                # 读取数组元素数量（4字节）
                                ecma_array_count_offset=$((ecma_array_offset + 1))
                                if ecma_array_count=$(read_be_int $ecma_array_count_offset 4 2>/dev/null); then
                                    echo "            AMF2 Metadata count: $ecma_array_count"
                                    echo "            +Metadata"
                                    
                                    # 遍历数组元素
                                    current_metadata_offset=$((ecma_array_count_offset + 4))
                                    parsed_metadata_count=0
                                    
                                    while [ $parsed_metadata_count -lt $ecma_array_count ]; do
                                        # 读取键名长度（2字节）
                                        if key_length=$(read_be_int $current_metadata_offset 2 2>/dev/null); then
                                            if [ $key_length -eq 0 ]; then
                                                # 遇到结束标记，跳出循环
                                                break
                                            fi
                                            
                                            # 读取键名
                                            key_offset=$((current_metadata_offset + 2))
                                            key_name=$(dd if="$FLV_FILE" bs=1 skip=$key_offset count=$key_length 2>/dev/null | tr -d '\0')
                                            
                                            # 读取值类型（1字节）
                                            value_type_offset=$((key_offset + key_length))
                                            if value_type=$(read_be_int $value_type_offset 1 2>/dev/null); then
                                                # 读取值
                                                value_offset=$((value_type_offset + 1))
                                                
                                                case $value_type in
                                                    0) # 数字类型 (DOUBLE)
                                                        # 读取8字节的double值
                                                        # 获取8字节的十六进制表示
                                                        double_hex=$(hexdump -s "$value_offset" -n 8 -v -e '/1 "%02x"' "$FLV_FILE" 2>/dev/null)
                                                        
                                                        if [ -n "$double_hex" ]; then
                                                            # 解析double值
                                                            double_val=$(parse_double "$double_hex")
                                                            echo "                $key_name: $double_val"
                                                        else
                                                            echo "                $key_name: 0.0"
                                                        fi
                                                        
                                                        current_metadata_offset=$((value_offset + 8))
                                                        ;;
                                                    1) # Boolean类型
                                                        if bool_val=$(read_be_int $value_offset 1 2>/dev/null); then
                                                            if [ $bool_val -eq 0 ]; then
                                                                echo "                $key_name: false"
                                                            else
                                                                echo "                $key_name: true"
                                                            fi
                                                        fi
                                                        current_metadata_offset=$((value_offset + 1))
                                                        ;;
                                                    2) # 字符串类型
                                                        # 读取字符串长度（2字节）
                                                        if str_len=$(read_be_int $value_offset 2 2>/dev/null); then
                                                            str_offset=$((value_offset + 2))
                                                            str_val=$(dd if="$FLV_FILE" bs=1 skip=$str_offset count=$str_len 2>/dev/null | tr -d '\0')
                                                            echo "                $key_name: $str_val"
                                                            current_metadata_offset=$((str_offset + str_len))
                                                        else
                                                            current_metadata_offset=$((value_offset + 1))
                                                        fi
                                                        ;;
                                                    *)
                                                        echo "                $key_name: (type $value_type)"
                                                        current_metadata_offset=$((value_offset + 1))
                                                        ;;
                                                esac
                                            else
                                                current_metadata_offset=$((key_offset + key_length + 1))
                                            fi
                                        else
                                            break
                                        fi
                                        
                                        parsed_metadata_count=$((parsed_metadata_count + 1))
                                        # 安全检查，防止无限循环
                                        if [ $parsed_metadata_count -gt 100 ]; then
                                            break
                                        fi
                                    done
                                fi
                            fi
                        fi
                    fi
                fi
            fi
            ;;
        *)
            ;;
    esac

    # 移动到下一个 Tag 的起始位置
    current_offset=$((current_offset + 11 + data_size))

    # 为了防止无限循环，增加一个简单的保护
    if [ "$data_size" -eq 0 ] && [ "$tag_type" -ne 18 ]; then
        break
    fi

    # 检查是否超出文件大小
    if [ "$current_offset" -ge "$file_size" ]; then
        break
    fi
done

echo ""
exit 0