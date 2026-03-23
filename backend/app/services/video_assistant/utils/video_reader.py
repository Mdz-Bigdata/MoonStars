import base64
import os
import re
import subprocess
import ffmpeg
from PIL import Image, ImageDraw, ImageFont

from app.services.video_assistant.utils.logger import get_logger
from app.services.video_assistant.utils.path_helper import get_app_dir

logger = get_logger(__name__)

class VideoReader:
    def __init__(self,
                 video_path: str,
                 task_id: str = "default",
                 grid_size=(3, 3),
                 frame_interval=2,
                 unit_width=960,
                 unit_height=540,
                 save_quality=90,
                 font_path="fonts/arial.ttf",
                 frame_dir=None,
                 grid_dir=None):
        self.video_path = video_path
        self.task_id = task_id
        self.grid_size = grid_size
        self.frame_interval = frame_interval
        self.unit_width = unit_width
        self.unit_height = unit_height
        self.save_quality = save_quality
        
        # 使用 task_id 创建唯一目录，防止并发任务冲突
        self.frame_dir = frame_dir or get_app_dir(os.path.join("output_frames", task_id))
        self.grid_dir = grid_dir or get_app_dir(os.path.join("grid_output", task_id))
        
        logger.info(f"VideoReader 初始化 - 任务ID: {task_id}, 视频: {video_path}")
        logger.debug(f"工作目录: 帧={self.frame_dir}, 网格={self.grid_dir}")
        self.font_path = font_path

    def format_time(self, seconds: float) -> str:
        mm = int(seconds // 60)
        ss = int(seconds % 60)
        return f"{mm:02d}_{ss:02d}"

    def extract_time_from_filename(self, filename: str) -> float:
        match = re.search(r"frame_(\d{2})_(\d{2})\.jpg", filename)
        if match:
            mm, ss = map(int, match.groups())
            return mm * 60 + ss
        return float('inf')

    def get_duration(self) -> float:
        """
        稳健获取视频时长
        """
        try:
            probe = ffmpeg.probe(self.video_path)
            duration = float(probe.get('format', {}).get('duration', 0))
            if duration == 0:
                for stream in probe.get('streams', []):
                    if 'duration' in stream:
                        duration = float(stream['duration'])
                        break
            return duration
        except Exception as e:
            logger.error(f"无法获取视频时长: {self.video_path}, 错误: {e}")
            return 0

    def extract_frames(self, max_frames=50) -> list[str]:
        """
        按间隔提取帧。限制最大帧数，防止 PPT 过大。
        """
        try:
            os.makedirs(self.frame_dir, exist_ok=True)
            duration = self.get_duration()
            if duration <= 0:
                logger.error(f"视频时长无效: {duration}")
                raise ValueError("无法处理时长无效的视频")

            timestamps = [i for i in range(0, int(duration), self.frame_interval)][:max_frames]

            image_paths = []
            for ts in timestamps:
                time_label = self.format_time(ts)
                output_path = os.path.join(self.frame_dir, f"frame_{time_label}.jpg")
                
                # 如果已经存在则跳过
                if os.path.exists(output_path):
                    image_paths.append(output_path)
                    continue
                    
                cmd = [
                    "ffmpeg", "-ss", str(ts), "-i", self.video_path, 
                    "-frames:v", "1", "-q:v", "2", "-y", output_path,
                    "-hide_banner", "-loglevel", "error"
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    image_paths.append(output_path)
                except subprocess.CalledProcessError as e:
                    logger.warning(f"提取帧失败 (ts={ts}): {e.stderr.decode().strip()}")
                    continue
            
            if not image_paths:
                raise ValueError("未提取到任何有效帧")
                
            return image_paths
        except Exception as e:
            logger.error(f"分割帧发生错误：{str(e)}")
            raise ValueError(f"视频处理失败: {str(e)}")

    def group_images(self) -> list[list[str]]:
        image_files = [os.path.join(self.frame_dir, f) for f in os.listdir(self.frame_dir) if
                       f.startswith("frame_") and f.endswith(".jpg")]
        image_files.sort(key=lambda f: self.extract_time_from_filename(os.path.basename(f)))
        group_size = self.grid_size[0] * self.grid_size[1]
        return [image_files[i:i + group_size] for i in range(0, len(image_files), group_size)]

    def concat_images(self, image_paths: list[str], name: str) -> str:
        os.makedirs(self.grid_dir, exist_ok=True)
        # 尝试查找字体
        font = None
        if os.path.exists(self.font_path):
            font = ImageFont.truetype(self.font_path, 48)
        else:
            # 常见系统路径兜底
            possible_fonts = ["/System/Library/Fonts/Cache/STHeiti Light.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
            for f in possible_fonts:
                if os.path.exists(f):
                    font = ImageFont.truetype(f, 48)
                    break
        
        if not font:
            font = ImageFont.load_default()
            
        images = []

        for path in image_paths:
            img = Image.open(path).convert("RGB").resize((self.unit_width, self.unit_height), Image.Resampling.LANCZOS)
            timestamp = re.search(r"frame_(\d{2})_(\d{2})\.jpg", os.path.basename(path))
            time_text = f"{timestamp.group(1)}:{timestamp.group(2)}" if timestamp else ""
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), time_text, fill="yellow", font=font, stroke_width=1, stroke_fill="black")
            images.append(img)

        cols, rows = self.grid_size
        grid_img = Image.new("RGB", (self.unit_width * cols, self.unit_height * rows), (255, 255, 255))

        for i, img in enumerate(images):
            x = (i % cols) * self.unit_width
            y = (i // cols) * self.unit_height
            grid_img.paste(img, (x, y))

        save_path = os.path.join(self.grid_dir, f"{name}.jpg")
        grid_img.save(save_path, quality=self.save_quality)
        return save_path

    def encode_images_to_base64(self, image_paths: list[str]) -> list[str]:
        base64_images = []
        for path in image_paths:
            with open(path, "rb") as img_file:
                encoded_string = base64.b64encode(img_file.read()).decode("utf-8")
                base64_images.append(f"data:image/jpeg;base64,{encoded_string}")
        return base64_images

    def run(self)->list[str]:
        logger.info(f"[{self.task_id}] 开始提取视频帧...")
        try:
            # 确保目录存在
            os.makedirs(self.frame_dir, exist_ok=True)
            os.makedirs(self.grid_dir, exist_ok=True)
            
            # 仅清理当前任务的帧（如果需要）
            # 注意：此处不强制清理，如果之前已经有成功的帧可以复用

            self.extract_frames()
            
            logger.info("开始拼接网格图...")
            image_paths = []
            groups = self.group_images()
            for idx, group in enumerate(groups, start=1):
                # 即使最后一组不满也进行拼接，防止漏掉结尾
                out_path = self.concat_images(group, f"grid_{idx}")
                image_paths.append(out_path)

            logger.info("📤 开始编码图像...")
            urls = self.encode_images_to_base64(image_paths)
            return urls
        except Exception as e:
            logger.error(f"发生错误：{str(e)}")
            raise ValueError(f"视频处理失败: {str(e)}")
