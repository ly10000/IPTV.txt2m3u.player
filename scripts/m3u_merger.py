import re
import argparse
import sys
import os

# --- 辅助函数：提取 Group-Title ---
def extract_group_title(info_line):
    """从 #EXTINF 行中提取 group-title 的值。"""
    # 匹配 group-title="...任何非引号内容..."
    match = re.search(r'group-title="([^"]*)"', info_line)
    if match:
        return match.group(1).strip()
    return "" # 如果没有 group-title 属性，返回空字符串

# --- 辅助函数：解析单个 M3U 内容 (返回 order_list, channels_map, header) ---
def parse_single_m3u(m3u_content):
    if not m3u_content:
        return [], {}, ""
        
    lines = [line.strip() for line in m3u_content.strip().split('\n') if line.strip()]
    
    # channels_map 结构: { "频道名称": {"info": "#EXTINF...", "urls": set(), "group": "..."} }
    channels_map = {}
    order_list = []
    header = ""
    
    current_info_line = None
    current_channel_name = None
    
    for line in lines:
        if line.startswith('#EXTM3U'):
            if not header:
                header = line
            continue

        if line.startswith('#EXTINF:'):
            current_info_line = line
            
            # 提取频道名称 (以逗号后的内容为准)
            name_match = re.search(r',(.+)$', line)
            current_channel_name = name_match.group(1).strip() if name_match else None
            
            # 提取 Group-Title
            group_title = extract_group_title(current_info_line)
            
            if current_channel_name:
                if current_channel_name not in channels_map:
                    channels_map[current_channel_name] = {
                        "info": current_info_line, 
                        "urls": set(),
                        "group": group_title # 存储分组信息
                    }
                    order_list.append(current_channel_name)
                else:
                    # 频道已存在，更新信息（使用最新文件中的 EXTINF 行）
                    channels_map[current_channel_name]["info"] = current_info_line
                    channels_map[current_channel_name]["group"] = group_title 
            
        elif (line.startswith('http://') or line.startswith('https://')):
            if current_channel_name and current_channel_name in channels_map:
                # 使用集合来自动去重 URL
                channels_map[current_channel_name]["urls"].add(line)
        
        else:
            # 重置，避免无关的行被视为 URL
            current_channel_name = None

    return order_list, channels_map, header

# --- 主函数：实现 Group-Title 排序的合并逻辑 ---
def main():
    parser = argparse.ArgumentParser(
        description="合并多个M3U文件的内容，对同名频道下的所有URL进行去重和分组，并**确保 Group-Title 块的连续性**。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-i', '--input', type=str, nargs='+', required=True, help="一个或多个输入M3U文件的路径")
    parser.add_argument('-o', '--output', type=str, required=True, help="输出M3U文件的路径")
    args = parser.parse_args()
    
    if not args.input:
        print("错误: 请提供至少一个输入文件。", file=sys.stderr)
        sys.exit(1)
        
    final_channels_map = {}
    final_order_list = [] # 用于记录频道首次被发现的相对顺序（作为组内排序的基准）
    final_header = ""
    
    # 1. 处理所有输入文件并合并数据
    for input_file in args.input:
        if not os.path.exists(input_file):
            print(f"警告: 输入文件 '{input_file}' 不存在。跳过。", file=sys.stderr)
            continue
        if input_file == args.output:
            print(f"警告: 输入文件 '{input_file}' 和输出文件不能是同一个文件。跳过。", file=sys.stderr)
            continue
            
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            current_order_list, current_map, header = parse_single_m3u(content)
            
            if not final_header and header:
                final_header = header
                
            # --- 核心合并逻辑 ---
            for channel_name in current_order_list:
                current_channel_data = current_map[channel_name]
                group = current_channel_data["group"]
                
                if channel_name in final_channels_map:
                    # 频道已存在: 仅合并 URL 和更新属性
                    final_channels_map[channel_name]["info"] = current_channel_data["info"]
                    final_channels_map[channel_name]["group"] = group # 更新分组信息
                    final_channels_map[channel_name]["urls"].update(current_channel_data["urls"])
                    
                else:
                    # 频道是新的: 直接添加到 map 和 order_list 末尾
                    final_channels_map[channel_name] = current_channel_data
                    final_order_list.append(channel_name) # 追加，不进行即时插入排序
                    
        except Exception as e:
            print(f"处理文件 '{input_file}' 时发生错误: {e}", file=sys.stderr)
            sys.exit(1)

    # 2. 排序最终结果：按照 Group-Title 块和组内原始顺序进行排序
    
    # 2.1. 确定分组的顺序 (Group Sort Key) - 基于 final_order_list 中 Group 的首次出现顺序
    group_order_keys = {}
    next_group_key = 0
    
    # 遍历 final_order_list 来建立分组的顺序基准
    for name in final_order_list:
        if name in final_channels_map:
            group = final_channels_map[name]["group"]
            if group not in group_order_keys:
                group_order_keys[group] = next_group_key
                next_group_key += 1
    
    # 2.2. 创建排序列表
    # 排序元素: (组顺序键, 频道在 final_order_list 中的原始索引, 频道名称)
    sortable_list = []
    
    for i, name in enumerate(final_order_list):
        if name in final_channels_map:
            group = final_channels_map[name]["group"]
            # 新分组（不在 File 1 中）将使用 next_group_key，排在所有已知分组的最后
            group_key = group_order_keys.get(group, next_group_key) 
            
            # 使用索引 'i' 作为次要排序键，保持同一组内频道在文件中的原始相对顺序
            sortable_list.append((group_key, i, name)) 

    # 2.3. 执行排序
    # 按 Group Key 排序，其次按原始索引排序
    sortable_list.sort(key=lambda x: (x[0], x[1]))
    
    # 2.4. 生成新的最终顺序列表
    sorted_final_order_list = [item[2] for item in sortable_list]
    
    # 3. 写入最终结果
    output_lines = [final_header] if final_header else []
    
    for name in sorted_final_order_list:
        if name in final_channels_map:
            data = final_channels_map[name]
            output_lines.append(data["info"])
            # 排序 URL，保证输出稳定
            for url in sorted(list(data["urls"])):
                output_lines.append(url)
                
    modified_m3u = '\n'.join(output_lines)

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(modified_m3u)
            
        print(f"成功: {len(args.input)} 个 M3U 文件已合并、去重并按 Group-Title 排序，并写入到 '{args.output}'")
        
    except Exception as e:
        print(f"写入文件时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
