bl_info = {
    "name": "骨骼重命名工具",
    "author": "AI Assistant",
    "version": (2, 10),
    "blender": (4, 4, 3),
    "location": "View3D > Sidebar > 工具",
    "description": "将角色2的骨骼按角色1的命名规范重命名，支持骨骼名称映射库",
    "category": "骨骼",
}

import bpy
import re
import json
import urllib.request
import ast
import os
from difflib import SequenceMatcher
from bpy.app.handlers import persistent

# 全局配置
BONE_MAPPING_URL = "https://raw.githubusercontent.com/LgcChina/Text/refs/heads/main/%E9%AA%A8%E9%AA%BC.json"
CACHE_FILE = "bone_data.json"
bone_mapping_data = None
version_info = "未加载版本信息"
last_updated_info = ""
file_exists = False

@persistent
def load_handler(dummy):
    """Blender启动时检查本地文件"""
    global file_exists, version_info, last_updated_info, bone_mapping_data
    
    file_path = get_cache_path()
    file_exists = os.path.exists(file_path)
    
    if file_exists:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                bone_mapping_data = json.load(f)
            
            # 验证JSON结构
            if "bone_regions" in bone_mapping_data:
                version_info = bone_mapping_data.get("version", "未知版本")
                last_updated_info = bone_mapping_data.get("last_updated", "")
                print(f"骨骼映射库已加载: {version_info}, 更新日期: {last_updated_info}")
            else:
                version_info = "无效的映射库格式"
                last_updated_info = ""
                print("本地映射库缺少bone_regions字段")
        except Exception as e:
            version_info = f"加载错误: {str(e)}"
            last_updated_info = ""
            print(f"加载本地映射库失败: {str(e)}")
    else:
        version_info = "本地无数据文件，请下载"
        last_updated_info = ""
        print("未找到本地骨骼映射库文件")

def get_cache_path():
    """获取缓存文件完整路径"""
    config_dir = bpy.utils.user_resource('CONFIG')
    return os.path.join(config_dir, CACHE_FILE)

def download_mapping():
    """下载映射库数据并保存到本地"""
    global file_exists, version_info, last_updated_info, bone_mapping_data
    
    try:
        # 下载数据
        with urllib.request.urlopen(BONE_MAPPING_URL) as response:
            data = response.read().decode('utf-8')
        
        # 解析并验证JSON
        try:
            bone_mapping_data = json.loads(data)
        except json.JSONDecodeError as e:
            # 如果标准JSON解析失败，尝试使用ast.literal_eval
            try:
                bone_mapping_data = ast.literal_eval(data)
            except:
                raise e
        
        # 验证JSON结构
        if "bone_regions" not in bone_mapping_data:
            return False, "无效的骨骼映射库格式: 缺少bone_regions字段"
        
        # 保存到配置目录
        file_path = get_cache_path()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(bone_mapping_data, f, ensure_ascii=False, indent=2)
        
        # 更新全局状态
        file_exists = True
        version_info = bone_mapping_data.get("version", "未知版本")
        last_updated_info = bone_mapping_data.get("last_updated", "")
        
        return True, "下载成功！"
    except urllib.error.URLError:
        return False, "网络错误：无法访问链接"
    except Exception as e:
        return False, f"下载失败: {str(e)}"

def reload_local_mapping():
    """从本地缓存文件重新加载映射库"""
    global bone_mapping_data, version_info, last_updated_info
    
    file_path = get_cache_path()
    
    if not os.path.exists(file_path):
        return False, "本地文件不存在"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            bone_mapping_data = json.load(f)
        
        # 验证JSON结构
        if "bone_regions" not in bone_mapping_data:
            return False, "无效的骨骼映射库格式: 缺少bone_regions字段"
        
        version_info = bone_mapping_data.get("version", "未知版本")
        last_updated_info = bone_mapping_data.get("last_updated", "")
        return True, "重新加载成功"
    except Exception as e:
        return False, f"加载失败: {str(e)}"

def get_bone_mapping():
    """获取当前骨骼映射库"""
    return bone_mapping_data

