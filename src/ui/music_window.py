import os
import json
from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSignal, pyqtSlot  # 确保导入了 pyqtSlot
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel


from src.services.music_api import search_music
from src.utils.painEvernts import set_rounded_corners   # 导入圆角工具


from config.file_config import music_html_a1
class MusicBridge(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window

    @pyqtSlot(str)
    def searchMusic(self, keyword):
        """接收前端传来的关键词并进行在线搜索"""
        if not keyword.strip():
            return
            
        try:
            # 引入你写好的搜索核心方法
            
            songs = search_music(keyword, n=6) # 默认搜索6首
            
            # 将搜索到的完整歌曲列表转换为 JSON 传回前端
            songs_json = json.dumps(songs, ensure_ascii=False)
            
            # 直接调用前端 music.html 中封装好的 window.setPlaylist 方法
            self.window.web_view.page().runJavaScript(f"window.setPlaylist({songs_json});")
        except Exception as e:
            print(f"后台搜索音乐失败: {e}")


class MusicWindow(QDialog):
    closed = pyqtSignal()

    def __init__(self, parent=None, playlist=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 适当加高一点高度，留出搜索框的空间（比如从 450 加到 500）
        self.setFixedSize(300, 500)

        set_rounded_corners(self, radius=15)

        self.playlist = playlist if playlist is not None else []
        self.playlist_json = json.dumps(self.playlist, ensure_ascii=False)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView(self)
        self.web_view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        self.web_view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        
        # 👇👇👇 加上这一行：关闭“必须由用户手势触发才能播放”的限制 👇👇👇
        self.web_view.settings().setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        
        self.web_view.page().setBackgroundColor(Qt.transparent)
        # ==================== 核心：建立 QWebChannel 通信桥梁 ====================
        self.channel = QWebChannel()
        self.bridge = MusicBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        # =====================================================================

        # 加载本地 HTML
        # 必须使用绝对路径，否则 Chromium 会报 ERR_FILE_NOT_FOUND
        html_path = os.path.abspath(music_html_a1)
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

        self.web_view.loadFinished.connect(self._inject_playlist)
        layout.addWidget(self.web_view)

    def _inject_playlist(self, ok):
        """页面加载完成后注入初始播放列表"""
        if not ok:
            return
        if self.playlist:
            js_code = f"window.INIT_PLAYLIST = {self.playlist_json};"
            js_code += "if(typeof initPlayer === 'function') initPlayer();"
            self.web_view.page().runJavaScript(js_code)

    def stop_play(self):
        """停止当前窗口的所有音频播放"""
        stop_js = """
            try {
                const audio = document.getElementById('audioPlayer');
                if (audio && !audio.paused) {
                    audio.pause();
                    audio.currentTime = 0;
                }
                const musicCard = document.getElementById('musicCard');
                if (musicCard) {
                    musicCard.classList.remove('rotate');
                }
                const playPath = document.getElementById('playPath');
                if (playPath) {
                    playPath.setAttribute('d', 'M8 5v14l11-7z');
                }
            } catch (e) {
                console.log('停止播放失败:', e);
            }
        """
        self.web_view.page().runJavaScript(stop_js)