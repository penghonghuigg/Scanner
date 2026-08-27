from pynput import keyboard
import threading

barcode_data = ""
timer = None

def reset_barcode():
    global barcode_data
    if barcode_data:
        if len(barcode_data) >= 8:
            print(f"扫码内容: {barcode_data}")
        barcode_data = ""

def on_press(key):
    global barcode_data, timer
    try:
        # 如果是字母或数字字符，添加到条码数据中
        if key.char:
            barcode_data += key.char
            # 每次检测到按键都重置计时器
            if timer:
                timer.cancel()
            timer = threading.Timer(0.2, reset_barcode)  # 设置0.5秒的超时时间
            timer.start()
    except AttributeError:
        pass  # 忽略非字符按键

# 开始监听键盘事件
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()