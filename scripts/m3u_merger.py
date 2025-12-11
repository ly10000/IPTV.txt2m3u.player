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
    
    # channels_map 现在将存储 group_title
    # { "频道名称": {"info": "#EXTINF...", "urls": set(), "group": "..."} }
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
            
            # 提取频道名称
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
                    channels_map[current_channel_name]["info"] = current_info_line
                    # 总是更新分组信息，以防不同文件中的分组名不同
                    channels_map[current_channel_name]["group"] = group_title 
            
        elif (line.startswith('http://') or line.startswith('https://')):
            if current_channel_name and current_channel_name in channels_map:
                channels_map[current_channel_name]["urls"].add(line)
        
        else:
             current_channel_name = None

    return order_list, channels_map, header

# --- 主函数：处理文件 I/O 和高级合并逻辑 ---
def main():
    parser = argparse.ArgumentParser(
        description="合并多个M3U文件的内容，对同名频道下的所有URL进行去重和分组，并按 Group-Title 保持频道连续性。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # ... (参数解析部分不变) ...
    parser.add_argument('-i', '--input', type=str, nargs='+', required=True, help="一个或多个输入M3U文件的路径")
    parser.add_argument('-o', '--output', type=str, required=True, help="输出M3U文件的路径")
    args = parser.parse_args()
    
    if not args.input:
        print("错误: 请提供至少一个输入文件。", file=sys.stderr)
        sys.exit(1)
        
    final_channels_map = {}
    final_order_list = []
    final_header = ""
    
    # 辅助字典：存储每个分组最后出现在 final_order_list 中的索引
    # { "group-title": index }
    group_last_index = {} 
    
    # 1. 处理第一个文件 (作为基础顺序)
    try:
        input_file_1 = args.input[0]
        if not os.path.exists(input_file_1):
            raise FileNotFoundError(f"文件不存在: {input_file_1}")
            
        with open(input_file_1, 'r', encoding='utf-8') as f:
            content_1 = f.read()
            
        temp_order_list, temp_map, header = parse_single_m3u(content_1)
        
        final_header = header
        final_order_list.extend(temp_order_list)
        final_channels_map.update(temp_map)
        
        # 初始化 group_last_index
        for i, name in enumerate(final_order_list):
            group = final_channels_map[name]["group"]
            group_last_index[group] = i
        
    except Exception as e:
        print(f"处理第一个文件 '{input_file_1}' 时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 依次处理后续文件 (进行高级合并)
    for input_file in args.input[1:]:
        # ... (文件检查部分不变) ...
        if not os.path.exists(input_file):
             print(f"警告: 输入文件 '{input_file}' 不存在。跳过。", file=sys.stderr)
             continue
        if input_file == args.output:
            print(f"警告: 输入文件 '{input_file}' 和输出文件不能是同一个文件。跳过。", file=sys.stderr)
            continue
            
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content_n = f.read()
                
            current_order_list, current_map, _ = parse_single_m3u(content_n) 
            
            # --- 核心修改：基于 Group-Title 的插入逻辑 ---
            for channel_name in current_order_list:
                current_channel_data = current_map[channel_name]
                group = current_channel_data["group"]
                
                if channel_name in final_channels_map:
                    # A. 频道已存在: 仅合并 URL 和更新属性
                    final_channels_map[channel_name]["info"] = current_channel_data["info"]
                    final_channels_map[channel_name]["group"] = group # 更新分组信息
                    final_channels_map[channel_name]["urls"].update(current_channel_data["urls"])
                    
                    # 更新该分组的最新位置 (防止其他组的频道被插入到这个组的中间)
                    try:
                        group_last_index[group] = final_order_list.index(channel_name)
                    except ValueError:
                         pass # 理论上不会发生

                else:
                    # B. 频道是新的: 寻找正确的分组插入点
                    
                    # 1. 确定插入位置
                    if group in group_last_index:
                        # 插入到该分组中最后一个频道之后
                        insert_index = group_last_index[group] + 1
                    else:
                        # 如果分组是全新的，则插入到 final_order_list 的末尾
                        insert_index = len(final_order_list)
                    
                    # 2. 将新频道添加到最终 map
                    final_channels_map[channel_name] = current_channel_data
                    
                    # 3. 插入到 order_list 中
                    final_order_list.insert(insert_index, channel_name)
                    
                    # 4. 更新该分组的最新位置到新插入的频道位置
                    group_last_index[group] = insert_index

        except Exception as e:
            print(f"处理文件 '{input_file}' 时发生错误: {e}", file=sys.stderr)
            sys.exit(1)

    # 3. 写入最终结果 (保持不变)
    output_lines = [final_header] if final_header else []
    
    for name in final_order_list:
        if name in final_channels_map:
            data = final_channels_map[name]
            output_lines.append(data["info"])
            for url in sorted(list(data["urls"])):
                output_lines.append(url)
                
    modified_m3u = '\n'.join(output_lines)

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(modified_m3u)
            
        print(f"成功: {len(args.input)} 个 M3U 文件已合并，并写入到 '{args.output}'")
        
    except Exception as e:
        print(f"写入文件时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
