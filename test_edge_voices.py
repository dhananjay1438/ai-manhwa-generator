import asyncio
import os
from pathlib import Path
from core.audio.edge_tts import EdgeTTSProvider

async def test_edge_voices():
    print("--- Edge TTS Voice Testing Tool ---")
    
    # Common high-quality English voices
    voices = [
        "en-GB-RyanNeural",
        "en-GB-SoniaNeural",
        "en-US-GuyNeural",
        "en-US-AriaNeural",
        "en-AU-WilliamNeural",
        "en-AU-NatashaNeural"
    ]
    
    test_text = "What's up everyone! Welcome back to the channel. Today we're looking at the top 10 strongest hunters in Solo Leveling. Don't forget to like and subscribe!"
    
    provider = EdgeTTSProvider()
    
    test_dir = Path("edge_voice_tests")
    test_dir.mkdir(exist_ok=True)
    
    for voice_name in voices:
        output_file = test_dir / f"edge_{voice_name.lower()}.mp3"
        print(f"Generating sample for: {voice_name}...")
        
        # We need to pass the voice parameter which we added to generate_audio
        await provider.generate_audio(test_text, str(output_file), voice=voice_name)

    print(f"\nDone! Samples generated in: {test_dir.resolve()}")

if __name__ == "__main__":
    asyncio.run(test_edge_voices())
