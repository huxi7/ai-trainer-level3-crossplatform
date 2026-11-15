# [INPUT]: 依赖 assistant.main 的共用入口。
# [OUTPUT]: 启动助手；启动失败时写入本机日志并显示清晰错误。
# [POS]: 项目启动文件；脚本与免安装运行包使用同一入口。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import logging
import sys

if __name__ == "__main__":
    try:
        from assistant.main import entry
        raise SystemExit(entry())
    except Exception as error:
        logging.getLogger(__name__).exception("助手启动失败")
        message = "助手未能启动。请确认运行包已完整解压。\n" + str(error)
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "三级助手", 0x10)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.run(["/usr/bin/osascript", "-e", 'on run argv\n display alert "三级助手" message (item 1 of argv)\nend run', message])
        raise SystemExit(1)
