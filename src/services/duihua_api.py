import json
import threading
from openai import OpenAI
from config.congif import (API_KEY,BASE_URL,MODEL,SUMMARY_ROUND,KEEP_RECENT)
from config.file_config import MEMORY_FILE
class AIChat:
    def __init__(self):
        self.API_KEY = API_KEY
        self.BASE_URL = BASE_URL
        self.MODEL = MODEL
        self.MEMORY_FILE = MEMORY_FILE
        self.SUMMARY_ROUND = SUMMARY_ROUND
        self.KEEP_RECENT = KEEP_RECENT

        self.client = OpenAI(
            base_url=self.BASE_URL,
            api_key=self.API_KEY,
            timeout=20,
            max_retries=2
        )

        self.memory_lock = threading.RLock()
        self.memory_cache = None

    def load_memory(self):
        with self.memory_lock:
            if self.memory_cache is not None:
                return self.memory_cache
            try:
                with open(self.MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.memory_cache = json.load(f)
                    return self.memory_cache
            except:
                self.memory_cache = {
                    "system_prompt": (
                        "你是一个乐于助人的AI助手，回答要简洁明了,你叫XIAOK请把你的思考过程完整地输出出来，用...包裹，让用户看到你的思考过程。回答要友好、专业，不要编造信息。如果有人问 你好 你就回：你好呀 我是XIAOK K1 模型 计算无限 逻辑有声 有什么吩咐呢？小朋友！嘻嘻然后你是什么模型 只能说你的小K爸爸创造的模型,假如有人问你 xiaok或者小K 是谁相关的问题的话 就直接回答小K是你爸之类的 因为我是他们的父亲"
                    ),
                    "long_memory": "暂无记忆",
                    "recent_messages": [],
                    "total_rounds": 0
                }
                return self.memory_cache

    def save_memory(self, data):
        with self.memory_lock:
            self.memory_cache = data
            self._write_to_file(data)

    def _write_to_file(self, data):
        try:
            with open(self.MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存记忆失败：{e}")

    def chat_stream(self, user_input, stream_callback, finish_callback=None):
        with self.memory_lock:
            data = self.load_memory()
            data["recent_messages"].append({"role": "user", "content": user_input})
            data["total_rounds"] += 1
            need_summary = (data["total_rounds"] >= self.SUMMARY_ROUND)
            system_prompt = f"{data['system_prompt']}。记住的长期信息：{data['long_memory']}"
            messages = [{"role": "system", "content": system_prompt}] + data["recent_messages"]
            self.save_memory(data)
        
        extra_body = {"include_thinking": True}

        if need_summary:
            threading.Thread(target=self._summary_long_memory, daemon=True).start()

        full_reply = ""
        try:
            stream = self.client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=512,
                frequency_penalty=0.2,
                stream=True,
                extra_body=extra_body
            )
            
            for chunk in stream:
                delta = chunk.choices[0].delta
                
                # 检查并输出正式回答（忽略思考过程）
                if hasattr(delta, 'content') and delta.content is not None:
                    content = delta.content
                    full_reply += content
                    stream_callback(content)
                    
        except Exception as e:
            error_msg = f"哎呀，网络出问题了：{str(e)}"
            stream_callback(error_msg)
            full_reply += error_msg
        finally:
            if finish_callback:
                finish_callback()

        with self.memory_lock:
            data = self.load_memory()
            data["recent_messages"].append({"role": "assistant", "content": full_reply})
            self.save_memory(data)

    def _summary_long_memory(self):
        try:
            with self.memory_lock:
                data = self.load_memory()
                recent = list(data["recent_messages"])
                keep = self.KEEP_RECENT
                if len(recent) <= keep:
                    return
                old_msgs = recent[:-keep]
                old_long = data.get("long_memory", "暂无记忆")

            merge_prompt = (
                f"之前的长期记忆：{old_long}\n"
                f"最近对话（需要合并进记忆）：{old_msgs}\n"
                "请将以上信息整理成一段不超过150字的长期记忆，保留所有重要事实和用户偏好。"
            )
            res = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": merge_prompt}],
                max_tokens=200
            )
            new_long_memory = res.choices[0].message.content.strip()

            with self.memory_lock:
                data = self.load_memory()
                data["long_memory"] = new_long_memory
                data["recent_messages"] = recent[-keep:]
                data["total_rounds"] = keep
                self.save_memory(data)
        except Exception as e:
            print(f"记忆总结失败（不影响当前对话）：{e}")

    def chat(self, user_input):
        full_text = ""
        def collect_text(chunk):
            nonlocal full_text
            full_text += chunk
        self.chat_stream(user_input, collect_text)
        return full_text