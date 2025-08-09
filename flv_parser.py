import struct
import os
import sys # 导入 sys 模块
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Any, Tuple, Optional, IO
from collections import Counter
import subprocess
from datetime import datetime

# --- AMF0 Parsing Utilities ---

def _read_ui8(f: IO[bytes]) -> int:
    return struct.unpack('>B', f.read(1))[0]

def _read_ui16(f: IO[bytes]) -> int:
    return struct.unpack('>H', f.read(2))[0]

def _read_double(f: IO[bytes]) -> float:
    return struct.unpack('>d', f.read(8))[0]

def _parse_amf_string(f: IO[bytes]) -> str:
    length = _read_ui16(f)
    return f.read(length).decode('utf-8', errors='replace')

def _parse_amf_value(f: IO[bytes], type_marker: Optional[int] = None) -> Any:
    if type_marker is None:
        type_marker = _read_ui8(f)
    
    if type_marker == 0:  # Number
        return _read_double(f)
    elif type_marker == 1:  # Boolean
        return _read_ui8(f) != 0
    elif type_marker == 2:  # String
        return _parse_amf_string(f)
    elif type_marker == 3:  # Object
        obj = {}
        while True:
            try:
                key = _parse_amf_string(f)
                if not key: break # End of object
                value_type = _read_ui8(f)
                if value_type == 9: break # Object End Marker
                obj[key] = _parse_amf_value(f, value_type)
            except (struct.error, IndexError):
                break # Reached end of data
        return obj
    elif type_marker == 8:  # ECMA Array
        count = struct.unpack('>I', f.read(4))[0]
        arr = {}
        for _ in range(count):
            key = _parse_amf_string(f)
            value = _parse_amf_value(f)
            arr[key] = value
        # Read object end marker (a string of length 0 and a type marker 9)
        f.read(3)
        return arr
    elif type_marker == 10: # Strict Array
        count = struct.unpack('>I', f.read(4))[0]
        arr = []
        for _ in range(count):
            arr.append(_parse_amf_value(f))
        return arr
    else:
        return f"Unsupported AMF Type: {type_marker}"

class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_pos = 0
        self.bit_pos = 0

    def read(self, num_bits: int) -> int:
        value = 0
        while num_bits > 0:
            if self.byte_pos >= len(self.data):
                raise ValueError("Reading past end of data")
            current_byte = self.data[self.byte_pos]
            bits_to_read = min(num_bits, 8 - self.bit_pos)
            mask = ((1 << bits_to_read) - 1) << (8 - self.bit_pos - bits_to_read)
            bits = (current_byte & mask) >> (8 - self.bit_pos - bits_to_read)
            value = (value << bits_to_read) | bits
            self.bit_pos += bits_to_read
            num_bits -= bits_to_read
            if self.bit_pos == 8:
                self.bit_pos = 0
                self.byte_pos += 1
        return value

AAC_AUDIO_OBJECT_TYPES = {
    1: "AAC Main", 2: "AAC LC", 3: "AAC SSR", 4: "AAC LTP", 5: "SBR", 6: "AAC Scalable"
}
AAC_SAMPLING_FREQUENCIES = {
    0: "96000 Hz", 1: "88200 Hz", 2: "64000 Hz", 3: "48000 Hz", 4: "44100 Hz",
    5: "32000 Hz", 6: "24000 Hz", 7: "22050 Hz", 8: "16000 Hz", 9: "12000 Hz",
    10: "11025 Hz", 11: "8000 Hz", 12: "7350 Hz"
}
AAC_CHANNEL_CONFIGURATIONS = {
    1: "1 channel: C", 2: "2 channels: L, R", 3: "3 channels: C, L, R",
    4: "4 channels: C, L, R, B", 5: "5 channels: C, L, R, SL, SR",
    6: "6 channels: C, L, R, SL, SR, LFE", 7: "8 channels: C, L, R, SL, SR, BL, BR, LFE"
}

