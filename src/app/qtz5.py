import sys
import random
import os
import re
from PyQt5.QtWidgets import QInputDialog, QDialog
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QMenu, QAction, QSystemTrayIcon
from PyQt5.QtGui import QMovie, QPixmap, QTransform, QIcon
from PyQt5.QtCore import (
    Qt, QTimer, QObject, pyqtSignal, pyqtSlot, QThread, QUrl
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from src.ui.duihua import ChatWindow
from src.ui.music_window import MusicWindow
from src.services.TTS_api import TTS

from config.file_config import (DOUYIN_DIR,BILIBILI_DIR)
from config.file_config import (IDLE_GIF,RUN_GIF,DRINK_GIF,DANCE_GIF,THANK_GIF,WHIRL_GIF,NO_GIF,DANCE1_GIF,HAPPLE_GIF,OK_GIF)


# ==================== 音乐目录配置 ====================
DOUYIN_DIR = DOUYIN_DIR
BILIBILI_DIR = BILIBILI_DIR

# 抖音权重增大的歌曲编号（概率增大）
WEIGHTED_SONGS = {
    97, 98, 107, 84, 85, 87, 66, 94, 90, 64, 47, 41, 29, 21, 14, 13,
    125, 123, 108, 93, 70, 53, 45, 24, 19, 12, 9, 100,
    137, 136, 135, 133, 132, 131, 130, 129, 99
}
# 补充 101 到 146
WEIGHTED_SONGS.update(range(101, 147))

# ==================== TTS 工作线程 ====================
class TTSWorker(QObject):
    finished = pyqtSignal(str)

    def __init__(self, tts_instance, text):
        super().__init__()
        self.tts = tts_instance
        self.text = text

    @pyqtSlot()
    def run(self):
        try:
            success = self.tts.synthesize(self.text)
            if success and hasattr(self.tts, 'last_filename'):
                self.finished.emit(self.tts.last_filename)
            else:
                self.finished.emit("")
        except Exception as e:
            print(f"TTS Worker 异常: {e}")
            self.finished.emit("")

# ==================== API 服务 ====================
class ApiService(QObject):
    response_ready = pyqtSignal(str)
    stream_chunk = pyqtSignal(str)
    stream_finish = pyqtSignal()

    def __init__(self, chat_stream_callback):
        super().__init__()
        self.chat_stream_callback = chat_stream_callback
        self.is_busy = False

    @pyqtSlot(str)
    def process_request(self, text):
        if self.is_busy:
            self.response_ready.emit("我正在思考上一个问题，请稍等一下~")
            return
        self.is_busy = True
        try:
            self.chat_stream_callback(
                text,
                lambda chunk: self.stream_chunk.emit(chunk)
            )
            self.stream_finish.emit()
        except Exception as e:
            self.response_ready.emit(f"哎呀，出错了：{str(e)}")
        finally:
            self.is_busy = False

# ==================== GIF 路径 ====================
IDLE_GIF    = IDLE_GIF
RUN_GIF     = RUN_GIF
DRINK_GIF   = DRINK_GIF
DANCE_GIF   = DANCE_GIF 

THANK_GIF   = THANK_GIF 
WHIRL_GIF   = WHIRL_GIF
NO_GIF      = NO_GIF
DANCE1_GIF  = DANCE1_GIF
HAPPLE_GIF  = HAPPLE_GIF
OK_GIF      = OK_GIF

RANDOM_GIFS = [DRINK_GIF, DANCE_GIF,THANK_GIF,HAPPLE_GIF,WHIRL_GIF,OK_GIF]

class DesktopPet(QWidget):
    request_api_signal = pyqtSignal(str)

    def __init__(self, ai_instance):
        super().__init__()
        self.ai = ai_instance
        self.chat_stream_callback = ai_instance.chat_stream
        self.chat_window = None
        self.music_window = None
        # 记录当前音乐窗口的模式（douyin/bilibili/all）
        self.current_music_mode = None

        self.tts = TTS(voice="zh-CN-XiaoyiNeural", rate="+6%", pitch="+10Hz")
        self.current_reply = ""
        self.tts_thread = None
        self.tts_worker = None
        self.current_tts_file = None

        self.tts_player = QMediaPlayer()
        self.tts_player.mediaStatusChanged.connect(self.on_tts_media_status)

        self.init_api_service()

        # 窗口基础设置
        # Qt.Tool 会隐藏任务栏图标，如果想在任务栏看到图标，可以去掉 Qt.Tool
        # 这里我们保留 Qt.Tool（不在任务栏显示），但通过系统托盘显示图标
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ⚠️ 修复：移除圆形遮罩，因为 GIF 本身带有绿幕去背遮罩，两者同时作用可能导致整个窗口不可见
        # set_rounded_corners(self, radius=15)
        
        # ✅ 新增：系统托盘图标，防止在后台运行找不到桌宠
        self.init_tray_icon()

        self.label = QLabel(self)
        self.drag_pos = None
        self.run_dir = random.choice([1, -1])
        self.flip = False
        self.is_manual_mode = False

        # 定时器
        self.run_timer = QTimer()
        self.run_timer.timeout.connect(self.update_run)
        self.action_timer = QTimer()
        self.action_timer.setSingleShot(True)
        self.action_timer.timeout.connect(self.goto_idle)
        self.auto_idle_timer = QTimer()
        self.auto_idle_timer.setSingleShot(True)
        self.auto_idle_timer.timeout.connect(self.play_random_gif)

        self.load_gif(IDLE_GIF)
        self.start_auto_idle()

    # -------------------- API 线程 --------------------
    def init_tray_icon(self):
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(IDLE_GIF)) # 默认使用待机GIF作为图标
        
        # 托盘菜单
        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {background-color:#1f1f1f;color:white;border-radius:9px;}
            QMenu::item {padding:7px 16px;border-radius:5px;}
            QMenu::item:selected {background-color:#4a86e8;}
        """)
        show_action = tray_menu.addAction("显示桌宠")
        show_action.triggered.connect(self.showNormal)
        
        quit_action = tray_menu.addAction("❌ 退出")
        quit_action.triggered.connect(self.quit_pet)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def init_api_service(self):
        self.api_thread = QThread()
        self.api_service = ApiService(self.chat_stream_callback)
        self.api_service.moveToThread(self.api_thread)
        self.api_service.stream_chunk.connect(self.on_api_stream_chunk)
        self.api_service.stream_finish.connect(self.on_api_stream_finish)
        self.api_service.response_ready.connect(self.on_api_response)
        self.request_api_signal.connect(self.api_service.process_request)
        self.api_thread.start()

    # -------------------- 聊天窗口 --------------------
    def open_chat(self):
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.action_timer.stop()
        self.run_timer.stop()

        if self.chat_window is not None:
            if self.chat_window.isVisible():
                self.chat_window.hide()
            else:
                self.update_chat_position()
                self.chat_window.show()
        else:
            memory = self.ai.load_memory()
            recent = memory.get("recent_messages", [])
            pairs = []
            i = len(recent) - 1
            while i >= 0 and len(pairs) < 5:
                if recent[i]["role"] == "assistant":
                    if i - 1 >= 0 and recent[i-1]["role"] == "user":
                        pairs.append((recent[i-1], recent[i]))
                        i -= 2
                    else:
                        break
                elif recent[i]["role"] == "user":
                    i -= 1
                else:
                    i -= 1
            pairs.reverse()
            history = []
            for u_msg, a_msg in pairs:
                history.append(u_msg)
                history.append(a_msg)

            self.chat_window = ChatWindow(self.send_api_request, history=history, parent=self)
            self.chat_window.closed.connect(self.on_chat_closed)
            self.update_chat_position()
            self.chat_window.show()

    def hide_chat(self):
        if self.chat_window:
            self.chat_window.hide()

    def close_chat(self):
        if self.chat_window:
            self.chat_window.close()
            self.chat_window = None

    def update_chat_position(self):
        if self.chat_window:
            x = self.x() + (self.width() - self.chat_window.width()) // 2
            y = self.y() + self.height() + 10
            self.chat_window.move(x, y)

    def on_chat_closed(self):
        self.chat_window = None
        self.goto_idle()

    # -------------------- 音乐窗口（核心修复：切换显示/隐藏） --------------------
    def open_music(self):
        """右键菜单触发，显示二级菜单"""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {background-color:#1f1f1f;color:white;border-radius:9px;}
            QMenu::item {padding:7px 16px;border-radius:5px;}
            QMenu::item:selected {background-color:#4a86e8;}
        """)
        action_douyin = menu.addAction("🎵 抖音热歌")
        action_bili = menu.addAction("🎵 B站热歌")
        action_all = menu.addAction("🎵 全部随机50首")
        online_action = menu.addAction("在线搜索音乐")
        action = menu.exec_(self.cursor().pos())

        if action == action_douyin:
            self._open_music_with_mode("douyin")
        elif action == action_bili:
            self._open_music_with_mode("bilibili")
        elif action == action_all:
            self._open_music_with_mode("all")
        elif action == online_action:
            self.open_online_music()

    # ========== 核心修复：相同模式切换显示/隐藏 ==========
    def _open_music_with_mode(self, mode):
        """根据模式构建播放列表并打开音乐窗口"""
        # 1. 已有音乐窗口的情况
        if self.music_window is not None:
            # 相同模式：切换显示/隐藏状态
            if self.current_music_mode == mode:
                if self.music_window.isVisible():
                    # 窗口已显示 → 隐藏（音乐继续播放）
                    self.music_window.hide()
                else:
                    # 窗口已隐藏 → 显示
                    self.music_window.show()
                    self.update_music_position()
                return
            # 不同模式：先停止旧窗口的音频，再关闭
            self.music_window.stop_play()
            self.music_window.close()
            self.music_window = None

        # 2. 构建播放列表（原有逻辑不变）
        playlist_urls = []
        if mode == "douyin":
            playlist_urls = self._get_song_urls_from_dir(DOUYIN_DIR)
        elif mode == "bilibili":
            playlist_urls = self._get_song_urls_from_dir(BILIBILI_DIR)
        elif mode == "all":
            # 抖音歌曲（带权重） + B站歌曲（权重1）
            douyin_songs = self._get_song_files_with_weight(DOUYIN_DIR)
            bili_songs = self._get_song_files_with_weight(BILIBILI_DIR, default_weight=1)
            all_candidates = douyin_songs + bili_songs
            if not all_candidates:
                return
            # 加权随机抽取最多50首（不重复）
            k = min(50, len(all_candidates))
            if k == 0:
                return
            # 分离文件和权重
            files = [item[0] for item in all_candidates]
            weights = [item[1] for item in all_candidates]
            selected_files = self._weighted_sample(files, weights, k)
            # 转换为完整 URL
            playlist_urls = [QUrl.fromLocalFile(os.path.abspath(f)).toString() for f in selected_files]
        else:
            return

        if not playlist_urls:
            return

        # 3. 准备打开新窗口
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.action_timer.stop()
        self.run_timer.stop()

        # 4. 创建新窗口并记录当前模式
        self.music_window = MusicWindow(parent=self, playlist=playlist_urls)
        self.current_music_mode = mode
        self.music_window.closed.connect(self.on_music_closed)
        self.update_music_position()
        self.music_window.show()
    def open_online_music(self):
        """打开在线搜索播放器，复用原有的音乐窗口逻辑"""
        # 1. 检查是否已经存在音乐窗口
        if self.music_window is not None:
            # 如果当前正是“在线搜索”模式，则切换显示/隐藏
            if self.current_music_mode == "online":
                if self.music_window.isVisible():
                    self.music_window.hide()
                else:
                    self.music_window.show()
                    self.update_music_position()
                return
            # 如果当前是“抖音/B站”模式，先停止并关闭旧窗口
            self.music_window.stop_play()
            self.music_window.close()
            self.music_window = None

        # 2. 暂停桌宠的随机动作
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.action_timer.stop()
        self.run_timer.stop()
        
        # 3. 实例化新版播放器（传入空列表以供搜索）

        self.music_window = MusicWindow(parent=self, playlist=[])
        
        # 4. 记录模式，并绑定原有的事件逻辑
        self.current_music_mode = "online"
        self.music_window.closed.connect(self.on_music_closed)
        
        # 5. 更新位置并显示
        self.update_music_position()
        self.music_window.show()
  
    @staticmethod
    def _get_song_urls_from_dir(directory):
        """从目录读取所有 mp3 文件，返回完整 file:// URL 列表"""
        if not os.path.isdir(directory):
            print(f"目录不存在: {directory}")
            return []
        urls = []
        for f in os.listdir(directory):
            if f.lower().endswith('.mp3'):
                full_path = os.path.abspath(os.path.join(directory, f))
                urls.append(QUrl.fromLocalFile(full_path).toString())
        return urls
    @staticmethod
    def _extract_song_number(filename):
        """从文件名中提取数字（如 '97.mp3' 或 '97_歌曲名.mp3'）"""
        match = re.search(r'\b(\d+)\b', filename)
        if match:
            return int(match.group(1))
        return None

    def _get_song_files_with_weight(self, directory, default_weight=1):
        """
        返回列表，每个元素为 (绝对路径, 权重)
        对于抖音目录，如果歌曲编号在 WEIGHTED_SONGS 中，权重设为 10（可调）
        """
        if not os.path.isdir(directory):
            return []
        result = []
        for f in os.listdir(directory):
            if f.lower().endswith('.mp3'):
                full_path = os.path.abspath(os.path.join(directory, f))
                weight = default_weight
                # 仅对抖音目录（且指定歌曲）增大权重
                if directory == DOUYIN_DIR:
                    num = self._extract_song_number(f)
                    if num is not None and num in WEIGHTED_SONGS:
                        weight = 10   # 概率提升10倍
                result.append((full_path, weight))
        return result

    @staticmethod
    def _weighted_sample(population, weights, k):
        """不放回加权抽样，返回 k 个元素列表"""
        if k <= 0 or not population:
            return []
        # 复制列表，避免修改原数据
        items = list(population)
        w = list(weights)
        selected = []
        for _ in range(min(k, len(items))):
            total = sum(w)
            if total == 0:
                break
            r = random.uniform(0, total)
            acc = 0
            for i, weight in enumerate(w):
                acc += weight
                if r <= acc:
                    selected.append(items.pop(i))
                    w.pop(i)
                    break
        return selected

    def hide_music(self):
        if self.music_window:
            self.music_window.hide()

    def close_music(self):
        if self.music_window:
            self.music_window.stop_play()
            self.music_window.close()
            self.music_window = None
            self.current_music_mode = None

    def update_music_position(self):
        if self.music_window:
            x = self.x() + (self.width() - self.music_window.width()) // 2
            y = self.y() + self.height() + 10
            self.music_window.move(x, y)

    def on_music_closed(self):
        self.music_window = None
        self.current_music_mode = None
        self.goto_idle()

    # -------------------- API 流式回调 --------------------
    def send_api_request(self, text):
        self.current_reply = ""
        self.request_api_signal.emit(text)

    def on_api_stream_chunk(self, chunk):
        self.current_reply += chunk
        if self.chat_window:
            self.chat_window.add_bot_chunk(chunk)

    def on_api_stream_finish(self):
        if self.chat_window:
            self.chat_window.finish_bot_message()
        if self.current_reply.strip():
            self.play_tts(self.current_reply)

    def on_api_response(self, reply):
        if self.chat_window:
            self.chat_window.add_bot_message(reply)
        if reply.strip():
            self.play_tts(reply)

    # -------------------- TTS 播放控制 --------------------
    def stop_current_tts(self):
        if self.tts_player.state() == QMediaPlayer.PlayingState:
            self.tts_player.stop()
        if self.current_tts_file and os.path.exists(self.current_tts_file):
            try:
                os.remove(self.current_tts_file)
                print(f"[TTS] 已清理旧文件: {self.current_tts_file}")
            except Exception as e:
                print(f"[TTS] 清理旧文件失败: {e}")
            self.current_tts_file = None

    def play_tts(self, text):
        self.stop_current_tts()
        if self.tts_thread and self.tts_thread.isRunning():
            self.tts_thread.requestInterruption()
            self.tts_thread.quit()
            self.tts_thread.wait(500)
        self.tts_thread = QThread()
        self.tts_worker = TTSWorker(self.tts, text)
        self.tts_worker.moveToThread(self.tts_thread)
        self.tts_thread.started.connect(self.tts_worker.run)
        self.tts_worker.finished.connect(self.on_tts_finished)
        self.tts_thread.finished.connect(self.tts_worker.deleteLater)
        self.tts_thread.finished.connect(self.tts_thread.deleteLater)
        self.tts_thread.start()

    def on_tts_finished(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return
        self.current_tts_file = file_path
        self.tts_player.setMedia(
            QMediaContent(QUrl.fromLocalFile(os.path.abspath(file_path)))
        )
        self.tts_player.play()

    def on_tts_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.current_tts_file and os.path.exists(self.current_tts_file):
                try:
                    os.remove(self.current_tts_file)
                    print(f"[TTS] 已删除播放完的文件: {self.current_tts_file}")
                except Exception as e:
                    print(f"[TTS] 删除失败: {e}")
                self.current_tts_file = None

    # -------------------- 宠物动作 --------------------
    def start_running(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.action_timer.stop()
        self.run_dir = random.choice([1, -1])
        self.load_gif(RUN_GIF, flip=(self.run_dir == 1))
        self.run_timer.start(30)
        QTimer.singleShot(7000, self.goto_idle)

    def start_drink(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(DRINK_GIF)
        self.action_timer.start(4000)

    def start_dance(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(DANCE_GIF)
        self.action_timer.start(4000)

    def start_thank(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(THANK_GIF)#这个是谢谢的那个表情包
        #播放时间
        self.action_timer.start(3000)


    def start_whirl(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(WHIRL_GIF)
        self.action_timer.start(4000)

    def start_no(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(NO_GIF)
        self.action_timer.start(4000)

    def start_dance1(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(DANCE1_GIF)
        self.action_timer.start(4000)


    def start_happle(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(HAPPLE_GIF)
        self.action_timer.start(4000)

    def start_ok(self):
        self.hide_chat()
        self.hide_music()
        self.is_manual_mode = True
        self.auto_idle_timer.stop()
        self.run_timer.stop()
        self.load_gif(OK_GIF)
        self.action_timer.start(4000)


    def goto_idle(self):
        self.hide_chat()
        self.hide_music()
        self.run_timer.stop()
        self.action_timer.stop()
        self.load_gif(IDLE_GIF)
        self.start_auto_idle()

    # -------------------- 拖拽 --------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(e.globalPos() - self.drag_pos)
            self.update_chat_position()
            self.update_music_position()

    def mouseReleaseEvent(self, e):
        self.drag_pos = None

    # -------------------- GIF 播放 --------------------
    def load_gif(self, path, flip=False):
        self.flip = flip
        if hasattr(self, 'movie'):
            self.movie.stop()
            del self.movie
        self.movie = QMovie(path)
        self.movie.frameChanged.connect(self.update_frame)
        self.movie.start()

    def update_frame(self):
        pix = self.movie.currentPixmap()
        if self.flip:
            pix = pix.transformed(QTransform().scale(-1, 1))
        mask = pix.createMaskFromColor(Qt.green, Qt.MaskInColor)
        pix.setMask(mask)
        self.label.setPixmap(pix)
        self.label.resize(pix.size())
        self.resize(pix.size())

    def start_auto_idle(self):
        self.is_manual_mode = False
        self.auto_idle_timer.start(15000)

    def play_random_gif(self):
        if self.is_manual_mode:
            return
        gif = random.choice(RANDOM_GIFS)
        self.load_gif(gif)
        self.action_timer.start(5000)

    # -------------------- 跑步 --------------------
    def update_run(self):
        screen = QApplication.desktop().availableGeometry()
        w = self.frameGeometry()
        speed = 3
        if w.left() <= screen.left():
            self.run_dir = 1
            self.load_gif(RUN_GIF, flip=True)
        elif w.right() >= screen.right():
            self.run_dir = -1
            self.load_gif(RUN_GIF, flip=False)
        self.move(self.x() + self.run_dir * speed, self.y())

    # -------------------- 右键菜单 --------------------
    def contextMenuEvent(self, e):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {background-color:#1f1f1f;color:white;border-radius:9px;}
            QMenu::item {padding:7px 16px;border-radius:5px;}
            QMenu::item:selected {background-color:#4a86e8;}
        """)
        # 音乐二级菜单
        music_menu = menu.addMenu("🎵 音乐")
        music_menu.addAction("抖音热歌")
        music_menu.addAction("B站热歌")
        music_menu.addAction("全部随机50首")
        music_menu.addSeparator()
        music_menu.addAction("在线搜索音乐")
        music_menu.triggered.connect(self._on_music_submenu)

        menu.addAction("💬 聊天", self.open_chat)
        menu.addSeparator()
        menu.addAction("🏃 爱心流动", self.start_running)
        menu.addAction("😄 略略略", self.start_drink)
        menu.addAction("🤯 哇~你好厉害呀", self.start_dance)

        menu.addAction("🙏谢谢",self.start_thank)
        menu.addAction("😄转圈",self.start_whirl)
        menu.addAction("❌不要啦",self.start_no)
        menu.addAction("💃跳舞啦",self.start_dance1)
        menu.addAction("🐷装货高冷",self.start_happle)
        menu.addAction("😄OK",self.start_ok)




        menu.addAction("😴 待机", self.goto_idle)
        menu.addSeparator()
        menu.addAction("❌ 退出", self.quit_pet)

        menu.exec_(e.globalPos())

    def _on_music_submenu(self, action):
        text = action.text()
        if text == "抖音热歌":
            self._open_music_with_mode("douyin")
        elif text == "B站热歌":
            self._open_music_with_mode("bilibili")
        elif text == "全部随机50首":
            self._open_music_with_mode("all")
        elif text == "在线搜索音乐":
            self.open_online_music()

    # -------------------- 退出程序 --------------------
    def quit_pet(self):
        self.stop_current_tts()
        if self.tts_thread and self.tts_thread.isRunning():
            self.tts_thread.requestInterruption()
            self.tts_thread.quit()
            self.tts_thread.wait(1000)
        # 退出时停止音乐并关闭窗口
        self.close_music()
        self.close_chat()
        if hasattr(self, 'api_thread') and self.api_thread.isRunning():
            self.api_thread.quit()
            self.api_thread.wait()
        self.run_timer.stop()
        self.action_timer.stop()
        self.auto_idle_timer.stop()
        self.close()
        sys.exit(0)