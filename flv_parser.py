import struct
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Any, Tuple, Optional

class FLVTag:
    """FLV标签类，用于存储和解析FLV文件中的标签信息"""
    
    # 标签类型常量
    AUDIO = 8
    VIDEO = 9
    SCRIPT = 18
    
    # 标签类型名称映射
    TAG_TYPES = {
        AUDIO: "Audio",
        VIDEO: "Video",
        SCRIPT: "Script Data"
    }
    
    # 音频格式映射
    AUDIO_FORMATS = {
        0: "Linear PCM, platform endian",
        1: "ADPCM",
        2: "MP3",
        3: "Linear PCM, little endian",
        4: "Nellymoser 16kHz mono",
        5: "Nellymoser 8kHz mono",
        6: "Nellymoser",
        7: "G.711 A-law logarithmic PCM",
        8: "G.711 mu-law logarithmic PCM",
        9: "reserved",
        10: "AAC",
        11: "Speex",
        14: "MP3 8kHz",
        15: "Device-specific sound"
    }
    
    # 音频采样率映射
    AUDIO_RATES = {
        0: "5.5kHz",
        1: "11kHz",
        2: "22kHz",
        3: "44kHz"
    }
    
    # 音频位深度映射
    AUDIO_BITS = {
        0: "8-bit",
        1: "16-bit"
    }
    
    # 音频通道映射
    AUDIO_CHANNELS = {
        0: "Mono",
        1: "Stereo"
    }
    
    # 视频帧类型映射
    VIDEO_FRAME_TYPES = {
        1: "Key frame",
        2: "Inter frame",
        3: "Disposable inter frame",
        4: "Generated key frame",
        5: "Video info/command frame"
    }
    
    # 视频编码映射
    VIDEO_CODECS = {
        1: "JPEG",
        2: "Sorenson H.263",
        3: "Screen video",
        4: "On2 VP6",
        5: "On2 VP6 with alpha channel",
        6: "Screen video version 2",
        7: "AVC (H.264)"
    }
    
    def __init__(self, offset: int, data: bytes):
        """初始化FLV标签
        
        Args:
            offset: 标签在文件中的偏移量
            data: 标签数据
        """
        self.offset = offset
        self.tag_type = data[0]
        self.data_size = (data[1] << 16) | (data[2] << 8) | data[3]
        self.timestamp = (data[4] << 16) | (data[5] << 8) | data[6] | (data[7] << 24)
        self.stream_id = (data[8] << 16) | (data[9] << 8) | data[10]
        self.data = data[11:11+self.data_size]
        self.total_size = 11 + self.data_size + 4  # 包括前置头部和后置的前一个标签大小
        
        # 解析特定类型的标签数据
        self.details = {}
        if self.tag_type == FLVTag.AUDIO:
            self._parse_audio_data()
        elif self.tag_type == FLVTag.VIDEO:
            self._parse_video_data()
        elif self.tag_type == FLVTag.SCRIPT:
            self._parse_script_data()
    
    def _parse_audio_data(self):
        """解析音频标签数据"""
        if not self.data:
            return
            
        flags = self.data[0]
        self.details["Format"] = FLVTag.AUDIO_FORMATS.get(flags >> 4, f"Unknown ({flags >> 4})")
        self.details["Sample Rate"] = FLVTag.AUDIO_RATES.get((flags >> 2) & 0x3, f"Unknown ({(flags >> 2) & 0x3})")
        self.details["Sample Size"] = FLVTag.AUDIO_BITS.get((flags >> 1) & 0x1, f"Unknown ({(flags >> 1) & 0x1})")
        self.details["Channels"] = FLVTag.AUDIO_CHANNELS.get(flags & 0x1, f"Unknown ({flags & 0x1})")
        
        # 对于AAC音频，解析AAC包类型
        if (flags >> 4) == 10:  # AAC
            if len(self.data) > 1:
                aac_packet_type = self.data[1]
                self.details["AAC Packet Type"] = "AAC sequence header" if aac_packet_type == 0 else "AAC raw"
    
    def _parse_video_data(self):
        """解析视频标签数据"""
        if not self.data:
            return
            
        flags = self.data[0]
        frame_type = (flags >> 4) & 0xF
        codec_id = flags & 0xF
        
        self.details["Frame Type"] = FLVTag.VIDEO_FRAME_TYPES.get(frame_type, f"Unknown ({frame_type})")
        self.details["Codec ID"] = FLVTag.VIDEO_CODECS.get(codec_id, f"Unknown ({codec_id})")
        
        # 对于H.264视频，解析AVC包类型
        if codec_id == 7:  # AVC (H.264)
            if len(self.data) > 1:
                avc_packet_type = self.data[1]
                if avc_packet_type == 0:
                    self.details["AVC Packet Type"] = "AVC sequence header"
                elif avc_packet_type == 1:
                    self.details["AVC Packet Type"] = "AVC NALU"
                elif avc_packet_type == 2:
                    self.details["AVC Packet Type"] = "AVC end of sequence"
                else:
                    self.details["AVC Packet Type"] = f"Unknown ({avc_packet_type})"
    
    def _parse_script_data(self):
        """解析脚本数据标签"""
        if not self.data:
            return
            
        # 简单解析AMF数据，只提取名称
        try:
            # 跳过AMF类型字节
            pos = 1
            # 读取字符串长度
            name_len = (self.data[pos] << 8) | self.data[pos+1]
            pos += 2
            # 读取名称
            if pos + name_len <= len(self.data):
                name = self.data[pos:pos+name_len].decode('utf-8', errors='replace')
                self.details["Name"] = name
                
                # 常见的脚本数据名称
                if name == "onMetaData":
                    self.details["Type"] = "Metadata"
        except Exception as e:
            self.details["Parse Error"] = str(e)
    
    def get_type_name(self) -> str:
        """获取标签类型名称"""
        return FLVTag.TAG_TYPES.get(self.tag_type, f"Unknown ({self.tag_type})")
    
    def get_display_info(self) -> Dict[str, Any]:
        """获取用于显示的标签信息"""
        return {
            "Offset": f"0x{self.offset:08X}",
            "Type": self.get_type_name(),
            "Size": self.data_size,
            "Timestamp": f"{self.timestamp} ms",
            "Details": self.details
        }