def extract_base_name_and_side(name):
    """提取骨骼名称的基础部分和侧别信息"""
    if not bone_mapping_data:
        return name, None
    
    # 获取侧别标识符
    side_ids = bone_mapping_data.get("side_identifiers", {})
    left_ids = side_ids.get("left", [])
    right_ids = side_ids.get("right", [])
    
    # 转换为小写以便比较
    lower_name = name.lower()
    
    # 初始化结果
    base_name = name
    side = None
    
    # 使用正则表达式确保精确匹配侧别标识
    # 先检查右侧标识
    for identifier in right_ids:
        # 使用单词边界确保完整匹配
        pattern = re.compile(r'(^|[\._\- ])' + re.escape(identifier) + r'([\._\- ]|$)', re.IGNORECASE)
        if pattern.search(name):
            # 移除侧别标识
            base_name = pattern.sub(r'\1\2', name).strip('._- ')
            side = 'RIGHT'
            break
            
    if side is None:
        for identifier in left_ids:
            pattern = re.compile(r'(^|[\._\- ])' + re.escape(identifier) + r'([\._\- ]|$)', re.IGNORECASE)
            if pattern.search(name):
                base_name = pattern.sub(r'\1\2', name).strip('._- ')
                side = 'LEFT'
                break
    
    # 如果未检测到侧别标识，尝试从名称末尾检测
    if side is None:
        # 检查名称末尾的侧别标识
        end_pattern = re.compile(r'[\._\- ]([lr])$', re.IGNORECASE)
        end_match = end_pattern.search(name)
        if end_match:
            side_char = end_match.group(1).lower()
            if side_char == 'l':
                side = 'LEFT'
            elif side_char == 'r':
                side = 'RIGHT'
            base_name = end_pattern.sub('', name).strip('._- ')
    
    # 移除数字后缀
    base_name = re.sub(r'[\d_\.\-]+$', '', base_name).strip('._- ')
    
    # 进一步清理基础名称
    base_name = re.sub(r'^[\._\- ]+|[\._\- ]+$', '', base_name)
    
    return base_name, side

def map_to_standard_name(bone_name):
    """将骨骼名称映射到标准名称"""
    base_name, side = extract_base_name_and_side(bone_name)
    
    if not bone_mapping_data:
        return base_name, side, "other"
    
    # 在映射库中查找匹配的标准名称
    bone_regions = bone_mapping_data.get("bone_regions", {})
    for region_name, region_data in bone_regions.items():
        for standard_name, variants in region_data.get("bones", {}).items():
            # 检查基础名称是否匹配任何变体
            if base_name.lower() in [v.lower() for v in variants]:
                return standard_name, side, region_name
            
            # 对于手指骨骼，检查是否包含标准名称
            if region_name == "fingers":
                if standard_name.lower() in base_name.lower():
                    return standard_name, side, region_name
    
    # 如果没有找到匹配，返回原始基础名称和侧别
    return base_name, side, "other"

def get_bone_category(standard_name):
    """获取骨骼的区域"""
    if not bone_mapping_data:
        return "other"
    
    bone_regions = bone_mapping_data.get("bone_regions", {})
    for region_name, region_data in bone_regions.items():
        if standard_name in region_data.get("bones", {}):
            return region_name
    return "other"

def find_best_match(target_name, source_names, include_fingers=False):
    """在源名称列表中查找与目标名称最匹配的名称"""
    # 将目标名称映射到标准名称和侧别
    target_standard, target_side, target_region = map_to_standard_name(target_name)
    
    # 如果不处理手指且目标骨骼是手指，直接返回
    if not include_fingers and target_region == "fingers":
        return None, 0
    
    # 首先尝试精确匹配
    for source_name in source_names:
        # 将源名称映射到标准名称和侧别
        source_standard, source_side, source_region = map_to_standard_name(source_name)
        
        # 确保左右侧匹配
        if target_side and source_side and target_side != source_side:
            continue  # 侧别不匹配，跳过
            
        # 如果标准名称和侧别都匹配，直接返回
        if target_standard == source_standard and target_side == source_side:
            return source_name, 1.0
    
    # 如果没有精确匹配，尝试相似度匹配
    best_match = None
    best_score = 0
    
    for source_name in source_names:
        # 将源名称映射到标准名称和侧别
        source_standard, source_side, source_region = map_to_standard_name(source_name)
        
        # 确保左右侧匹配
        if target_side and source_side and target_side != source_side:
            continue  # 侧别不匹配，跳过
            
        # 计算标准名称的相似度
        score = SequenceMatcher(None, target_standard.lower(), source_standard.lower()).ratio()
        
        # 如果侧别匹配，增加相似度权重
        if target_side == source_side:
            score = min(score * 1.2, 1.0)  # 增加20%的相似度，但不超过1.0
        
        if score > best_score and score > 0.8:  # 提高相似度阈值
            best_score = score
            best_match = source_name
    
    # 只有当相似度非常高时才返回匹配结果
    if best_score > 0.9:  # 非常高的相似度阈值
        return best_match, best_score
    
    return None, 0  # 没有找到合适的匹配

