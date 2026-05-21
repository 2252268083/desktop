"""
桌宠 TTS 模块（稳定版）
-----------------------
- 文本清洗（移除 Markdown、颜文字）
- edge-tts 语音合成
- 自动重试 + 备用语音降级
- 每次生成唯一文件名，避免覆盖冲突
- 独立事件循环，防止多线程 asyncio 冲突
"""

import asyncio
import edge_tts
import re
import logging
import uuid
import os
import time

logger = logging.getLogger("TTS")


class TTS:
    """文本转语音工具类"""

    # 备用语音列表（按优先级）
    FALLBACK_VOICES = [
        "zh-CN-XiaoxiaoNeural",
        "zh-TW-HsiaoYuNeural",
    ]

    def __init__(self,
                 voice: str = "zh-CN-XiaoyiNeural",
                 rate: str = "+6%",
                 pitch: str = "+10Hz"):
        """
        :param voice: 首选语音名称
        :param rate:  语速，如 "-5%", "+10%"
        :param pitch: 音调，如 "+0Hz", "+10Hz"
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.last_filename = None   # 记录最近一次合成的文件名

    # ==================== 文本清洗（静态方法） ====================
    @staticmethod
    def clean(text: str) -> str:
        """
        移除 Markdown 符号、颜文字、思考过程及多余标点，让 TTS 朗读更自然
        """
        # 移除通过 API 输出的自定义思考过程
        text = re.sub(r'【思考过程开始】[\s\S]*?【思考过程结束】', '', text)
        # 移除部分模型自带的 <think>...</think> 标签内容
        text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        
        text = re.sub(r'\*+\s*(.*?)\s*\*+', r'\1', text)     # 粗体/斜体
        text = re.sub(r'\([\w\W]{1,10}\)', '', text)          # (QWQ) 等短颜文字
        text = re.sub(r'（[\w\W]{1,10}）', '', text)         # 中文括号颜文字
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'~{2,}', '~', text)
        text = re.sub(r'！+', '！', text)
        text = re.sub(r'？+', '？', text)
        text = re.sub(r'[ \t]+', ' ', text).strip()
        text = text.replace('*', '').replace('_', '')
        text = text.replace('【思考过程开始】', '').replace('【思考过程结束】', '')
        return text

    # ==================== 异步合成（内部） ====================
    async def _async_speak(self, text: str, voice: str) -> str:
        """
        单次合成，返回生成的临时文件名
        """
        filename = f"reply_{uuid.uuid4().hex[:8]}.mp3"
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=self.rate,
            pitch=self.pitch
        )
        await communicate.save(filename)
        self.last_filename = filename
        return filename

    # ==================== 同步接口（带重试 + 降级） ====================
    def synthesize(self, text: str) -> bool:
        """
        供子线程调用的同步方法。
        自动清洗文本、重试、降级到备用语音。
        成功返回 True，失败返回 False。
        合成后的文件名可通过 self.last_filename 获取。
        """
        text = self.clean(text)
        if not text.strip():
            logger.warning("清洗后文本为空，跳过 TTS")
            return False

        # 构建尝试列表（首选 + 备用，去重）
        voices_to_try = [self.voice]
        for v in self.FALLBACK_VOICES:
            if v not in voices_to_try:
                voices_to_try.append(v)

        for current_voice in voices_to_try:
            for attempt in range(2):   # 每个语音最多尝试 2 次
                try:
                    # 为每次尝试创建独立的事件循环，避免冲突
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self._async_speak(text, current_voice)
                        )
                    finally:
                        loop.close()
                    logger.info(f"✅ TTS 成功，语音: {current_voice}")
                    return True
                except Exception as e:
                    logger.warning(
                        f"⚠️ 尝试 {attempt+1}/2 失败 ({current_voice}): {e}"
                    )
                    time.sleep(0.3)   # 短暂等待后重试
            logger.info(f"↪️ 切换备用语音...")

        logger.error("❌ 所有语音均失败，TTS 放弃")
        return False

    # ==================== 清理临时文件 ====================
    def cleanup_last(self):
        """删除最近一次合成的临时文件（可在播放完毕后调用）"""
        if self.last_filename and os.path.exists(self.last_filename):
            try:
                os.remove(self.last_filename)
                logger.debug(f"已删除临时文件: {self.last_filename}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {e}")
        self.last_filename = None