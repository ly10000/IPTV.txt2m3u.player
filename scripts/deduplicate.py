import argparse
import os
import tempfile
import shutil

def deduplicate_m3u(filepath):
    """
    对M3U文件进行去重处理（基于频道名称）
    兼容多个URL
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    seen = set()
    deduped = []
    
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            extinf_line = lines[i]
            channel_name = extinf_line.split(',', 1)[1] if ',' in extinf_line else ""
            
            if channel_name not in seen:
                seen.add(channel_name)
                deduped.append(extinf_line)
                
                # 添加直到下一个EXTINF或文件结束的所有行
                i += 1
                while i < len(lines) and not lines[i].startswith("#EXTINF"):
                    deduped.append(lines[i])
                    i += 1
                deduped.append("")  # 空行分隔
            else:
                # 跳过重复频道
                i += 1
                while i < len(lines) and not lines[i].startswith("#EXTINF"):
                    i += 1
        else:
            # 保留文件头部和其他注释
            deduped.append(lines[i])
            deduped.append("")
            i += 1
    
    return deduped

def safe_write_output(data, input_path, output_path, add_header=True):
    """
    安全地写入输出文件，支持同文件覆盖
    
    :param data: 要写入的数据列表
    :param input_path: 输入文件路径
    :param output_path: 输出文件路径
    :param add_header: 是否添加#EXTM3U头部
    :return: 成功返回True，失败返回False
    """
    # 获取绝对路径以判断是否为同一个文件
    input_abs = os.path.abspath(input_path)
    output_abs = os.path.abspath(output_path)
    is_same_file = input_abs == output_abs
    
    try:
        # 如果是同一个文件，先写到临时文件
        if is_same_file:
            # 在与输出文件相同目录创建临时文件
            fd, temp_path = tempfile.mkstemp(
                dir=os.path.dirname(output_path) or '.',
                suffix='.m3u',
                text=True
            )
            
            # 使用文件描述符打开文件
            out_f = os.fdopen(fd, 'w', encoding='utf-8')
        else:
            # 直接打开输出文件
            out_f = open(output_path, 'w', encoding='utf-8')
        
        # 写入数据
        with out_f:
            if add_header:
                out_f.write("#EXTM3U\n")
            
            for line in data:
                if line == "":  # 处理空行
                    out_f.write('\n')
                else:
                    out_f.write(line + '\n')
        
        # 如果是同一个文件，进行原子替换
        if is_same_file:
            try:
                # Python 3.3+ 推荐使用 os.replace 实现原子替换
                os.replace(temp_path, output_path)
                print(f"注意：输入和输出为同一文件，已安全覆盖")
            except Exception as e:
                # 如果 os.replace 失败，使用 shutil.move 作为备选
                print(f"警告：os.replace 失败，使用备选方案: {e}")
                shutil.move(temp_path, output_path)
        
        return True
        
    except Exception as e:
        print(f"写入文件失败: {e}")
        
        # 清理临时文件（如果存在）
        if is_same_file and 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
                
        return False

def parse_arguments():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(
        description='M3U文件去重工具 - 安全处理同文件覆盖',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='输入M3U文件路径',
        metavar='FILE'
    )
    parser.add_argument(
        '-o', '--output',
        default='output.m3u',
        help='输出M3U文件路径',
        metavar='FILE'
    )
    parser.add_argument(
        '--no-extm3u',
        action='store_false',
        dest='add_header',
        help='不在输出文件中添加#EXTM3U头'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制覆盖输出文件（如果已存在且与输入不同）'
    )
    
    return parser.parse_args()

def validate_arguments(args):
    """
    验证命令行参数的合理性
    """
    # 检查输入文件是否存在
    if not os.path.exists(args.input):
        print(f"错误：输入文件 '{args.input}' 不存在")
        return False
    
    # 检查输入文件是否可读
    if not os.access(args.input, os.R_OK):
        print(f"错误：输入文件 '{args.input}' 不可读")
        return False
    
    # 检查是否为文件
    if not os.path.isfile(args.input):
        print(f"错误：'{args.input}' 不是文件")
        return False
    
    # 检查输入文件扩展名（可选警告）
    if not args.input.lower().endswith('.m3u'):
        print(f"警告：输入文件 '{args.input}' 可能不是标准M3U文件")
    
    # 检查输出文件是否已存在且与输入不同
    input_abs = os.path.abspath(args.input)
    output_abs = os.path.abspath(args.output)
    
    if os.path.exists(args.output) and input_abs != output_abs:
        if not args.force:
            print(f"警告：输出文件 '{args.output}' 已存在")
            print("使用 --force 参数强制覆盖，或指定不同的输出文件")
            return False
    
    # 检查输出目录是否可写
    output_dir = os.path.dirname(output_abs) or '.'
    if not os.access(output_dir, os.W_OK):
        print(f"错误：输出目录 '{output_dir}' 不可写")
        return False
    
    return True

if __name__ == "__main__":
    args = parse_arguments()
    
    # 验证参数
    if not validate_arguments(args):
        exit(1)
    
    # 执行去重
    try:
        unique_entries = deduplicate_m3u(args.input)
        
        # 计算频道数量（仅统计EXTINF行）
        channel_count = sum(1 for line in unique_entries if line.startswith("#EXTINF"))
        
        # 安全写入输出文件
        success = safe_write_output(unique_entries, args.input, args.output, args.add_header)
        
        if success:
            print(f"已处理: {args.input}")
            print(f"去重后: {channel_count} 个频道")
            print(f"输出到: {args.output}")
        else:
            print("处理失败！")
            exit(1)
            
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        exit(1)
