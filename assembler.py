from pathlib import Path
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
import moviepy.video.fx as vfx
from logger import logger


class FFmpegAssembler:
    def __init__(self, episode_id: str, assets_dir: str, enable_subtitles: bool = True, output_path: str = None):
        self.episode_id = episode_id
        self.assets_dir = Path(assets_dir)
        self.images_dir = self.assets_dir / "images"
        self.audio_path = self.assets_dir / "audio.mp3"
        self.subtitle_path = self.assets_dir / "subtitles.ass"
        self.enable_subtitles = enable_subtitles
        if output_path:
            self.output_path = Path(output_path)
        else:
            self.output_path = Path(f"ep_{episode_id}_final.mp4")

    def assemble(self) -> str:
        """Assembles the final video using MoviePy with a progress bar."""
        if self.output_path.exists():
            logger.info("Skipping assembly, %s already exists.", self.output_path)
            return str(self.output_path)

        # 1. Load audio and images
        audio_clip = AudioFileClip(str(self.audio_path))
        image_files = sorted(self.images_dir.glob("*.png"))
        num_images = len(image_files)

        if num_images == 0:
            raise ValueError(f"No images found in {self.images_dir}")

        duration_per_image = audio_clip.duration / num_images
        
        clips = []
        for img_path in image_files:
            # Load image and set duration
            img_clip = ImageClip(str(img_path)).with_duration(duration_per_image)
            
            # Apply subtle zoom effect (Ken Burns)
            # Zoom from 1.0 to 1.05
            w, h = img_clip.size
            img_clip = img_clip.with_effects([
                vfx.Resize(lambda t: 1 + 0.05 * (t / duration_per_image)),
                vfx.Crop(x_center=w/2, y_center=h/2, width=w, height=h)
            ])
            
            clips.append(img_clip)

        # 2. Concatenate and attach audio
        video = concatenate_videoclips(clips, method="compose")
        video = video.with_audio(audio_clip)

        # 3. Handle subtitles (MoviePy 2.x style or via ffmpeg_params)
        # For ASS subtitles, it's often easiest to pass the filter to ffmpeg directly
        ffmpeg_params = []
        if self.enable_subtitles and self.subtitle_path.exists():
            # moviepy allows passing extra ffmpeg arguments
            # Note: The 'ass' filter in ffmpeg needs the path
            sub_path = str(self.subtitle_path).replace("\\", "/").replace(":", "\\:")
            ffmpeg_params = ["-vf", f"ass={sub_path}"]

        # 4. Write output with progress bar
        try:
            logger.info("Starting video assembly for %s", self.episode_id)
            video.write_videofile(
                str(self.output_path),
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                logger="bar",
                ffmpeg_params=ffmpeg_params
            )
            logger.info("Successfully created %s", self.output_path)
        except Exception as e:
            logger.error("Error during video assembly: %s", e)
            raise

        # Close clips to free resources
        audio_clip.close()
        video.close()
        for clip in clips:
            clip.close()

        return str(self.output_path)
