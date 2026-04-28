import json
from typing import List, Dict

class SubtitleGenerator:
    """
    Converts Whisper word-level JSON into an ASS file with a 'popping' effect.
    Active word is Yellow & 120% scale, inactive words in sentence are White & 100%.
    """
    def __init__(self, transcription_path: str, output_ass_path: str):
        self.transcription_path = transcription_path
        self.output_ass_path = output_ass_path

    def _format_time(self, seconds: float) -> str:
        """Converts seconds into ASS time format: H:MM:SS.cs"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def generate(self):
        with open(self.transcription_path, 'r', encoding='utf-8') as f:
            words = json.load(f)

        if not words:
            # Handle empty transcription
            with open(self.output_ass_path, "w", encoding="utf-8") as f:
                f.write("[Script Info]\nTitle: Default\nScriptType: v4.00+\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            return self.output_ass_path

        # Standard ASS Header
        ass_lines = [
            "[Script Info]",
            "Title: Popping Subtitles",
            "ScriptType: v4.00+",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            # Base style: Bold, Center-Middle aligned (Alignment 5), Margin adjusts vertical position
            "Style: Default,Arial,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,5,10,10,200,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        # Simplified grouping: every N words becomes a "sentence" for visual display.
        # In a robust implementation, you'd look for punctuation.
        words_per_group = 5

        for i in range(0, len(words), words_per_group):
            group = words[i:i+words_per_group]

            group_start = group[0]['start_time']
            group_end = group[-1]['end_time']

            # Create a dialogue line for EACH word in the group being the "active" word
            for idx, active_word_data in enumerate(group):
                start_t = self._format_time(active_word_data['start_time'])
                end_t = self._format_time(active_word_data['end_time'])

                # If we are at the end of the group, extend to the actual end time of the active word
                # Normally dialogue shows the whole group, but we want the highlighted word to update
                # at exactly its start/end times.

                text_parts = []
                for j, w_data in enumerate(group):
                    w_text = w_data['word'].strip()
                    if j == idx:
                        # Active word: Yellow (\c&H00FFFF&), 120% scale (\fs96 if base is 80)
                        text_parts.append(f"{{\\c&H00FFFF&\\fscx120\\fscy120}}{w_text}{{\\r}}")
                    else:
                        # Inactive word: White (\c&HFFFFFF&), 100% scale
                        text_parts.append(f"{{\\c&HFFFFFF&\\fscx100\\fscy100}}{w_text}{{\\r}}")

                full_text = " ".join(text_parts)
                dialogue_line = f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{full_text}"
                ass_lines.append(dialogue_line)

        with open(self.output_ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_lines))

        return self.output_ass_path