class FLVFile:
    """FLV文件解析类"""
    
    def __init__(self, file_path: str):
        """初始化FLV文件解析器
        
        Args:
            file_path: FLV文件路径
        """
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.header = {}
        self.tags = []
        self._parse()
    
    def _parse(self):
        """解析FLV文件"""
        with open(self.file_path, 'rb') as f:
            # 解析文件头
            header_data = f.read(9)
            if len(header_data) < 9:
                raise ValueError("Invalid FLV file: header too short")
                
            # 检查FLV签名
            if header_data[0:3] != b'FLV':
                raise ValueError("Invalid FLV file: signature mismatch")
                
            self.header["Version"] = header_data[3]
            flags = header_data[4]
            self.header["HasVideo"] = bool(flags & 0x1)
            self.header["HasAudio"] = bool(flags & 0x4)
            self.header["HeaderSize"] = struct.unpack(">I", header_data[5:9])[0]
            
            # 跳过前一个标签大小字段（通常为0）
            f.read(4)
            
            # 解析标签
            offset = 13  # 文件头(9) + 前一个标签大小(4)
            while True:
                # 读取标签头
                tag_header = f.read(11)
                if len(tag_header) < 11:
                    break  # 文件结束
                    
                # 读取标签数据大小
                data_size = (tag_header[1] << 16) | (tag_header[2] << 8) | tag_header[3]
                
                # 读取完整标签数据
                tag_data = tag_header + f.read(data_size)
                
                # 创建标签对象
                tag = FLVTag(offset, tag_data)
                self.tags.append(tag)
                
                # 跳过前一个标签大小字段
                f.read(4)
                
                # 更新偏移量
                offset += tag.total_size
    
    def get_header_info(self) -> Dict[str, Any]:
        """获取文件头信息"""
        return {
            "File": self.file_name,
            "Version": self.header.get("Version", "Unknown"),
            "Has Video": self.header.get("HasVideo", False),
            "Has Audio": self.header.get("HasAudio", False),
            "Header Size": self.header.get("HeaderSize", 0)
        }
    
    def get_tags(self) -> List[FLVTag]:
        """获取所有标签"""
        return self.tags
    
    def get_tag_count(self) -> Dict[str, int]:
        """获取各类型标签的数量统计"""
        counts = {"Total": len(self.tags)}
        type_counts = {}
        
        for tag in self.tags:
            tag_type = tag.get_type_name()
            type_counts[tag_type] = type_counts.get(tag_type, 0) + 1
            
        counts.update(type_counts)
        return counts


