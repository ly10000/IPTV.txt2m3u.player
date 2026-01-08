import os
import argparse
import tempfile
import shutil

def add_channels_to_m3u(input_file, output_file, channels_str, group_name, append_to_end):
    # 处理频道信息
    parts = [p.strip() for p in channels_str.split(',')]
    new_channels_block = ""
    for i in range(0, len(parts), 2):
        if i + 1 < len(parts):
            name = parts[i]
            url = parts[i+1]
            inf_line = f'#EXTINF:-1 tvg-name="{name}" group-title="{group_name}",{name}\n'
            new_channels_block += f"{inf_line}{url}\n"
    
    if not os.path.exists(input_file):
        print(f"错误：找不到输入文件 '{input_file}'")
        return

    # 获取绝对路径以判断是否为同一个文件
    is_same_file = os.path.abspath(input_file) == os.path.abspath(output_file)

    try:
        # 先读取原始数据
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 如果是同一个文件，先写到临时文件，防止数据截断丢失
        if is_same_file:
            fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(output_file), text=True)
            out_f = open(fd, 'w', encoding='utf-8')
        else:
            out_f = open(output_file, 'w', encoding='utf-8')

        with out_f:
            if append_to_end:
                out_f.writelines(lines)
                if lines and not lines[-1].endswith('\n'):
                    out_f.write('\n')
                out_f.write(new_channels_block)
            else:
                if lines and lines[0].strip().startswith("#EXTM3U"):
                    out_f.write(lines[0])
                    out_f.write(new_channels_block)
                    out_f.writelines(lines[1:])
                else:
                    out_f.write("#EXTM3U\n")
                    out_f.write(new_channels_block)
                    out_f.writelines(lines)

        # 如果使用了临时文件，最后进行替换
        if is_same_file:
            shutil.move(temp_path, output_file)
                
        print(f"成功！{'覆盖' if is_same_file else '生成'}了文件: {output_file}")

    except Exception as e:
        print(f"处理过程中发生错误: {e}")

def main():
    parser = argparse.ArgumentParser(description="安全地向 M3U 插入频道记录")
    parser.add_argument("-i", "--input", required=True, help="输入文件")
    parser.add_argument("-o", "--output", required=True, help="输出文件")
    parser.add_argument("-a", "--add", required=True, help='频道信息')
    parser.add_argument("-g", "--group", default="其它", help="分组名")
    parser.add_argument("-r", "--rear", action="store_true", help="添加到末尾")
    
    args = parser.parse_args()
    add_channels_to_m3u(args.input, args.output, args.add, args.group, args.rear)

if __name__ == "__main__":
    main()
