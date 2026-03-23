from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioDownloadResult:
    file_path: str               # 本地音频路径
    title: str                   # 视频标题
    duration: float              # 视频时长（秒）
    cover_url: Optional[str]     # 视频封面图
    platform: str                # 平台，如 "bilibili"
    video_id: str                # 唯一视频ID
    raw_info: dict               # yt-dlp 的原始 info 字典
    video_path: Optional[str] = None  #  新增字段：可选视频文件路径


@dataclass
class NoteResult:
    """
    GPT 生成笔记后的最终包裹结果，包含 markdown 文本以及转录和音频元信息。
    """
    markdown: str
    transcript: any  # 使用 any 避开循环导入，实际为 TranscriptResult
    audio_meta: AudioDownloadResult

