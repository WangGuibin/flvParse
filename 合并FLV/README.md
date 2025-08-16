

```bash
#!/bin/bash

# 生成带时间戳的输出文件名
timestamp=$(date +%Y%m%d%H%M%S)
output_file="${1%.*}_mix_${timestamp}.flv"

# 构建输入参数列表
input_params=()
for f in "$@"
do
    # 检查文件是否存在
    if [ ! -f "$f" ]; then
        echo "错误: 文件不存在 $f"
        exit 1
    fi
    # 添加-i参数和文件路径到数组
    input_params+=("-i" "$f")
done

# 检查是否提供了至少一个输入文件
if [ ${#input_params[@]} -eq 0 ]; then
    echo "错误: 未提供输入文件"
    exit 1
fi

# 执行yamdi命令 找到yamdi命令进行执行即可
~/MyShell/flvbind/yamdi "${input_params[@]}" -o "$output_file"

# 检查命令执行结果
if [ $? -eq 0 ]; then
    echo "成功生成文件: $output_file"
else
    echo "处理失败"
    exit 1
fi
```



需要把 `flvbind`  (https://github.com/bilibili/flvbind  make编译一下即可)放到一个指定目录下 ,我这里放到了 `~/MyShell`  所以能够执行成功 直接安装自动操作的话就更完美了 直接选取文件然后触发快速操作即可

