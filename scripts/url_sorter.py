import argparse
import sys

def sort_m3u_urls(input_file, output_file, keywords_str):
    # 将输入的逗号分隔关键字转为列表并去除空格
    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: 找不到文件 '{input_file}'")
        return

    processed_content = []
    # 检查并保留 M3U 文件头
    start_index = 0
    if lines and lines[0].startswith('#EXTM3U'):
        processed_content.append(lines[0].strip())
        start_index = 1

    channels = []
    current_inf = None
    current_urls = []

    # 解析 M3U 结构
    for line in lines[start_index:]:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('#EXTINF'):
            if current_inf:
                channels.append({"inf": current_inf, "urls": current_urls})
            current_inf = line
            current_urls = []
        else:
            current_urls.append(line)
    
    # 存入最后一个频道
    if current_inf:
        channels.append({"inf": current_inf, "urls": current_urls})

    # 定义排序权重函数
    def get_sort_score(url):
        for index, kw in enumerate(keywords):
            if kw in url:
                return index
        return len(keywords)  # 未命中关键字的 URL 分数相同，保持原始顺序

    # 写入结果
    with open(output_file, 'w', encoding='utf-8') as f:
        if processed_content:
            f.write(processed_content[0] + '\n')
        
        for ch in channels:
            f.write(ch["inf"] + '\n')
            # 稳定排序：分数相同（即都不含关键字）时，保留原顺序
            sorted_urls = sorted(ch["urls"], key=get_sort_score)
            for url in sorted_urls:
                f.write(url + '\n')

def main():
    parser = argparse.ArgumentParser(description="根据关键字对 M3U 播放列表中的 URL 进行排序")
    
    # 添加命令行参数
    parser.add_argument("-i", "--input", required=True, help="输入的 M3U 文件路径")
    parser.add_argument("-o", "--output", default="sorted_output.m3u", help="输出的 M3U 文件路径 (默认: sorted_output.m3u)")
    parser.add_argument("-k", "--keywords", required=True, help="排序关键字，用逗号分隔，如 'HD,666,auth'")

    args = parser.parse_args()

    sort_m3u_urls(args.input, args.output, args.keywords)
    print(f"成功！处理完成。")
    print(f"输入: {args.input}")
    print(f"输出: {args.output}")
    print(f"关键字优先级: {args.keywords}")

if __name__ == "__main__":
    main()
