import argparse
import sys
import re

def sort_m3u_urls(input_file, output_file, keywords_str, reverse_mode=False, target_channels_str=None, new_name=None):
    # 1. 参数解析与标准化
    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
    target_channels = [c.strip() for c in target_channels_str.split(',') if c.strip()] if target_channels_str else None
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error: 无法读取输入文件: {e}")
        return

    # 2. 结构化解析
    processed_content = []
    start_index = 0
    # 兼容处理首行（BOM 或 空格）
    if lines and '#EXTM3U' in lines[0]:
        processed_content.append(lines[0].strip())
        start_index = 1

    channels_data = []
    current_inf = None
    current_urls = []

    for line in lines[start_index:]:
        line = line.strip()
        if not line: continue
        if line.startswith('#EXTINF'):
            if current_inf:
                channels_data.append({"inf": current_inf, "urls": current_urls})
            current_inf = line
            current_urls = []
        else:
            current_urls.append(line)
    
    # 存入最后一个频道组
    if current_inf:
        channels_data.append({"inf": current_inf, "urls": current_urls})

    # 排序得分函数
    def get_sort_score(item):
        if "://" not in item: return 9999 # 非 URL 行保持在末尾
        for index, kw in enumerate(keywords):
            if kw in item:
                # 标准模式：关键字越靠前分数越低（负数）
                # 反向模式：关键字越靠前分数越高（正数）
                return (index + 1) if reverse_mode else (index - len(keywords))
        return 0 # 未匹配项分为 0

    # 重命名函数
    def rename_inf(inf_line, name):
        # 同步更新 tvg-name 属性
        if 'tvg-name="' in inf_line:
            inf_line = re.sub(r'tvg-name="[^"]*"', f'tvg-name="{name}"', inf_line)
        # 更新末尾显示名称
        if ',' in inf_line:
            parts = inf_line.rsplit(',', 1)
            return f"{parts[0]},{name}"
        return f"{inf_line},{name}"

    # 3. 执行复合逻辑并写入
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            if processed_content:
                f.write(processed_content[0] + '\n')
            
            for ch in channels_data:
                # 条件 A: 频道名匹配（命中 -ch）
                name_match = any(tc in ch["inf"] for tc in target_channels) if target_channels else False
                
                # 条件 B: 旗下 URL 匹配（命中 -k）
                url_match = any(any(kw in url for kw in keywords) for url in ch["urls"])
                
                # 只有 A 和 B 同时成立，才执行重命名
                final_inf = ch["inf"]
                if name_match and url_match and new_name:
                    final_inf = rename_inf(ch["inf"], new_name)
                
                f.write(final_inf + '\n')
                
                # 排序逻辑：如果指定了 -ch，则只对命中的频道排序；未指定则全局排
                should_sort = name_match if target_channels else True
                if should_sort:
                    # 稳定排序保证了未匹配项保持原始相对顺序
                    sorted_list = sorted(ch["urls"], key=get_sort_score)
                    for item in sorted_list:
                        f.write(item + '\n')
                else:
                    for item in ch["urls"]:
                        f.write(item + '\n')
                        
        print(f"✅ 处理成功！输出文件：{output_file}")
    except Exception as e:
        print(f"Error: 写入文件失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="M3U 复合条件重命名与 URL 排序加固工具")
    parser.add_argument("-i", "--input", required=True, help="输入文件路径")
    parser.add_argument("-o", "--output", default="sorted_output.m3u", help="输出文件路径")
    parser.add_argument("-k", "--keywords", required=True, help="排序关键字，逗号分隔 (大小写敏感)")
    parser.add_argument("-r", "--reverse", action="store_true", help="开启反向模式 (匹配项放最后)")
    parser.add_argument("-ch", "--channels", help="目标频道名关键字，逗号分隔")
    parser.add_argument("-rn", "--rename", help="重命名 (仅在满足 -ch 且包含 -k 时生效)")

    args = parser.parse_args()
    sort_m3u_urls(args.input, args.output, args.keywords, args.reverse, args.channels, args.rename)

if __name__ == "__main__":
    main()