class FLVParserGUI:
    """FLV解析器GUI界面"""
    
    def __init__(self, root):
        """初始化GUI界面
        
        Args:
            root: tkinter根窗口
        """
        self.root = root
        self.root.title("FLV文件解析器")
        self.root.geometry("1000x700")
        
        self.flv_file = None
        self.search_results = []
        self.current_search_index = -1
        
        self._create_widgets()
        self._setup_layout()
    
    def _create_widgets(self):
        """创建GUI组件"""
        # 创建菜单栏
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # 文件菜单
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="打开FLV文件", command=self._open_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self.root.quit)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        
        # 帮助菜单
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label="关于", command=self._show_about)
        self.menu_bar.add_cascade(label="帮助", menu=self.help_menu)
        
        # 工具栏框架
        self.toolbar_frame = ttk.Frame(self.root)
        
        # 打开文件按钮
        self.open_button = ttk.Button(self.toolbar_frame, text="打开FLV文件", command=self._open_file)
        
        # 搜索框架
        self.search_frame = ttk.Frame(self.toolbar_frame)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var, width=30)
        self.search_entry.bind("<Return>", self._search)
        
        self.search_button = ttk.Button(self.search_frame, text="搜索", command=self._search)
        self.prev_button = ttk.Button(self.search_frame, text="上一个", command=self._prev_search_result)
        self.next_button = ttk.Button(self.search_frame, text="下一个", command=self._next_search_result)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("准备就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        
        # 主分隔窗口
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        
        # 左侧信息面板
        self.info_frame = ttk.Frame(self.main_paned)
        
        # 文件信息标签框架
        self.file_info_labelframe = ttk.LabelFrame(self.info_frame, text="文件信息")
        self.file_info_text = tk.Text(self.file_info_labelframe, wrap=tk.WORD, width=30, height=8, state=tk.DISABLED)
        
        # 标签统计标签框架
        self.tag_stats_labelframe = ttk.LabelFrame(self.info_frame, text="标签统计")
        self.tag_stats_text = tk.Text(self.tag_stats_labelframe, wrap=tk.WORD, width=30, height=10, state=tk.DISABLED)
        
        # 右侧标签树形视图
        self.tree_frame = ttk.Frame(self.main_paned)
        
        # 创建树形视图
        self.tree = ttk.Treeview(self.tree_frame, selectmode=tk.BROWSE)
        self.tree.heading("#0", text="FLV结构", anchor=tk.W)
        
        # 树形视图滚动条
        self.tree_scrollbar_y = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scrollbar_y.set)
        
        self.tree_scrollbar_x = ttk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscrollcommand=self.tree_scrollbar_x.set)
        
        # 标签详情面板
        self.details_labelframe = ttk.LabelFrame(self.root, text="标签详情")
        self.details_text = tk.Text(self.details_labelframe, wrap=tk.WORD, state=tk.DISABLED)
        self.details_scrollbar = ttk.Scrollbar(self.details_labelframe, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=self.details_scrollbar.set)
        
        # 绑定树形视图选择事件
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
    
    def _setup_layout(self):
        """设置组件布局"""
        # 工具栏布局
        self.toolbar_frame.pack(fill=tk.X, padx=5, pady=5)
        self.open_button.pack(side=tk.LEFT, padx=5)
        
        self.search_frame.pack(side=tk.RIGHT, padx=5)
        self.search_entry.pack(side=tk.LEFT, padx=2)
        self.search_button.pack(side=tk.LEFT, padx=2)
        self.prev_button.pack(side=tk.LEFT, padx=2)
        self.next_button.pack(side=tk.LEFT, padx=2)
        
        # 主分隔窗口布局
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧信息面板布局
        self.main_paned.add(self.info_frame, weight=1)
        
        self.file_info_labelframe.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.file_info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tag_stats_labelframe.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tag_stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 右侧树形视图布局
        self.main_paned.add(self.tree_frame, weight=3)
        
        self.tree_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 标签详情面板布局
        self.details_labelframe.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 状态栏布局
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _open_file(self):
        """打开FLV文件"""
        file_path = filedialog.askopenfilename(
            title="选择FLV文件",
            filetypes=[("FLV文件", "*.flv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            self.status_var.set(f"正在解析文件: {file_path}")
            self.root.update_idletasks()
            
            # 解析FLV文件
            self.flv_file = FLVFile(file_path)
            
            # 更新界面
            self._update_file_info()
            self._update_tag_stats()
            self._populate_tree()
            
            self.status_var.set(f"文件已加载: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"解析文件时出错: {str(e)}")
            self.status_var.set("文件解析失败")
    
    def _update_file_info(self):
        """更新文件信息显示"""
        if not self.flv_file:
            return
            
        # 获取文件头信息
        header_info = self.flv_file.get_header_info()
        
        # 更新文件信息文本
        self.file_info_text.config(state=tk.NORMAL)
        self.file_info_text.delete(1.0, tk.END)
        
        for key, value in header_info.items():
            self.file_info_text.insert(tk.END, f"{key}: {value}\n")
            
        self.file_info_text.config(state=tk.DISABLED)
    
    def _update_tag_stats(self):
        """更新标签统计信息"""
        if not self.flv_file:
            return
            
        # 获取标签统计信息
        tag_counts = self.flv_file.get_tag_count()
        
        # 更新标签统计文本
        self.tag_stats_text.config(state=tk.NORMAL)
        self.tag_stats_text.delete(1.0, tk.END)
        
        for key, value in tag_counts.items():
            self.tag_stats_text.insert(tk.END, f"{key}: {value}\n")
            
        self.tag_stats_text.config(state=tk.DISABLED)
    
    def _populate_tree(self):
        """填充树形视图"""
        if not self.flv_file:
            return
            
        # 清空树形视图
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 添加文件头节点
        header_node = self.tree.insert("", tk.END, text="FLV Header", values=("header",))
        
        # 添加文件头详情
        header_info = self.flv_file.get_header_info()
        for key, value in header_info.items():
            self.tree.insert(header_node, tk.END, text=f"{key}: {value}")
            
        # 添加标签节点
        tags_node = self.tree.insert("", tk.END, text="FLV Tags", values=("tags",))
        
        # 添加各个标签
        for i, tag in enumerate(self.flv_file.get_tags()):
            tag_info = tag.get_display_info()
            tag_node = self.tree.insert(
                tags_node, 
                tk.END, 
                text=f"Tag {i+1}: {tag_info['Type']} @ {tag_info['Timestamp']}",
                values=("tag", i)
            )
            
            # 添加标签基本信息
            for key in ["Offset", "Size", "Timestamp"]:
                self.tree.insert(tag_node, tk.END, text=f"{key}: {tag_info[key]}")
                
            # 添加标签详情
            if tag_info["Details"]:
                details_node = self.tree.insert(tag_node, tk.END, text="Details")
                for key, value in tag_info["Details"].items():
                    self.tree.insert(details_node, tk.END, text=f"{key}: {value}")
        
        # 展开根节点
        self.tree.item(header_node, open=True)
        self.tree.item(tags_node, open=True)
    
    def _on_tree_select(self, event):
        """处理树形视图选择事件"""
        selected_item = self.tree.selection()
        if not selected_item:
            return
            
        item_id = selected_item[0]
        item_values = self.tree.item(item_id, "values")
        
        # 清空详情文本
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        
        if len(item_values) >= 2 and item_values[0] == "tag":
            # 显示标签详情
            tag_index = int(item_values[1])
            if 0 <= tag_index < len(self.flv_file.get_tags()):
                tag = self.flv_file.get_tags()[tag_index]
                tag_info = tag.get_display_info()
                
                # 添加基本信息
                self.details_text.insert(tk.END, f"标签类型: {tag_info['Type']}\n")
                self.details_text.insert(tk.END, f"文件偏移: {tag_info['Offset']}\n")
                self.details_text.insert(tk.END, f"数据大小: {tag_info['Size']} 字节\n")
                self.details_text.insert(tk.END, f"时间戳: {tag_info['Timestamp']}\n\n")
                
                # 添加详细信息
                if tag_info["Details"]:
                    self.details_text.insert(tk.END, "详细信息:\n")
                    for key, value in tag_info["Details"].items():
                        self.details_text.insert(tk.END, f"  {key}: {value}\n")
                        
                # 添加十六进制数据预览
                if tag.data:
                    self.details_text.insert(tk.END, "\n数据预览 (十六进制):\n")
                    
                    # 每行显示16个字节
                    for i in range(0, min(len(tag.data), 160), 16):
                        # 十六进制部分
                        hex_part = ""
                        for j in range(16):
                            if i + j < len(tag.data):
                                hex_part += f"{tag.data[i+j]:02X} "
                            else:
                                hex_part += "   "
                                
                        # ASCII部分
                        ascii_part = ""
                        for j in range(16):
                            if i + j < len(tag.data):
                                if 32 <= tag.data[i+j] <= 126:  # 可打印ASCII字符
                                    ascii_part += chr(tag.data[i+j])
                                else:
                                    ascii_part += "."
                            else:
                                ascii_part += " "
                                
                        self.details_text.insert(tk.END, f"  {i:04X}: {hex_part} | {ascii_part}\n")
                        
                    if len(tag.data) > 160:
                        self.details_text.insert(tk.END, "  ...（数据过长，仅显示前160字节）\n")
        
        self.details_text.config(state=tk.DISABLED)
    
    def _search(self, event=None):
        """搜索标签"""
        search_text = self.search_var.get().strip().lower()
        if not search_text or not self.flv_file:
            return
            
        # 重置搜索结果
        self.search_results = []
        self.current_search_index = -1
        
        # 搜索所有标签
        for i, tag in enumerate(self.flv_file.get_tags()):
            tag_info = tag.get_display_info()
            
            # 检查标签类型
            if search_text in tag_info["Type"].lower():
                self.search_results.append(i)
                continue
                
            # 检查详情
            for key, value in tag_info["Details"].items():
                if search_text in str(value).lower() or search_text in key.lower():
                    self.search_results.append(i)
                    break
        
        # 更新状态栏
        if self.search_results:
            self.status_var.set(f"找到 {len(self.search_results)} 个匹配项")
            self._next_search_result()
        else:
            self.status_var.set(f"未找到匹配项: {search_text}")
    
    def _next_search_result(self):
        """跳转到下一个搜索结果"""
        if not self.search_results:
            return
            
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self._highlight_search_result()
    
    def _prev_search_result(self):
        """跳转到上一个搜索结果"""
        if not self.search_results:
            return
            
        self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
        self._highlight_search_result()
    
    def _highlight_search_result(self):
        """高亮显示当前搜索结果"""
        if not self.search_results or self.current_search_index < 0:
            return
            
        # 获取标签索引
        tag_index = self.search_results[self.current_search_index]
        
        # 查找对应的树节点
        tags_node = None
        for item in self.tree.get_children():
            if self.tree.item(item, "values") and self.tree.item(item, "values")[0] == "tags":
                tags_node = item
                break
                
        if not tags_node:
            return
            
        # 查找标签节点
        tag_node = None
        for item in self.tree.get_children(tags_node):
            item_values = self.tree.item(item, "values")
            if len(item_values) >= 2 and item_values[0] == "tag" and int(item_values[1]) == tag_index:
                tag_node = item
                break
                
        if not tag_node:
            return
            
        # 展开并选择节点
        self.tree.see(tag_node)
        self.tree.selection_set(tag_node)
        
        # 更新状态栏
        self.status_var.set(f"搜索结果 {self.current_search_index + 1}/{len(self.search_results)}")
    
    def _show_about(self):
        """显示关于对话框"""
        messagebox.showinfo(
            "关于FLV解析器",
            "FLV文件解析与可视化工具\n\n"
            "这个工具可以解析FLV文件格式，并以树形结构显示文件内容。\n"
            "支持查看标签详情、搜索特定标签等功能。"
        )


def main():
    """主函数"""
    root = tk.Tk()
    app = FLVParserGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()