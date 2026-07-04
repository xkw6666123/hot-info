#!/usr/bin/env python3
"""测试：Playwright 主动截获抖音音频 URL"""
import subprocess, time, os, json

PCLI = "playwright-cli"

# Kill existing browser
subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"], capture_output=True)
time.sleep(1)

# Test one video
url = "https://www.douyin.com/video/7646893632482760433"

# Open page
print("Opening page...")
r = subprocess.run(
    ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{url}\""],
    capture_output=True, timeout=30, text=True
)
print("Open result:", r.stdout[:200] if r.stdout else r.stderr[:200])
time.sleep(8)

# Get network requests
print("\nNetwork requests:")
r = subprocess.run(
    ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} requests"],
    capture_output=True, timeout=15, text=True
)

# Filter for audio/video URLs
lines = r.stdout.split("\n")
audio_lines = [l for l in lines if "audio" in l.lower() or "mp4" in l.lower() or "vod" in l.lower()]
print(f"Total requests: {len(lines)}, audio/video: {len(audio_lines)}")
for l in audio_lines[:20]:
    print(f"  {l[:200]}")

# Try to click the play button  
print("\nTrying to click video...")
r = subprocess.run(
    ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} click \"video\""],
    capture_output=True, timeout=10, text=True
)
time.sleep(3)

# Check again
r = subprocess.run(
    ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} requests"],
    capture_output=True, timeout=15, text=True
)
lines = r.stdout.split("\n")
audio_lines = [l for l in lines if "audio" in l.lower() or "douyinvod" in l.lower() or "media-audio" in l.lower()]
print(f"After click: audio lines: {len(audio_lines)}")
for l in audio_lines[:10]:
    print(f"  {l[:200]}")

subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} close"], capture_output=True)
