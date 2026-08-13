import subprocess
import os

os.chdir(r"F:\code\MediaRefitAgent")

input_file = "video/seg0002.mp4"
output_file = "video/output_seg0002_pan.mp4"

# smooth_sine 模式：30秒周期（更慢，不晕）
x_expr = "480+480*sin(2*3.14159*t/30)"

vf = f"crop=ih*9/16:ih:{x_expr}:0,scale=1080:1920,setsar=1:1"

cmd = [
    "ffmpeg", "-i", input_file,
    "-vf", vf,
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
    "-y", output_file
]

print("Generating pan video with 30s period...")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("Error:", result.stderr[-400:])
else:
    print("Success:", output_file)