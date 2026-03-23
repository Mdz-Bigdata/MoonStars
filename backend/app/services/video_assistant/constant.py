from app.services.video_assistant.downloaders.bilibili_downloader import BilibiliDownloader
from app.services.video_assistant.downloaders.douyin_downloader import DouyinDownloader
from app.services.video_assistant.downloaders.kuaishou_downloader import KuaiShouDownloader
from app.services.video_assistant.downloaders.local_downloader import LocalDownloader
from app.services.video_assistant.downloaders.youtube_downloader import YoutubeDownloader

SUPPORT_PLATFORM_MAP = {
    'youtube':YoutubeDownloader(),
    'bilibili':BilibiliDownloader(),
    'tiktok':DouyinDownloader(),
    'kuaishou':KuaiShouDownloader(),
    'douyin':DouyinDownloader(),
    'local':LocalDownloader()
}