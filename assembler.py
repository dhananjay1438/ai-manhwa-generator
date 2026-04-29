import os
import glob
import ffmpeg
from typing import List

class FFmpegAssembler:
    def __init__(self, episode_id: str, assets_dir: str, enable_subtitles: bool = True):
        self.episode_id = episode_id
        self.assets_dir = assets_dir
        self.images_dir = os.path.join(assets_dir, "images")
        self.audio_path = os.path.join(assets_dir, "audio.mp3")
        self.subtitle_path = os.path.join(assets_dir, "subtitles.ass")
        self.enable_subtitles = enable_subtitles
        self.output_path = f"ep_{episode_id}_final.mp4"

    def _get_audio_duration(self) -> float:
        """Probe the audio file to get its duration."""
        try:
            probe = ffmpeg.probe(self.audio_path)
            duration = float(probe['format']['duration'])
            return duration
        except ffmpeg.Error as e:
            print(f"Error probing audio: {e.stderr.decode()}")
            # Fallback duration if probe fails
            return 10.0

    def assemble(self):
        """Assembles the final video using ffmpeg-python."""
        if os.path.exists(self.output_path):
            print(f"Skipping assembly, {self.output_path} already exists.")
            return self.output_path

        # 1. Calculate image pacing
        audio_duration = self._get_audio_duration()
        image_files = sorted(glob.glob(os.path.join(self.images_dir, "*.png")))
        num_images = len(image_files)

        if num_images == 0:
            raise ValueError(f"No images found in {self.images_dir}")

        time_per_image = audio_duration / num_images
        fps = 30 # standard output fps
        frames_per_image = int(time_per_image * fps)

        # 2. Build input streams for each image with zoompan
        # zoompan: zoom in slowly to 1.05x over the duration of the image.
        video_streams = []
        for img in image_files:
            # We use format 'image2' and loop 1.
            # Then apply zoompan. Note: zoompan needs to output the exact number of frames
            # to match time_per_image.
            stream = ffmpeg.input(img)

            # zoompan equation: zoom='min(zoom+0.05/d,1.05)'
            # d is duration in frames.
            stream = stream.filter(
                'zoompan',
                z='min(zoom+0.05/%d,1.05)' % frames_per_image,
                d=frames_per_image,
                s='1080x1920', # ensuring consistent output size
                fps=fps
            )
            video_streams.append(stream)

        # 3. Concatenate all processed image streams
        video = ffmpeg.concat(*video_streams, v=1, a=0)

        # 4. Add ASS subtitles conditionally
        if self.enable_subtitles and os.path.exists(self.subtitle_path):
            video = video.filter('ass', self.subtitle_path)

        # 5. Bring in audio stream
        audio_stream = ffmpeg.input(self.audio_path)

        # 6. Output
        try:
            out = ffmpeg.output(
                video,
                audio_stream,
                self.output_path,
                vcodec='libx264',
                acodec='aac',
                pix_fmt='yuv420p',
                shortest=None # Ensures video stops when shortest stream (audio) ends
            )
            out.run(overwrite_output=True, quiet=True)
            print(f"Successfully created {self.output_path}")
        except ffmpeg.Error as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            raise

        return self.output_path
