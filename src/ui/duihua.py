from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QObject, pyqtSlot, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
import os
import json
from config.file_config import chat_html_a1

from src.utils.painEvernts import set_rounded_corners   # 导入圆角工具


class ChatBridge(QObject):
    send_message = pyqtSignal(str)
    settings_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def sendMsg(self, text):
        self.send_message.emit(text)

    @pyqtSlot(str)
    def settings(self, text):
        self.settings_changed.emit(text)


class ChatWindow(QDialog):
    closed = pyqtSignal()

    def __init__(self, chat_callback, history=None, parent=None):
        super().__init__(parent)#- 保存外面传进来的聊天处理函数和历史记录- 设置这个聊天窗口的外观和大小
        self.chat_callback = chat_callback
        self.history = history or []
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(300, 300)
        self.setMaximumSize(800, 700)
        self.resize(380, 420)

        # 应用圆角（半径 15px）
        set_rounded_corners(self, radius=15)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.NoContextMenu)

        # 关键：让 WebView 背景透明，以便窗口透明度生效
        self.web_view.setStyleSheet("background: transparent;")
        self.web_view.page().setBackgroundColor(Qt.transparent)

        # 启用本地存储和缓存清除
        profile = self.web_view.page().profile()
        profile.clearHttpCache()
        profile.clearAllVisitedLinks()

        self.web_view.settings().setAttribute(
            self.web_view.settings().WebAttribute.Accelerated2dCanvasEnabled, True
        )
        self.web_view.settings().setAttribute(
            self.web_view.settings().WebAttribute.WebGLEnabled, True
        )

        self.bridge = ChatBridge()
        self.bridge.send_message.connect(self.on_message_received)
        self.bridge.settings_changed.connect(self.on_settings_received)

        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # 加载 HTML，添加随机参数防止缓存
        html_path = os.path.abspath(chat_html_a1)
        url = QUrl.fromLocalFile(html_path)
        url.setQuery(f"_={os.urandom(4).hex()}")
        self.web_view.load(url)
        self.web_view.loadFinished.connect(self.on_page_loaded)

        layout.addWidget(self.web_view)

    def on_page_loaded(self, ok):
        """页面加载完成后，设置透明背景 + 加载历史消息"""
        if ok:
            # 再次确保网页根元素背景透明（额外保险）
            self.web_view.page().runJavaScript("""
                document.documentElement.style.backgroundColor = 'transparent';
                document.body.style.backgroundColor = 'transparent';
            """)
        if not ok or not self.history:
            return

        self._history_json = json.dumps(self.history, ensure_ascii=False)
        self._load_attempts = 0
        self._try_load_history()

    def _try_load_history(self):
        """轮询检查 loadHistory 函数是否存在，最多尝试 30 次（约 3 秒）"""
        self._load_attempts += 1
        if self._load_attempts > 30:
            print("[ChatWindow] 加载历史消息超时，放弃")
            return

        self.web_view.page().runJavaScript(
            "typeof loadHistory === 'function'",
            self._on_load_history_ready
        )

    def _on_load_history_ready(self, is_ready):
        if is_ready:
            self.web_view.page().runJavaScript(f"loadHistory({self._history_json})")
            print("[ChatWindow] 历史消息加载成功")
        else:
            QTimer.singleShot(100, self._try_load_history)

    def on_message_received(self, text):
        if not text.strip():
            return
        self.chat_callback(text)

    def on_settings_received(self, text):
        try:
            commands = text.split(';')
            for cmd in commands:
                cmd = cmd.strip()
                if not cmd:
                    continue
                if cmd.startswith("opacity:"):
                    val = float(cmd.split(":")[1])
                    self.setWindowOpacity(val)
                elif cmd.startswith("size:"):
                    w, h = map(float, cmd.split(":")[1].split(","))
                    w = max(300, min(800, int(w)))
                    h = max(300, min(700, int(h)))
                    self.resize(w, h)
                elif cmd.startswith("offset:"):
                    dx, dy = map(float, cmd.split(":")[1].split(","))
                    self.move(self.x() + int(dx), self.y() + int(dy))
        except Exception as e:
            print("处理设置命令失败:", e)

    def add_bot_chunk(self, chunk):
        if not chunk:
            return
        safe_chunk = json.dumps(chunk, ensure_ascii=False)
        self.web_view.page().runJavaScript(f"addBotChunk({safe_chunk})")

    def finish_bot_message(self):
        self.web_view.page().runJavaScript("finishBotMessage()")

    def add_bot_message(self, reply):
        if not reply:
            return
        safe_reply = json.dumps(reply, ensure_ascii=False)
        self.web_view.page().runJavaScript(f"addBotMessage({safe_reply})")

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)