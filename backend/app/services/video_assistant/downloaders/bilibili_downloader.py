import os
import threading
from abc import ABC
from typing import Union, Optional

import yt_dlp
import ffmpeg

from app.services.video_assistant.downloaders.base import Downloader, DownloadQuality, QUALITY_MAP
from app.services.video_assistant.models.audio_model import AudioDownloadResult
from app.services.video_assistant.utils.path_helper import get_data_dir
from app.services.video_assistant.utils.url_parser import extract_video_id
from app.services.video_assistant.utils.logger import get_logger

logger = get_logger(__name__)

# 全局下载锁，防止并发下载同一个视频导致文件损坏
_DOWNLOAD_LOCKS = {}
_LOCKS_LOCK = threading.Lock()

def get_lock(video_id: str):
    with _LOCKS_LOCK:
        if video_id not in _DOWNLOAD_LOCKS:
            _DOWNLOAD_LOCKS[video_id] = threading.Lock()
        return _DOWNLOAD_LOCKS[video_id]

class BilibiliDownloader(Downloader, ABC):
    def __init__(self):
        super().__init__()

    def _verify_file(self, file_path: str) -> bool:
        """
        使用 ffprobe 验证视频文件是否完整
        """
        if not os.path.exists(file_path):
            return False
        if os.path.getsize(file_path) < 1024:  # 小于 1KB 肯定有问题
            return False
        try:
            ffmpeg.probe(file_path)
            return True
        except Exception as e:
            logger.warning(f"文件验证失败，将删除重试: {file_path}, 错误: {e}")
            try:
                os.remove(file_path)
            except:
                pass
            return False

    def _get_cookie_path(self) -> Optional[str]:
        """获取 cookies 文件路径"""
        cookies_file = os.getenv("BILIBILI_COOKIES_FILE", "cookies.txt")
        # 尝试多个可能的位置
        paths_to_check = [
            cookies_file,
            os.path.join(os.getcwd(), cookies_file),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), cookies_file), # backend 根目录
        ]
        for p in paths_to_check:
            if os.path.exists(p):
                logger.info(f"找到 Bilibili cookies 文件: {p}")
                return p
        return None

    def download(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        quality: DownloadQuality = "fast",
        need_video: Optional[bool] = False
    ) -> AudioDownloadResult:
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir = self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        video_id = extract_video_id(video_url, "bilibili")
        
        with get_lock(f"audio_{video_id}"):
            output_path_tmpl = os.path.join(output_dir, "%(id)s.%(ext)s")

            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': output_path_tmpl,
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '64',
                    }
                ],
                'noplaylist': True,
                'quiet': False,
                # 稳定性优化 (参考 BiliNote 和 yt-dlp 最佳实践)
                'retries': 10,
                'fragment_retries': 10,
                'socket_timeout': 30,
                'source_address': '0.0.0.0',  # 强制使用 IPv4，避免 B 站对某些 IPv6 地址的连接重置
                'nockeckcertificate': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.bilibili.com',
                },
                'extractor_args': {
                    'bilibili': {
                        'player_backend': ['mediasource'], # 尝试更稳定的后端
                    }
                }
            }

            cookie_path = self._get_cookie_path()
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path
            
            # 支持从浏览器读取 Cookies (例如 chrome, firefox, edge)
            browser_cookies = os.getenv("BILIBILI_COOKIES_FROM_BROWSER")
            if browser_cookies:
                ydl_opts['cookiesfrombrowser'] = (browser_cookies,)
                logger.info(f"使用浏览器 {browser_cookies} 的 Cookies")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_id_real = info.get("id")
                title = info.get("title")
                duration = info.get("duration", 0)
                cover_url = info.get("thumbnail")
                
                actual_filename = info.get('_filename')
                if actual_filename:
                    audio_path = os.path.splitext(actual_filename)[0] + ".mp3"
                else:
                    audio_path = os.path.join(output_dir, f"{video_id_real}.mp3")

                # 如果 mp3 文件损坏或不存在，尝试清理并重新触发 (虽然 yt-dlp 已经下载了，但在并发下可能出问题)
                if not os.path.exists(audio_path):
                     logger.warning(f"音频文件不存在: {audio_path}")

            return AudioDownloadResult(
                file_path=audio_path,
                title=title,
                duration=duration,
                cover_url=cover_url,
                platform="bilibili",
                video_id=video_id_real,
                raw_info=info,
                video_path=None
            )

    def download_video(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
    ) -> str:
        """
        下载视频，返回视频文件路径
        """
        if output_dir is None:
            output_dir = get_data_dir()
        os.makedirs(output_dir, exist_ok=True)
        
        video_id = extract_video_id(video_url, "bilibili")
        
        with get_lock(f"video_{video_id}"):
            # 1. 检查物理文件并验证
            # 注意：由于 B 站分 P 会带 _p1 后缀，我们无法直接预测精准路径，
            # 所以我们还是需要先跑一遍 yt-dlp (download=False) 来获取最终 ID 和路径。
            
            output_path_tmpl = os.path.join(output_dir, "%(id)s.%(ext)s")

            ydl_opts = {
                'format': 'bv*[ext=mp4]/bestvideo+bestaudio/best',
                'outtmpl': output_path_tmpl,
                'noplaylist': True,
                'quiet': False,
                'merge_output_format': 'mp4',
                # 稳定性优化
                'retries': 10,
                'fragment_retries': 10,
                'socket_timeout': 30,
                'source_address': '0.0.0.0',
                'nockeckcertificate': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.bilibili.com',
                },
                'extractor_args': {
                    'bilibili': {
                        'player_backend': ['mediasource'],
                    }
                }
            }

            cookie_path = self._get_cookie_path()
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path

            # 支持从浏览器读取 Cookies
            browser_cookies = os.getenv("BILIBILI_COOKIES_FROM_BROWSER")
            if browser_cookies:
                ydl_opts['cookiesfrombrowser'] = (browser_cookies,)
                logger.info(f"使用浏览器 {browser_cookies} 的 Cookies")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 获取信息但不立即下载，以便我们检查缓存文件是否损坏
                info_only = ydl.extract_info(video_url, download=False)
                potential_video_path = info_only.get('_filename')
                
                if potential_video_path and os.path.exists(potential_video_path):
                    if self._verify_file(potential_video_path):
                        logger.info(f"使用已验证的缓存视频: {potential_video_path}")
                        return potential_video_path
                    else:
                        logger.warning(f"无效的视频缓存，将重新下载: {potential_video_path}")
                
                # 2. 执行实际下载
                info = ydl.extract_info(video_url, download=True)
                video_path = info.get('_filename')
                
                if not video_path or not os.path.exists(video_path):
                    video_id_real = info.get("id")
                    video_path = os.path.join(output_dir, f"{video_id_real}.mp4")

            if not os.path.exists(video_path):
                raise FileNotFoundError(f"视频文件未找到: {video_path}")
            
            # 最后验证一次
            if not self._verify_file(video_path):
                raise ValueError(f"下载的视频文件损坏或无法读取: {video_path}")

            return video_path

    def delete_video(self, video_path: str) -> str:
        """
        删除视频文件
        """
        if os.path.exists(video_path):
            os.remove(video_path)
            return f"视频文件已删除: {video_path}"
        else:
            return f"视频文件未找到: {video_path}"