class BONE_RENAME_OT_download_mapping(bpy.types.Operator):
    """下载骨骼名称映射库"""
    bl_idname = "bone_rename.download_mapping"
    bl_label = "下载映射库"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        tool = scene.bone_rename_tool
        
        success, message = download_mapping()
        if success:
            self.report({'INFO'}, f"{message} 版本: {version_info}")
        else:
            self.report({'ERROR'}, message)
        
        # 更新UI显示
        tool.mapping_version = version_info
        tool.mapping_last_updated = last_updated_info
        
        return {'FINISHED'}

class BONE_RENAME_OT_reload_mapping(bpy.types.Operator):
    """重新加载本地映射库"""
    bl_idname = "bone_rename.reload_mapping"
    bl_label = "重新加载"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        tool = scene.bone_rename_tool
        
        success, message = reload_local_mapping()
        if success:
            self.report({'INFO'}, f"{message} 版本: {version_info}")
        else:
            self.report({'ERROR'}, message)
        
        # 更新UI显示
        tool.mapping_version = version_info
        tool.mapping_last_updated = last_updated_info
        
        return {'FINISHED'}

class BONE_RENAME_OT_load_local_mapping(bpy.types.Operator):
    """从本地文件加载骨骼名称映射库"""
    bl_idname = "bone_rename.load_local_mapping"
    bl_label = "加载本地映射库"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(
        subtype="FILE_PATH",
        description="选择骨骼映射库JSON文件"
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        global bone_mapping_data, version_info, last_updated_info
        
        scene = context.scene
        tool = scene.bone_rename_tool
        
        try:
            # 从本地文件读取JSON
            with open(self.filepath, 'r', encoding='utf-8') as file:
                data = file.read()
            
            # 解析JSON
            try:
                bone_mapping_data = json.loads(data)
            except json.JSONDecodeError as e:
                # 如果标准JSON解析失败，尝试使用ast.literal_eval
                try:
                    bone_mapping_data = ast.literal_eval(data)
                except:
                    raise e
            
            # 验证JSON结构
            if "bone_regions" not in bone_mapping_data:
                self.report({'ERROR'}, "无效的骨骼映射库格式: 缺少bone_regions字段")
                return {'CANCELLED'}
            
            # 更新全局状态
            version_info = bone_mapping_data.get("version", "未知版本")
            last_updated_info = bone_mapping_data.get("last_updated", "")
            
            # 保存到缓存文件
            cache_path = get_cache_path()
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(bone_mapping_data, f, ensure_ascii=False, indent=2)
            
            # 更新UI显示
            tool.mapping_version = version_info
            tool.mapping_last_updated = last_updated_info
            
            self.report({'INFO'}, f"骨骼映射库加载成功: 版本 {version_info}")
        except Exception as e:
            self.report({'ERROR'}, f"加载骨骼映射库失败: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class BONE_RENAME_OT_preview_rename(bpy.types.Operator):
    """预览骨骼重命名结果"""
    bl_idname = "bone_rename.preview_rename"
    bl_label = "预览重命名"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        tool = scene.bone_rename_tool
        
        if not tool.character1 or not tool.character2:
            self.report({'ERROR'}, "请先选择两个角色骨架")
            return {'CANCELLED'}
        
        if tool.character1.type != 'ARMATURE' or tool.character2.type != 'ARMATURE':
            self.report({'ERROR'}, "选择的对象必须是骨架")
            return {'CANCELLED'}
        
        # 检查是否有骨骼映射库
        if bone_mapping_data is None:
            self.report({'ERROR'}, "请先加载骨骼映射库")
            return {'CANCELLED'}
        
        # 获取骨骼名称列表
        char1_bones = [bone.name for bone in tool.character1.data.bones]
        char2_bones = [bone.name for bone in tool.character2.data.bones]
        
        # 清空之前的匹配结果
        tool.match_results.clear()
        
        # 创建重命名映射
        matched_count = 0
        
        for bone_name in char2_bones:
            # 将目标骨骼映射到标准名称和侧别
            standard_name, side, region = map_to_standard_name(bone_name)
            
            # 如果不处理手指且是手指骨骼，则跳过
            if not tool.rename_fingers and region == "fingers":
                continue  # 跳过这个骨骼，不进行匹配和重命名
            
            # 如果这个骨骼在映射库中有定义，则尝试匹配
            bone_regions = bone_mapping_data.get("bone_regions", {})
            bone_found = False
            
            for region_name, region_data in bone_regions.items():
                if standard_name in region_data.get("bones", {}):
                    bone_found = True
                    break
            
            # 只处理映射库中有定义的骨骼
            if bone_found:
                best_match, score = find_best_match(bone_name, char1_bones, tool.rename_fingers)
                
                if best_match:
                    # 添加匹配结果到列表
                    result = tool.match_results.add()
                    result.original_name = bone_name
                    result.matched_name = best_match
                    result.similarity = score
                    matched_count += 1
                else:
                    # 没有找到匹配的骨骼，保持原名
                    result = tool.match_results.add()
                    result.original_name = bone_name
                    result.matched_name = bone_name  # 保持原名
                    result.similarity = 0
        
        # 更新统计信息
        tool.matched_count = matched_count
        tool.has_preview = True
        
        self.report({'INFO'}, f"预览完成: {matched_count} 个骨骼将重命名")
        return {'FINISHED'}

class BONE_RENAME_OT_execute_rename(bpy.types.Operator):
    """执行骨骼重命名操作"""
    bl_idname = "bone_rename.execute_rename"
    bl_label = "执行重命名"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        tool = scene.bone_rename_tool
        
        if not tool.has_preview:
            self.report({'ERROR'}, "请先预览重命名结果")
            return {'CANCELLED'}
        
        if not tool.character2:
            self.report({'ERROR'}, "目标角色不存在")
            return {'CANCELLED'}
        
        # 执行重命名
        renamed_count = 0
        for result in tool.match_results:
            bone = tool.character2.data.bones.get(result.original_name)
            if bone and result.original_name != result.matched_name:  # 只有当名称不同时才重命名
                bone.name = result.matched_name
                renamed_count += 1
        
        # 重置预览状态
        tool.has_preview = False
        
        self.report({'INFO'}, f"重命名完成: {renamed_count} 个骨骼已重命名")
        return {'FINISHED'}

class BONE_RENAME_OT_clear_results(bpy.types.Operator):
    """清空匹配结果"""
    bl_idname = "bone_rename.clear_results"
    bl_label = "清空结果"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        tool = scene.bone_rename_tool
        
        tool.match_results.clear()
        tool.matched_count = 0
        tool.has_preview = False
        
        self.report({'INFO'}, "已清空匹配结果")
        return {'FINISHED'}

class BoneMatchResult(bpy.types.PropertyGroup):
    """单个骨骼匹配结果"""
    original_name: bpy.props.StringProperty(name="原始名称")
    matched_name: bpy.props.StringProperty(name="匹配名称")
    similarity: bpy.props.FloatProperty(name="相似度", precision=3)

class BONE_RENAME_PT_main_panel(bpy.types.Panel):
    """创建主面板"""
    bl_label = "骨骼重命名工具"
    bl_idname = "BONE_RENAME_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '工具'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        tool = scene.bone_rename_tool
        
        # 角色选择部分
        box = layout.box()
        box.label(text="角色选择:")
        box.prop(tool, "character1", text="角色1 (参考)")
        box.prop(tool, "character2", text="角色2 (目标)")
        
        # 骨骼映射库设置 - 可折叠区域
        mapping_box = layout.box()
        
        # 映射库标题行
        row = mapping_box.row()
        row.prop(tool, "show_mapping_details", 
                icon="TRIA_DOWN" if tool.show_mapping_details else "TRIA_RIGHT",
                emboss=False,
                text="骨骼名称映射库" + ("" if tool.show_mapping_details else f" ({version_info})"))
        
        # 如果用户选择展开或者没有缓存文件，显示详细内容
        if tool.show_mapping_details or not file_exists:
            # 映射库状态
            row = mapping_box.row()
            row.label(text="状态:", icon='FILE')
            row.label(text="已缓存" if file_exists else "未缓存", 
                     icon='CHECKMARK' if file_exists else 'ERROR')
            
            # 版本信息
            row = mapping_box.row()
            row.label(text="版本:", icon='SORTALPHA')
            row.label(text=version_info)
            
            # 更新日期信息
            if last_updated_info:
                row = mapping_box.row()
                row.label(text="更新日期:", icon='TIME')
                row.label(text=last_updated_info)
            
            # 操作按钮
            row = mapping_box.row(align=True)
            row.operator("bone_rename.download_mapping", text="下载映射库", icon='IMPORT')
            row.operator("bone_rename.reload_mapping", text="重新加载", icon='FILE_REFRESH')
            
            # 加载本地文件按钮
            mapping_box.operator("bone_rename.load_local_mapping", text="加载本地映射库", icon='FILE_FOLDER')
            
            # 文件路径
            if file_exists:
                cache_path = get_cache_path()
                mapping_box.label(text="本地文件路径:", icon='FILE_TICK')
                mapping_box.label(text=cache_path)
        else:
            # 简略显示 - 只显示版本和更新日期
            if last_updated_info:
                row = mapping_box.row()
                row.label(text=f"版本: {version_info} | 更新: {last_updated_info}", icon='INFO')
            else:
                row = mapping_box.row()
                row.label(text=f"版本: {version_info}", icon='INFO')
        
        # 选项设置
        options_box = layout.box()
        options_box.label(text="选项:")
        options_box.prop(tool, "rename_fingers", text="处理手指骨骼")
        
        # 操作按钮
        row = layout.row()
        row.operator("bone_rename.preview_rename", text="预览重命名")
        row.operator("bone_rename.clear_results", text="清空", icon='X')
        
        # 执行按钮（仅在预览后显示）
        if tool.has_preview:
            layout.operator("bone_rename.execute_rename", text="执行重命名", icon='CHECKMARK')
        
        # 结果显示部分
        if tool.match_results:
            result_box = layout.box()
            result_box.label(text=f"匹配结果: {tool.matched_count} 个骨骼将重命名")
            
            # 按类别分组显示骨骼
            self.draw_bones_by_category(result_box, tool)
    
    def draw_bones_by_category(self, layout, tool):
        """按区域分组显示骨骼，左右分列"""
        if bone_mapping_data is None:
            layout.label(text="骨骼映射库未加载", icon='ERROR')
            return
            
        # 获取所有区域
        bone_regions = bone_mapping_data.get("bone_regions", {})
        
        # 按区域分组骨骼
        categorized_bones = {region_name: [] for region_name in bone_regions.keys()}
        
        for result in tool.match_results:
            standard_name, _, region_name = map_to_standard_name(result.original_name)
            if region_name in categorized_bones:
                categorized_bones[region_name].append(result)
        
        # 显示每个区域的骨骼
        for region_name, region_data in bone_regions.items():
            if categorized_bones.get(region_name):
                region_box = layout.box()
                region_box.label(text=f"{region_data.get('name', region_name)}:", icon=self.get_region_icon(region_name))
                self.draw_side_by_side(region_box, categorized_bones[region_name])
    
    def get_region_icon(self, region_name):
        """获取区域的图标"""
        icon_map = {
            "core": 'ORIENTATION_LOCAL',
            "arms": 'VIEW_PAN',
            "legs": 'CON_FOLLOWPATH',
            "fingers": 'HAND'
        }
        return icon_map.get(region_name, 'QUESTION')
    
    def draw_side_by_side(self, layout, bones):
        """左右分列显示骨骼"""
        # 分离左侧和右侧骨骼
        left_bones = []
        right_bones = []
        center_bones = []  # 无侧别的骨骼
        
        for bone in bones:
            _, side, _ = map_to_standard_name(bone.original_name)
            if side == 'LEFT':
                left_bones.append(bone)
            elif side == 'RIGHT':
                right_bones.append(bone)
            else:
                center_bones.append(bone)
        
        # 创建左右分列布局
        split = layout.split(factor=0.5)
        col_left = split.column()
        col_right = split.column()
        
        # 显示左侧骨骼和无侧别骨骼
        for bone in left_bones + center_bones:
            row = col_left.row()
            if bone.original_name == bone.matched_name:
                row.label(text=f"{bone.original_name} (保持原名)", icon='BONE_DATA')
            else:
                row.label(text=f"{bone.original_name} → {bone.matched_name}", icon='BONE_DATA')
        
        # 显示右侧骨骼
        for bone in right_bones:
            row = col_right.row()
            if bone.original_name == bone.matched_name:
                row.label(text=f"{bone.original_name} (保持原名)", icon='BONE_DATA')
            else:
                row.label(text=f"{bone.original_name} → {bone.matched_name}", icon='BONE_DATA')

class BoneRenameProperties(bpy.types.PropertyGroup):
    """工具属性"""
    character1: bpy.props.PointerProperty(
        name="角色1",
        description="参考骨骼的角色",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    
    character2: bpy.props.PointerProperty(
        name="角色2",
        description="要重命名的角色",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    
    rename_fingers: bpy.props.BoolProperty(
        name="处理手指骨骼",
        description="是否处理手指骨骼",
        default=False
    )
    
    show_mapping_details: bpy.props.BoolProperty(
        name="显示映射库详情",
        description="显示或隐藏映射库详细设置",
        default=False
    )
    
    mapping_version: bpy.props.StringProperty(
        name="映射库版本",
        description="骨骼名称映射库版本",
        default=""
    )
    
    mapping_last_updated: bpy.props.StringProperty(
        name="映射库更新日期",
        description="骨骼名称映射库最后更新日期",
        default=""
    )
    
    match_results: bpy.props.CollectionProperty(
        type=BoneMatchResult
    )
    
    matched_count: bpy.props.IntProperty(
        name="匹配数量",
        default=0
    )
    
    has_preview: bpy.props.BoolProperty(
        name="有预览",
        default=False
    )

def register():
    bpy.utils.register_class(BoneMatchResult)
    bpy.utils.register_class(BoneRenameProperties)
    bpy.utils.register_class(BONE_RENAME_OT_download_mapping)
    bpy.utils.register_class(BONE_RENAME_OT_reload_mapping)
    bpy.utils.register_class(BONE_RENAME_OT_load_local_mapping)
    bpy.utils.register_class(BONE_RENAME_OT_preview_rename)
    bpy.utils.register_class(BONE_RENAME_OT_execute_rename)
    bpy.utils.register_class(BONE_RENAME_OT_clear_results)
    bpy.utils.register_class(BONE_RENAME_PT_main_panel)
    
    bpy.types.Scene.bone_rename_tool = bpy.props.PointerProperty(type=BoneRenameProperties)
    
    # 注册启动处理函数
    bpy.app.handlers.load_post.append(load_handler)
    
    # 初始化状态
    load_handler(None)

def unregister():
    bpy.utils.unregister_class(BoneMatchResult)
    bpy.utils.unregister_class(BoneRenameProperties)
    bpy.utils.unregister_class(BONE_RENAME_OT_download_mapping)
    bpy.utils.unregister_class(BONE_RENAME_OT_reload_mapping)
    bpy.utils.unregister_class(BONE_RENAME_OT_load_local_mapping)
    bpy.utils.unregister_class(BONE_RENAME_OT_preview_rename)
    bpy.utils.unregister_class(BONE_RENAME_OT_execute_rename)
    bpy.utils.unregister_class(BONE_RENAME_OT_clear_results)
    bpy.utils.unregister_class(BONE_RENAME_PT_main_panel)
    
    del bpy.types.Scene.bone_rename_tool
    
    # 移除启动处理函数
    bpy.app.handlers.load_post.remove(load_handler)

if __name__ == "__main__":
    register()
