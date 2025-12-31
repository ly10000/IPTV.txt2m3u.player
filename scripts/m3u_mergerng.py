import re
import argparse
import sys
import os
#忽略频道组 临时使用

# --- 辅助函数：提取 Group-Title ---
def extract_group_title(info_line):
    match = re.search(r'group-title="([^"]*)"', info_line)
    if match:
        return match.group(1).strip()
    return "未分类"

# --- 辅助函数：频道名归一化（用于合并逻辑） ---
def normalize_channel_name(name):
    """
    处理逻辑：去掉'-'，去掉后缀'台'，转大写。
    用于判断两个名字在逻辑上是否为同一个。
    """
    if not name:
        return ""
    temp = name.replace('-', '') # 去掉横杠
    if temp.endswith('台'):      # 去掉后缀“台”
        temp = temp[:-1]
    return temp.strip().upper()

# --- 辅助函数：判断是否为“更优”的显示名称 ---
def is_preferred_name(name):
    """如果名字包含 '-' 或以 '台' 结尾，则认为其是显示效果更佳的名字"""
    if not name:
        return False
    return '-' in name or name.endswith('台')

# --- 辅助函数：解析单个 M3U 内容 ---
def parse_single_m3u(m3u_content):
    if not m3u_content:
        return [], {}, ""
        
    lines = [line.strip() for line in m3u_content.strip().split('\n') if line.strip()]
    
    # channels_map 结构: { "归一化键": {"raw_name": "原始名", "info": "...", "urls": set(), "group": "..."} }
    channels_map = {}
    order_list = [] # 存储归一化后的键
    header = ""
    
    current_info_line = None
    current_channel_name = None
    
    for line in lines:
        if line.startswith('#EXTM3U'):
            if not header: header = line
            continue

        if line.startswith('#EXTINF:'):
            current_info_line = line
            name_match = re.search(r',([^,]+)$', line)
            current_channel_name = name_match.group(1).strip() if name_match else None
            
            if current_channel_name:
                norm_key = normalize_channel_name(current_channel_name)
                group_title = extract_group_title(current_info_line)
                
                if norm_key not in channels_map:
                    channels_map[norm_key] = {
                        "raw_name": current_channel_name,
                        "info": current_info_line, 
                        "urls": set(),
                        "group": group_title
                    }
                    order_list.append(norm_key)
                else:
                    # 核心逻辑：判断是否需要更新显示名称
                    existing_data = channels_map[norm_key]
                    existing_name = existing_data["raw_name"]
                    
                    # 只有当新名字更符合“包含 - 或 台”的特征，或者当前还没这种特征时更新
                    if is_preferred_name(current_channel_name) or not is_preferred_name(existing_name):
                        channels_map[norm_key]["info"] = current_info_line
                        channels_map[norm_key]["raw_name"] = current_channel_name
                        channels_map[norm_key]["group"] = group_title
            
        elif (line.startswith('http://') or line.startswith('https://')):
            if current_channel_name:
                norm_key = normalize_channel_name(current_channel_name)
                if norm_key in channels_map:
                    channels_map[norm_key]["urls"].add(line)
        
        else:
            current_channel_name = None

    return order_list, channels_map, header

# --- 主函数 ---
def main():
    parser = argparse.ArgumentParser(description="M3U合并脚本：模糊匹配横杠与'台'字，合并URL并保持相对顺序。")
    parser.add_argument('-i', '--input', type=str, nargs='+', required=True, help="输入M3U文件")
    parser.add_argument('-o', '--output', type=str, required=True, help="输出M3U文件")
    args = parser.parse_args()
    
    final_channels_map = {} # Key 为归一化名
    group_global_order = []
    group_channels_order = {}
    final_header = ""
    
    for input_file in args.input:
        if not os.path.exists(input_file): continue
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        curr_order, curr_map, header = parse_single_m3u(content)
        if not final_header: final_header = header
        
        for norm_key in curr_order:
            item = curr_map[norm_key]
            new_group = item["group"]
            
            # 1. 更新全局数据
            if norm_key not in final_channels_map:
                final_channels_map[norm_key] = item
            else:
                final_channels_map[norm_key]["urls"].update(item["urls"])
                # 检查显示名称优先级：如果新发现的名字带有特征，覆盖旧的显示属性
                if is_preferred_name(item["raw_name"]) and not is_preferred_name(final_channels_map[norm_key]["raw_name"]):
                    final_channels_map[norm_key]["info"] = item["info"]
                    final_channels_map[norm_key]["raw_name"] = item["raw_name"]
                
                # 更新组信息
                old_group = final_channels_map[norm_key]["group"]
                if old_group != new_group:
                    if old_group in group_channels_order and norm_key in group_channels_order[old_group]:
                        group_channels_order[old_group].remove(norm_key)
                    final_channels_map[norm_key]["group"] = new_group

            # 2. 维护组顺序
            if new_group not in group_global_order:
                group_global_order.append(new_group)
                group_channels_order[new_group] = []
        
        # 3. 相对插入排序
        for g in group_global_order:
            target_list = group_channels_order[g]
            file_names_in_group = [k for k in curr_order if curr_map[k]["group"] == g]
            
            last_known_idx = -1
            for k in file_names_in_group:
                if k in target_list:
                    last_known_idx = target_list.index(k)
                else:
                    insert_at = last_known_idx + 1
                    target_list.insert(insert_at, k)
                    last_known_idx = insert_at

    # 4. 写入文件
    output_lines = [final_header] if final_header else ["#EXTM3U"]
    for group in group_global_order:
        for norm_key in group_channels_order.get(group, []):
            data = final_channels_map[norm_key]
            output_lines.append(data["info"])
            for url in sorted(list(data["urls"])):
                output_lines.append(url)
                
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    print(f"合并完成！归一化处理已生效。")

if __name__ == "__main__":
    main()