class FLVTag:
    AUDIO, VIDEO, SCRIPT = 8, 9, 18
    TAG_TYPES = {AUDIO: "Audio", VIDEO: "Video", SCRIPT: "Script Data"}
    AUDIO_FORMATS = {
        0: "LPCM", 1: "ADPCM", 2: "MP3", 3: "LPCM LE", 4: "Nellymoser 16kHz",
        5: "Nellymoser 8kHz", 6: "Nellymoser", 7: "G.711 A-law", 8: "G.711 mu-law",
        9: "reserved", 10: "AAC", 11: "Speex", 14: "MP3 8kHz", 15: "Device-specific"
    }
    AUDIO_RATES = {0: "5.5kHz", 1: "11kHz", 2: "22kHz", 3: "44kHz"}
    AUDIO_BITS = {0: "8-bit", 1: "16-bit"}
    AUDIO_CHANNELS = {0: "Mono", 1: "Stereo"}
    VIDEO_FRAME_TYPES = {
        1: "Key frame", 2: "Inter frame", 3: "Disposable inter frame",
        4: "Generated key frame", 5: "Video info/command frame"
    }
    VIDEO_CODECS = {
        2: "Sorenson H.263", 3: "Screen video", 4: "On2 VP6",
        5: "On2 VP6 with alpha", 6: "Screen video v2", 7: "AVC (H.264)"
    }

    def __init__(self, offset: int, data: bytes, global_metadata: Dict[str, Any]):
        self.offset = offset
        self.tag_type = data[0]
        self.data_size = (data[1] << 16) | (data[2] << 8) | data[3]
        self.timestamp = (data[4] << 16) | (data[5] << 8) | data[6] | (data[7] << 24)
        self.stream_id = (data[8] << 16) | (data[9] << 8) | data[10]
        self.data = data[11:11+self.data_size]
        self.total_size = 11 + self.data_size + 4
        self.details = {}
        self.analysis = {} # For frame drop analysis
        
        if self.tag_type == FLVTag.AUDIO:
            self._parse_audio_data(global_metadata)
        elif self.tag_type == FLVTag.VIDEO:
            self._parse_video_data()
        elif self.tag_type == FLVTag.SCRIPT:
            self._parse_script_data()

    def _parse_audio_data(self, meta: Dict[str, Any]):
        if not self.data: return
        flags = self.data[0]
        sound_format = flags >> 4
        self.details["Format"] = self.AUDIO_FORMATS.get(sound_format, f"Unknown ({sound_format})")
        self.details["Sample Size"] = self.AUDIO_BITS.get((flags >> 1) & 0x1, "Unknown")

        if sound_format == 10 and len(self.data) > 1: # AAC
            aac_packet_type = self.data[1]
            self.details["AAC Packet Type"] = "AAC sequence header" if aac_packet_type == 0 else "AAC raw"
            if aac_packet_type == 0 and len(self.data) > 3:
                try:
                    reader = BitReader(self.data[2:])
                    obj_type = reader.read(5)
                    freq_idx = reader.read(4)
                    self.details["Audio Object Type"] = AAC_AUDIO_OBJECT_TYPES.get(obj_type, "Unknown")
                    if freq_idx == 15:
                        self.details["Sample Rate"] = f"{reader.read(24)} Hz (Explicit from ASC)"
                    else:
                        self.details["Sample Rate"] = f"{AAC_SAMPLING_FREQUENCIES.get(freq_idx, 'Unknown')} (from ASC)"
                    chan_cfg = reader.read(4)
                    self.details["Channels"] = f"{AAC_CHANNEL_CONFIGURATIONS.get(chan_cfg, 'Unknown')} (from ASC)"
                    return
                except Exception as e:
                    self.details["ASC Parse Error"] = str(e)

        if 'audiosamplerate' in meta:
            self.details["Sample Rate"] = f"{int(meta['audiosamplerate'])} Hz (from onMetaData)"
        else:
            self.details["Sample Rate"] = f"{self.AUDIO_RATES.get((flags >> 2) & 0x3, 'Unknown')} (from Tag Header)"
        
        if 'stereo' in meta:
            self.details["Channels"] = "Stereo (from onMetaData)" if meta['stereo'] else "Mono (from onMetaData)"
        else:
            self.details["Channels"] = f"{self.AUDIO_CHANNELS.get(flags & 0x1, 'Unknown')} (from Tag Header)"

    def _parse_video_data(self):
        if not self.data: return
        flags = self.data[0]
        frame_type, codec_id = (flags >> 4) & 0xF, flags & 0xF
        self.details["Frame Type"] = self.VIDEO_FRAME_TYPES.get(frame_type, f"Unknown ({frame_type})")
        self.details["Codec ID"] = self.VIDEO_CODECS.get(codec_id, f"Unknown ({codec_id})")
        if codec_id == 7 and len(self.data) > 4: # AVC
            avc_packet_type = self.data[1]
            cts = (self.data[2] << 16) | (self.data[3] << 8) | self.data[4]
            self.details["AVC Packet Type"] = {0: "Seq. header", 1: "NALU", 2: "End of seq."}.get(avc_packet_type, "Unknown")
            self.details["CompositionTime Offset"] = f"{cts} ms"

    def _parse_script_data(self):
        if not self.data: return
        from io import BytesIO
        f = BytesIO(self.data)
        try:
            name = _parse_amf_value(f)
            value = _parse_amf_value(f)
            self.details["Name"] = name
            if name == "onMetaData":
                self.details["Type"] = "Metadata"
                self.details["Metadata"] = value
            else:
                self.details["Value"] = value
        except Exception as e:
            self.details["Parse Error"] = str(e)

    def get_type_name(self) -> str:
        return self.TAG_TYPES.get(self.tag_type, f"Unknown ({self.tag_type})")

    def get_display_info(self) -> Dict[str, Any]:
        info = {"Offset": f"0x{self.offset:08X}", "Type": self.get_type_name(),
                "Size": self.data_size, "Timestamp": f"{self.timestamp} ms"}
        if self.analysis:
            info["Analysis"] = self.analysis
        info["Details"] = self.details
        return info

