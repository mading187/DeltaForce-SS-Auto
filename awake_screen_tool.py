import time
import ctypes

# Windows 常量
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
# 注意：故意不用 ES_CONTINUOUS，只做一次唤醒，不长期保活

SC_MONITORPOWER = 0xF170
WM_SYSCOMMAND = 0x0112


def wake_screen_once(logger=print):
    """
    只唤醒一次：重置系统+显示器空闲计时器，并发送点亮显示器消息。
    不持续阻止息屏，不阻止系统后续睡眠。
    """
    # 1. 告诉系统“我现在有用”，重置空闲计时器（不带 CONTINUOUS）
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )

    # 2. 向当前前台窗口发送“点亮显示器”消息
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if hwnd:
        ctypes.windll.user32.SendMessageW(
            hwnd, WM_SYSCOMMAND, SC_MONITORPOWER, -1
        )

    logger(f"[{time.strftime('%H:%M:%S')}] 已发送唤醒信号（单次）")

