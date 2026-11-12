import os
import json
import glob
import shutil

def check_empty_json_files(base_path, backup_first=True, actually_delete=False):
    """
    检查并可选择删除指定路径下内容为空数组 [] 的JSON文件
    
    参数:
    base_path - 要检查的目录
    backup_first - 是否先创建备份
    actually_delete - 是否实际删除文件，False则只打印不删除
    """
    # 创建备份
    # if backup_first:
    #     backup_dir = base_path + "_backup"
    #     print(f"创建备份到 {backup_dir}")
    #     if os.path.exists(backup_dir):
    #         print(f"备份目录已存在，跳过备份")
    #     else:
    #         shutil.copytree(base_path, backup_dir)
    #         print("备份完成")
    
    # 获取所有JSON文件
    json_files = glob.glob(os.path.join(base_path, "**/*.json"), recursive=True)
    
    print(f"找到 {len(json_files)} 个 JSON 文件需要检查")
    
    empty_files = []
    error_files = []
    
    # 先检查，不删除
    for file_path in json_files:
        try:
            # 读取JSON文件
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # 检查是否为空数组 []
            if isinstance(data, list) and len(data) == 0:
                empty_files.append(file_path)
                
        except Exception as e:
            error_msg = f"处理文件 {file_path} 时出错: {e}"
            print(error_msg)
            error_files.append((file_path, str(e)))
    
    print(f"\n检查完成:")
    print(f"- 总计: {len(json_files)} 个文件")
    print(f"- 空文件: {len(empty_files)} 个文件 ({len(empty_files)/len(json_files)*100:.2f}%)")
    print(f"- 处理失败: {len(error_files)} 个文件")
    
    # 如果空文件比例超过50%，请求确认
    if len(empty_files) > len(json_files) * 0.5:
        print("\n警告: 超过50%的文件将被删除!")
        if actually_delete:
            confirm = input("是否继续删除? (y/n): ")
            if confirm.lower() != 'y':
                print("操作已取消")
                return
    
    # 执行删除
    deleted_count = 0
    if actually_delete:
        for file_path in empty_files:
            try:
                os.remove(file_path)
                deleted_count += 1
                
                # 每删除100个文件打印一次进度
                if deleted_count % 100 == 0:
                    print(f"已删除 {deleted_count} 个空文件...")
            except Exception as e:
                print(f"删除文件 {file_path} 时出错: {e}")
        
        print(f"\n删除完成: 已删除 {deleted_count} 个空文件")
    else:
        print("\n仅检查模式，未执行实际删除。如需删除，请设置 actually_delete=True")
        # 打印前10个空文件路径作为示例
        if empty_files:
            print("\n空文件示例 (前10个):")
            for i, file_path in enumerate(empty_files[:10]):
                print(f"{i+1}. {file_path}")

if __name__ == "__main__":
    base_path = "/ssd1/zhen/tablellm/test_results"
    
    # 默认只检查不删除，如需删除请设置actually_delete=True
    check_empty_json_files(base_path, backup_first=True, actually_delete=True)