class FLVFile:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.header, self.tags, self.metadata = {}, [], {}
        self._parse()
        self._analyze_tags()

    def _parse(self):
        with open(self.file_path, 'rb') as f:
            header_data = f.read(9)
            if len(header_data) < 9 or header_data[0:3] != b'FLV':
                raise ValueError("Invalid FLV file")
            self.header["Version"] = header_data[3]
            flags = header_data[4]
            self.header["HasVideo"], self.header["HasAudio"] = bool(flags & 1), bool(flags & 4)
            self.header["HeaderSize"] = struct.unpack(">I", header_data[5:9])[0]
            f.seek(self.header["HeaderSize"])
            f.read(4)
            
            temp_offset = self.header["HeaderSize"] + 4
            while True:
                tag_header = f.read(11)
                if len(tag_header) < 11: break
                tag_type = tag_header[0]
                data_size = (tag_header[1] << 16) | (tag_header[2] << 8) | tag_header[3]
                if tag_type == FLVTag.SCRIPT:
                    tag_data = tag_header + f.read(data_size)
                    tag = FLVTag(temp_offset, tag_data, {})
                    if tag.details.get("Name") == "onMetaData":
                        self.metadata = tag.details.get("Metadata", {})
                        break
                else:
                    f.seek(data_size + 4, 1)
                temp_offset += 11 + data_size + 4

            f.seek(self.header["HeaderSize"] + 4)
            offset = self.header["HeaderSize"] + 4
            while True:
                tag_header = f.read(11)
                if len(tag_header) < 11: break
                data_size = (tag_header[1] << 16) | (tag_header[2] << 8) | tag_header[3]
                tag_data = tag_header + f.read(data_size)
                self.tags.append(FLVTag(offset, tag_data, self.metadata))
                f.read(4)
                offset += 11 + data_size + 4

    def _analyze_tags(self):
        framerate = self.metadata.get('framerate')
        if framerate and framerate > 0:
            video_tags = [t for t in self.tags if t.tag_type == FLVTag.VIDEO]
            expected_interval = 1000 / framerate
            threshold = expected_interval * 2
            for i in range(1, len(video_tags)):
                prev_tag, curr_tag = video_tags[i-1], video_tags[i]
                gap = curr_tag.timestamp - prev_tag.timestamp
                if gap > threshold:
                    dropped_frames = round(gap / expected_interval) - 1
                    curr_tag.analysis['Warning'] = f"视频时间戳跳跃 {gap}ms (预期值 ~{expected_interval:.1f}ms)，可能丢失 {dropped_frames} 帧。"
                    curr_tag.analysis['Reason'] = "可能原因：推流端性能不足、网络抖动丢包、编码器延迟。"

        audio_tags = [t for t in self.tags if t.tag_type == FLVTag.AUDIO]
        if len(audio_tags) > 10:
            gaps = [audio_tags[i].timestamp - audio_tags[i-1].timestamp for i in range(1, len(audio_tags))]
            common_gap = Counter(g for g in gaps if g > 0).most_common(1)
            if common_gap:
                expected_interval = common_gap[0][0]
                threshold = expected_interval * 2.5
                for i in range(1, len(audio_tags)):
                    prev_tag, curr_tag = audio_tags[i-1], audio_tags[i]
                    gap = curr_tag.timestamp - prev_tag.timestamp
                    if gap > threshold:
                        dropped_packets = round(gap / expected_interval) - 1
                        curr_tag.analysis['Warning'] = f"音频时间戳跳跃 {gap}ms (预期值 ~{expected_interval}ms)，可能丢失 {dropped_packets} 个音频包。"
                        curr_tag.analysis['Reason'] = "可能原因：推流端音频采集问题、网络抖动、服务器处理延迟。"

    def get_header_info(self) -> Dict[str, Any]:
        return {"File": self.file_name, **self.header}

class FLVParserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FLV文件解析与工具集")
        self.root.geometry("1200x800")
        self.flv_file = None
        self._create_widgets()
        self._setup_layout()

    def _create_widgets(self):
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="打开FLV文件", command=self._open_file)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        self.menu_bar.add_cascade(label="文件", menu=file_menu)

        self.toolbar_frame = ttk.Frame(self.root)
        self.open_button = ttk.Button(self.toolbar_frame, text="打开FLV文件", command=self._open_file)
        self.report_button = ttk.Button(self.toolbar_frame, text="丢帧分析报告", command=self._show_analysis_report, state=tk.DISABLED)
        self.extract_button = ttk.Button(self.toolbar_frame, text="分离音视频", command=self._extract_streams, state=tk.DISABLED)
        
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        
        self.tree_frame = ttk.Frame(self.main_paned)
        self.tree = ttk.Treeview(self.tree_frame, selectmode=tk.BROWSE)
        self.tree.heading("#0", text="FLV结构", anchor=tk.W)
        self.tree.tag_configure('warning', foreground='red')
        self.tree_scrollbar_y = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scrollbar_y.set)
        
        self.right_pane = ttk.PanedWindow(self.main_paned, orient=tk.VERTICAL)
        self.info_frame = ttk.Frame(self.right_pane)
        self.file_info_labelframe = ttk.LabelFrame(self.info_frame, text="文件信息")
        self.file_info_text = tk.Text(self.file_info_labelframe, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.file_info_text.bind("<Key>", lambda e: "break") # Make read-only but allow copy
        
        self.details_frame = ttk.Frame(self.right_pane)
        self.details_labelframe = ttk.LabelFrame(self.details_frame, text="标签详情")
        self.details_text = tk.Text(self.details_labelframe, wrap=tk.WORD, state=tk.DISABLED)
        self.copy_button = ttk.Button(self.details_labelframe, text="复制详情", command=self._copy_details)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _setup_layout(self):
        self.toolbar_frame.pack(fill=tk.X, padx=5, pady=5)
        self.open_button.pack(side=tk.LEFT, padx=5)
        self.report_button.pack(side=tk.LEFT, padx=5)
        self.extract_button.pack(side=tk.LEFT, padx=5)
        
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.main_paned.add(self.tree_frame, weight=2)
        self.tree_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        self.main_paned.add(self.right_pane, weight=3)
        self.right_pane.add(self.info_frame, weight=1)
        self.file_info_labelframe.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.file_info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.right_pane.add(self.details_frame, weight=3)
        self.details_labelframe.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.copy_button.pack(side=tk.RIGHT, anchor=tk.SE, padx=5, pady=5)
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _open_file(self):
        file_path = filedialog.askopenfilename(title="选择FLV文件", filetypes=[("FLV文件", "*.flv")])
        if not file_path: return
        try:
            self.flv_file = FLVFile(file_path)
            self._update_file_info()
            self._populate_tree()
            self.report_button.config(state=tk.NORMAL)
            self.extract_button.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("错误", f"解析文件时出错: {e}")
            self.report_button.config(state=tk.DISABLED)
            self.extract_button.config(state=tk.DISABLED)

    def _update_file_info(self):
        self.file_info_text.config(state=tk.NORMAL)
        self.file_info_text.delete(1.0, tk.END)
        
        # --- Basic FLV Header Info ---
        info = self.flv_file.get_header_info()
        self.file_info_text.insert(tk.END, "--- FLV 基础信息 ---\n")
        for key, value in info.items():
            self.file_info_text.insert(tk.END, f"{key}: {value}\n")

        # --- File System Info ---
        try:
            stat = os.stat(self.flv_file.file_path)
            size_mb = stat.st_size / (1024 * 1024)
            creation_time = datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            modification_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            self.file_info_text.insert(tk.END, "\n--- 文件系统信息 ---\n")
            self.file_info_text.insert(tk.END, f"文件大小: {size_mb:.2f} MB\n")
            self.file_info_text.insert(tk.END, f"创建时间: {creation_time}\n")
            self.file_info_text.insert(tk.END, f"修改时间: {modification_time}\n")
        except Exception:
            pass # Ignore if file stat fails

        # --- Media Duration from Metadata ---
        duration = self.flv_file.metadata.get('duration')
        if duration:
            minutes, seconds = divmod(duration, 60)
            self.file_info_text.insert(tk.END, "\n--- 媒体信息 ---\n")
            self.file_info_text.insert(tk.END, f"媒体时长: {int(minutes):02d}:{seconds:05.2f}\n")

        self.file_info_text.config(state=tk.DISABLED)

    def _populate_tree(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        header_node = self.tree.insert("", tk.END, text="FLV Header", open=True)
        for key, value in self.flv_file.get_header_info().items():
            self.tree.insert(header_node, tk.END, text=f"{key}: {value}")
        
        tags_node = self.tree.insert("", tk.END, text="FLV Tags", open=True)
        for i, tag in enumerate(self.flv_file.tags):
            info = tag.get_display_info()
            tag_style = ('warning',) if 'Analysis' in info else ()
            tag_node = self.tree.insert(tags_node, tk.END, text=f"Tag {i+1}: {info['Type']} @ {info['Timestamp']}", values=("tag", i), tags=tag_style)
            
            if info.get("Analysis"):
                self.tree.insert(tag_node, tk.END, text=f"Analysis: {info['Analysis']['Warning']}", tags=('warning',))
            
            self.tree.insert(tag_node, tk.END, text=f"Offset: {info['Offset']}")
            self.tree.insert(tag_node, tk.END, text=f"Size: {info['Size']}")
            
            if info["Details"]:
                details_node = self.tree.insert(tag_node, tk.END, text="Details")
                self._populate_details_tree(details_node, info["Details"])

    def _populate_details_tree(self, parent, details):
        for key, value in details.items():
            if isinstance(value, dict):
                node = self.tree.insert(parent, tk.END, text=str(key))
                self._populate_details_tree(node, value)
            else:
                self.tree.insert(parent, tk.END, text=f"{key}: {value}")

    def _on_tree_select(self, event):
        selected_item = self.tree.selection()
        if not selected_item: return
        item_values = self.tree.item(selected_item[0], "values")
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        if len(item_values) >= 2 and item_values[0] == "tag":
            tag_index = int(item_values[1])
            tag = self.flv_file.tags[tag_index]
            self._format_details_text(tag.get_display_info())
        self.details_text.config(state=tk.DISABLED)

    def _format_details_text(self, details, indent=0):
        prefix = "  " * indent
        for key, value in details.items():
            if isinstance(value, dict):
                self.details_text.insert(tk.END, f"{prefix}{key}:\n")
                self._format_details_text(value, indent + 1)
            else:
                self.details_text.insert(tk.END, f"{prefix}{key}: {value}\n")

    def _copy_details(self):
        content = self.details_text.get(1.0, tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("成功", "标签详情已复制到剪贴板！")

    def _show_analysis_report(self):
        if not self.flv_file: return
        
        report_window = tk.Toplevel(self.root)
        report_window.title("丢帧分析报告")
        report_window.geometry("800x600")
        
        report_text = tk.Text(report_window, wrap=tk.WORD, font=("Courier", 11))
        scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=report_text.yview)
        report_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        meta = self.flv_file.metadata
        report_text.insert(tk.END, "--- 媒体信息参数 ---\n")
        meta_table = [
            ("参数名", "参数值"),("视频宽度", meta.get('width', 'N/A')),("视频高度", meta.get('height', 'N/A')),
            ("视频帧率", meta.get('framerate', 'N/A')),("视频码率(kbps)", meta.get('videodatarate', 'N/A')),
            ("视频编码", FLVTag.VIDEO_CODECS.get(meta.get('videocodecid'), 'N/A')),("音频采样率(Hz)", meta.get('audiosamplerate', 'N/A')),
            ("音频声道", "双声道" if meta.get('stereo') else "单声道"),("音频码率(kbps)", meta.get('audiodatarate', 'N/A')),
            ("音频编码", FLVTag.AUDIO_FORMATS.get(meta.get('audiocodecid'), 'N/A')),
        ]
        
        col_widths = [max(len(str(item[i])) for item in meta_table) for i in range(2)]
        header = f"{'参数名':<{col_widths[0]}} | {'参数值':<{col_widths[1]}}\n"
        separator = "-" * (col_widths[0] + col_widths[1] + 3) + "\n"
        report_text.insert(tk.END, header)
        report_text.insert(tk.END, separator)
        for name, value in meta_table[1:]:
            report_text.insert(tk.END, f"{str(name):<{col_widths[0]}} | {str(value):<{col_widths[1]}}\n")

        report_text.insert(tk.END, "\n\n--- 时间戳跳跃分析 ---\n")
        problematic_tags = [ (i, tag) for i, tag in enumerate(self.flv_file.tags) if tag.analysis ]
        
        if not problematic_tags:
            report_text.insert(tk.END, "未检测到明显的时间戳跳跃或丢帧问题。")
        else:
            report_text.insert(tk.END, f"检测到 {len(problematic_tags)} 个有问题的标签:\n\n")
            for i, tag in problematic_tags:
                info = tag.get_display_info()
                report_text.insert(tk.END, f"标签 #{i+1} ({info['Type']} @ {info['Timestamp']}):\n")
                report_text.insert(tk.END, f"  - 警告: {info['Analysis']['Warning']}\n")
                report_text.insert(tk.END, f"  - 参考: {info['Analysis']['Reason']}\n\n")
        
        report_text.config(state=tk.DISABLED)

    def _get_ffmpeg_path(self):
        """
        动态获取 ffmpeg 的路径。
        如果是在 PyInstaller 打包的环境中，则返回相对于 _MEIPASS 的路径。
        否则，直接返回 'ffmpeg'，依赖系统 PATH。
        """
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # 在 PyInstaller 打包的应用中
            base_path = sys._MEIPASS
            ffmpeg_executable = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
            return os.path.join(base_path, ffmpeg_executable)
        else:
            # 在正常的开发环境中
            return 'ffmpeg'

    def _check_ffmpeg(self):
        ffmpeg_path = self._get_ffmpeg_path()
        try:
            # 使用获取到的路径执行命令
            subprocess.run([ffmpeg_path, "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _extract_streams(self):
        if not self.flv_file: return

        if not self._check_ffmpeg():
            messagebox.showerror("错误", "未在本机或应用包中找到 FFmpeg。\n请确保已安装 FFmpeg 并将其添加到系统路径，或确保它已随应用正确打包。")
            return

        save_dir = filedialog.askdirectory(initialdir=os.path.expanduser("~/Desktop"), title="选择保存目录")
        if not save_dir: return

        ffmpeg_path = self._get_ffmpeg_path()
        input_file = self.flv_file.file_path
        base_name = os.path.splitext(self.flv_file.file_name)[0]
        output_video = os.path.join(save_dir, f"{base_name}_video.mp4")
        output_audio = os.path.join(save_dir, f"{base_name}_audio.aac")

        try:
            # 使用获取到的路径执行命令
            subprocess.run([ffmpeg_path, "-i", input_file, "-c:v", "copy", "-an", "-y", output_video], check=True)
            subprocess.run([ffmpeg_path, "-i", input_file, "-c:a", "copy", "-vn", "-y", output_audio], check=True)
            messagebox.showinfo("成功", f"音视频已成功分离到:\n{save_dir}")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("FFmpeg 错误", f"执行FFmpeg命令时出错:\n{e}")
        except Exception as e:
            messagebox.showerror("错误", f"分离文件时出错:\n{e}")

def main():
    root = tk.Tk()
    app = FLVParserGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()


