import requests
import urllib3
import time
from config.congif import API_KEY1,API_URL1

urllib3.disable_warnings()

API_URL = API_URL1
API_KEY = API_KEY1


def search_music(keyword, n=5):

    results = []

    for i in range(1, n + 1):

        try:

            params = {
                "key": API_KEY,
                "msg": keyword,
                "n": i
            }

            response = requests.get(
                API_URL,
                params=params,
                timeout=10,
                proxies={
                    "http": None,
                    "https": None
                },
                verify=False
            )

            # 防止返回 HTML
            if "application/json" not in response.headers.get("Content-Type", ""):
                print("接口不是JSON：")
                print(response.text)
                continue

            data = response.json()

            if data.get("code") != 200:
                continue

            song = data.get("data")

            if not song:
                continue

            results.append({
                "name": song.get("name", "未知歌曲"),

                "artist": song.get("songname", ""),

                # 关键修复
                "musicurl": song.get("url", ""),

                "picurl": song.get("picture", ""),

                "lrc": song.get("lrc", "")
            })

            # 防止503限流
            time.sleep(0.3)

        except Exception as e:
            print("搜索失败:", e)

    return results