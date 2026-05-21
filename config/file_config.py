import os
import sys

def get_resource_path(relative_path):
    """
    获取资源的绝对路径。
    在开发环境中，返回基于当前运行目录的路径；
    在 PyInstaller 打包后的环境中，返回基于 sys._MEIPASS（对于 onedir 模式通常是 _internal 目录）的路径。
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

MEMORY_FILE = get_resource_path("config/pet_memory.json")
DOUYIN_DIR = get_resource_path(r"src/assets/music/抖音")
BILIBILI_DIR = get_resource_path(r"src/assets/music/B站")

IDLE_GIF    = get_resource_path("src/assets/gif/lbxx/开头.gif")
RUN_GIF     = get_resource_path("src/assets/gif/lbxx/喜欢.gif")
DRINK_GIF   = get_resource_path("src/assets/gif/lbxx/略略略.gif")
DANCE_GIF   = get_resource_path("src/assets/gif/lbxx/哇.gif")
THANK_GIF   = get_resource_path("src/assets/gif/lbxx/谢谢.gif")
WHIRL_GIF   = get_resource_path("src/assets/gif/lbxx/转圈.gif") 
NO_GIF      = get_resource_path("src/assets/gif/lbxx/不要.gif")
DANCE1_GIF  = get_resource_path("src/assets/gif/lbxx/跳舞1.gif")
HAPPLE_GIF  = get_resource_path("src/assets/gif/lbxx/高冷.gif")
OK_GIF      = get_resource_path("src/assets/gif/lbxx/OK.gif")

chat_html_a1 = get_resource_path("src/router/chat.html")
music_html_a1  = get_resource_path("src/router/music.html")