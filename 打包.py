import os
import PyInstaller.__main__

if __name__ == '__main__':
    # 确保在项目根目录运行
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print("开始打包桌宠项目...")

    PyInstaller.__main__.run([
        'main.py',                           # 你的主入口文件
        '--name=DesktopPet',                 # 生成的 exe 名字
        # '--noconsole',                     # 注释掉：保留控制台窗口以便查看崩溃报错
        '--onedir',                          # 推荐打成一个文件夹(onedir)，加载速度快，且不容易出资源路径Bug
        
        # 👇 把你需要的静态文件夹全都拷贝到打包后的文件夹里 👇
        # 格式：'--add-data=源路径;目标路径' （Windows 是分号 ; ）
        '--add-data=src/assets;src/assets',
        '--add-data=src/router;src/router',
        '--add-data=config;config',
        
        # 解决部分潜在的导入丢失问题
        '--hidden-import=PyQt5.QtWebEngineWidgets',
        '--hidden-import=edge_tts',
        
        # '--icon=你的图标.ico',             # 如果你有桌宠图标，把前面的#删掉并写上路径
        
        '--clean',                           # 每次打包前清理上次的缓存
        '-y'                                 # 自动覆盖已有的输出文件夹
    ])

    print("打包完成！请去 dist/DesktopPet 文件夹下寻找你的 DesktopPet.exe！")