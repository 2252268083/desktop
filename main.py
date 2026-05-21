import sys
import os
from pathlib import Path

# 1. 环境变量和路径配置最好放在最前面，防止后面的模块找不到或沙盒报错
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
sys.path.insert(0, str(Path(__file__).parent))

# 2. 配置好环境后再导入 PyQt 和你自己的模块
from PyQt5.QtWidgets import QApplication
from src.app.qtz5 import DesktopPet
from src.services.duihua_api import AIChat  # 导入你的AI聊天类

if __name__ == "__main__":
    # 初始化AI聊天实例
    ai = AIChat()   

    # 创建Qt应用
    app = QApplication(sys.argv)

    # ✅ 修复：传入完整的AI实例，而不是单独的chat_stream函数
    pet = DesktopPet(ai)

    # 显示桌宠
    pet.show()

    # 运行应用主循环
    sys.exit(app.exec_())



