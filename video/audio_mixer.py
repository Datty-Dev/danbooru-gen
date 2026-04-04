#!/usr/bin/env python3
"""Audio Mixer — background music + sound effects for MangaCut.

Uses ffmpeg to mix audio into video.
"""
import os
import subprocess
import shutil

def get_ffmpeg():
    """Find ffmpeg binary."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        # Try imageio-ffmpeg
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except:
            pass
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found. Install ffmpeg or imageio-ffmpeg.")
    return ffmpeg


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds."""
    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg, "-i", audio_path,
        "-show_entries", "format=duration",
        "-v", "quiet",
        "-of", "csv=p=0",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0


def mix_background_music(video_path, audio_path, output_path, volume=0.8, fade_in=0.5, fade_out=0.5):
    """Mix background music into a video.

    Args:
        video_path: path to input video (no audio)
        audio_path: path to audio file (mp3/wav)
        output_path: path to output video with audio
        volume: audio volume (0.0-1.0)
        fade_in: fade in duration in seconds
        fade_out: fade out duration in seconds
    """
    ffmpeg = get_ffmpeg()
    
    # Get video duration
    probe_cmd = [
        ffmpeg, "-i", video_path,
        "-show_entries", "format=duration",
        "-v", "quiet",
        "-of", "csv=p=0",
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        video_duration = float(result.stdout.strip())
    except:
        video_duration = 0

    # Build audio filter
    audio_filters = []
    
    # Volume
    audio_filters.append(f"volume={volume}")
    
    # Fade in/out
    if fade_in > 0:
        audio_filters.append(f"afade=t=in:st=0:d={fade_in}")
    if fade_out > 0 and video_duration > 0:
        fade_start = max(0, video_duration - fade_out)
        audio_filters.append(f"afade=t=out:st={fade_start}:d={fade_out}")
    
    filter_str = ",".join(audio_filters)
    
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex", f"[1:a]{filter_str}[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def add_sfx_at_time(video_path, sfx_path, output_path, timestamp, volume=1.0):
    """Add a sound effect at a specific timestamp.

    Args:
        video_path: path to input video
        sfx_path: path to sound effect file
        output_path: path to output video
        timestamp: time in seconds to play the SFX
        volume: SFX volume (0.0-1.0)
    """
    ffmpeg = get_ffmpeg()
    
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", sfx_path,
        "-filter_complex",
        f"[1:a]adelay={int(timestamp * 1000)}|{int(timestamp * 1000)},volume={volume}[sfx];"
        f"[0:a][sfx]amix=inputs=2:duration=first[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def mix_audio(video_path, output_path, background_music=None, sfx_list=None, 
              music_volume=0.8, fade_in=0.5, fade_out=0.5):
    """Full audio mixing pipeline.

    Args:
        video_path: path to input video (no audio)
        output_path: path to final output video
        background_music: path to background music file (optional)
        sfx_list: list of {"path": str, "time": float, "volume": float} (optional)
        music_volume: background music volume
        fade_in: music fade in seconds
        fade_out: music fade out seconds
    """
    ffmpeg = get_ffmpeg()
    temp_dir = os.path.dirname(output_path)
    
    if not background_music and not sfx_list:
        # No audio — just copy
        shutil.copy2(video_path, output_path)
        return output_path
    
    current = video_path
    
    # Add background music first
    if background_music and os.path.exists(background_music):
        temp_music = os.path.join(temp_dir, "_temp_music.mp4")
        mix_background_music(current, background_music, temp_music, 
                           volume=music_volume, fade_in=fade_in, fade_out=fade_out)
        current = temp_music
    
    # Add SFX one by one
    if sfx_list:
        for i, sfx in enumerate(sfx_list):
            sfx_path = sfx.get("path")
            sfx_time = sfx.get("time", 0)
            sfx_vol = sfx.get("volume", 1.0)
            
            if not os.path.exists(sfx_path):
                continue
            
            temp_sfx = os.path.join(temp_dir, f"_temp_sfx_{i}.mp4")
            add_sfx_at_time(current, sfx_path, temp_sfx, sfx_time, volume=sfx_vol)
            
            # Cleanup previous temp
            if current != video_path:
                os.remove(current)
            current = temp_sfx
    
    # Move final to output
    if current != output_path:
        shutil.move(current, output_path)
    
    # Cleanup any remaining temps
    for f in os.listdir(temp_dir):
        if f.startswith("_temp_"):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass
    
    return output_path


# Transition SFX mapping
TRANSITION_SFX = {
    "whip_pan": "whoosh",
    "whip_tilt": "whoosh",
    "screen_shake": "impact",
    "hard_cut": "cut",
    "fade_black": None,
    "cross_dissolve": None,
    "zoom_in": "whoosh",
    "zoom_out": "whoosh",
    "slide_left": "whoosh",
    "slide_right": "whoosh",
    "slide_up": "whoosh",
    "slide_down": "whoosh",
    "glitch": "glitch",
    "page_turn": "page",
}


if __name__ == "__main__":
    print("Audio mixer ready")
    print(f"ffmpeg: {get_ffmpeg()}")
    print(f"Transition SFX map: {len(TRANSITION_SFX)} transitions")
