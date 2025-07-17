import pyautogui
import time
import random
import sys
import json
import os
from tqdm import tqdm
from colorama import Fore, Style, init
from pyfiglet import Figlet
import psutil
from threading import Event, Thread, Lock
from pynput import keyboard
import logging
import atexit

# 初始化配置
init(autoreset=True)
logging.basicConfig(filename='file_sender.log', level=logging.INFO)
CONFIG_FILE = 'sender_config.json'
DEFAULT_CONFIG = {
    'coordinates': {'pos_a': [760, 200], 'pos_b': [300, 800], 'pos_c': [1050, 15]},
    'last_count': 5
}

# 颜色和样式定义
COLOR_TITLE = Fore.CYAN + Style.BRIGHT
COLOR_PROMPT = Fore.YELLOW + Style.BRIGHT
COLOR_INPUT = Fore.GREEN + Style.BRIGHT
COLOR_ERROR = Fore.RED + Style.BRIGHT
COLOR_SUCCESS = Fore.GREEN + Style.BRIGHT
COLOR_PROGRESS = Fore.MAGENTA
COLOR_SPEED_DATA = Fore.YELLOW

# 加载配置
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return DEFAULT_CONFIG
    except Exception as e:
        logging.warning(f"配置加载失败: {e}")
        return DEFAULT_CONFIG

# 保存配置
def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logging.error(f"配置保存失败: {e}")

# 打印装饰性标题
def print_banner():
    f = Figlet(font='slant')
    print(COLOR_TITLE + f.renderText('File Sender 3.0'))
    print("╒══════════════════════════════════════════╕")
    print("│          超 级 文 件 发 送 终 端         │")
    print("╘══════════════════════════════════════════╛\n")

# 获取屏幕分辨率
def get_screen_resolution():
    res = pyautogui.size()
    print(COLOR_PROMPT + f"\n当前屏幕分辨率: {Fore.MAGENTA}{res.width}x{res.height}")
    return res

# 自定义进度条
class CustomProgressBar(tqdm):
    def __init__(self, *args, **kwargs):
        kwargs['colour'] = 'MAGENTA'
        kwargs['dynamic_ncols'] = True
        super().__init__(*args, **kwargs)

# 倒计时功能
def countdown():
    print(COLOR_PROMPT + "\n🎯 准备就绪！发图程序将在倒计时后启动")
    print(COLOR_PROMPT + "🚨 中断操作请按" + Fore.RED + " Ctrl + C\n")
    try:
        for count in range(10, 0, -1):
            count_str = f"{Fore.MAGENTA}⏳ {count}..." if count > 3 else f"{Fore.RED}🔥 {count}!"
            print(f"\r{COLOR_PROMPT}倒计时: {count_str}", end='', flush=True)
            time.sleep(1)
        print(f"\n\n{COLOR_SUCCESS}🚀 开始发送！自动操作中，请勿触碰鼠标键盘...")
    except KeyboardInterrupt:
        print(f"\n{COLOR_ERROR}❌ 操作已取消")
        sys.exit()

# 实时坐标追踪线程
class MouseTracker(Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.stop_event = Event()
        self.current_pos = (0, 0)
        
    def run(self):
        while not self.stop_event.is_set():
            self.current_pos = pyautogui.position()
            print(f"\r📍 当前坐标: {Fore.CYAN}{self.current_pos}   ", end='', flush=True)
            time.sleep(0.1)

# 获取坐标函数
def get_coordinates(prompt, default_key, screen_width, screen_height, config):
    coord_prompt = f"📌 是否需要重新设置 {Fore.CYAN}{prompt}{COLOR_PROMPT} 的坐标? ({Fore.GREEN}y{COLOR_PROMPT}/{Fore.RED}n{COLOR_PROMPT}): "
    print(f"\n{COLOR_PROMPT}▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬")
    
    while True:
        user_input = input(coord_prompt).strip().lower()
        if user_input in ['y', 'n', '']:
            if user_input == 'y':
                tracker = MouseTracker()
                tracker.start()
                print(f"{COLOR_INPUT}\n🖱  请移动鼠标到目标位置，按任意键捕获坐标...")
                
                # 使用pynput等待按键
                key_pressed = False
                def on_press(_):
                    nonlocal key_pressed
                    key_pressed = True
                    return False
                    
                with keyboard.Listener(on_press=on_press) as listener:
                    while not key_pressed and not tracker.stop_event.is_set():
                        time.sleep(0.1)
                
                tracker.stop_event.set()
                tracker.join()
                coordinates = tracker.current_pos
                
                x, y = coordinates
                retry = 3
                while retry > 0:
                    if 0 <= x <= screen_width and 0 <= y <= screen_height:
                        break
                    print(f"{COLOR_ERROR}⚠ 坐标超出屏幕范围！请重新操作（剩余{retry}次机会）")
                    retry -= 1
                    time.sleep(1)
                    coordinates = pyautogui.position()
                    x, y = coordinates
                else:
                    coordinates = tuple(config['coordinates'].get(default_key, [0,0]))
                    print(f"{COLOR_PROMPT}⚡ 使用备用默认坐标: {Fore.MAGENTA}{coordinates}")
                
                print(f"{COLOR_SUCCESS}✔ 捕获坐标: {Fore.MAGENTA}{coordinates}")
                config['coordinates'][default_key] = list(coordinates)
                save_config(config)
                return coordinates
            else:
                coordinates = tuple(config['coordinates'].get(default_key, [0,0]))
                print(f"{COLOR_PROMPT}⚡ 使用默认坐标: {Fore.MAGENTA}{coordinates}")
                return coordinates
        else:
            print(f"{COLOR_ERROR}⚠ 无效输入，请输入 y 或 n")

# 网络监控
def network_monitor(stop_event, speed_dict, lock):
    old_upload = psutil.net_io_counters().bytes_sent
    old_download = psutil.net_io_counters().bytes_recv
    upload_samples = []
    download_samples = []
    
    while not stop_event.is_set():
        time.sleep(0.5)
        new_upload = psutil.net_io_counters().bytes_sent
        new_download = psutil.net_io_counters().bytes_recv
        
        upload_speed = (new_upload - old_upload) / (1024 * 1024) * 2
        download_speed = (new_download - old_download) / (1024 * 1024) * 2
        
        with lock:
            upload_samples.append(upload_speed)
            download_samples.append(download_speed)
            # 保持最近3秒的数据
            if len(upload_samples) > 6:
                upload_samples.pop(0)
                download_samples.pop(0)
                
            speed_dict['upload'] = sum(upload_samples)/len(upload_samples)
            speed_dict['download'] = sum(download_samples)/len(download_samples)
        
        old_upload = new_upload
        old_download = new_download

# 动态延迟计算
def calculate_delay(base_delay, speed_info):
    with speed_info['lock']:
        upload_speed = speed_info['upload']
    # 上传速度越快，延迟越小（0.01-0.1秒范围）
    return max(0.01, base_delay - (upload_speed / 100))

# 模拟操作主函数
def simulate_copy_paste_cycle(pos_a, pos_b, pos_c, repeat_times=5):
    try:
        # 初始化网络监控
        speed_info = {
            'upload': 0.0,
            'download': 0.0,
            'lock': Lock()
        }
        stop_event = Event()
        monitor_thread = Thread(
            target=network_monitor, 
            args=(stop_event, speed_info, speed_info['lock']),
            daemon=True
        )
        monitor_thread.start()
        
        # 开始操作
        pyautogui.click(pos_a)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(random.uniform(0.001, 0.05))
        
        # 进度条显示
        start_time = time.time()
        with CustomProgressBar(
            range(repeat_times),
            desc=f"{COLOR_PROGRESS}📤 文件发送进度",
            bar_format="{l_bar}{bar:40}{r_bar}",
            ascii="░▒█"
        ) as pbar:
            for i in pbar:
                base_delay = 0.05
                
                # 动态延迟
                delay = calculate_delay(base_delay, speed_info)
                pyautogui.click(pos_b)
                pyautogui.hotkey('ctrl', 'v')
                pyautogui.press('enter')
                time.sleep(delay)
                
                pyautogui.click(pos_c)
                pyautogui.press('right')
                pyautogui.hotkey('ctrl', 'c')
                time.sleep(delay)
                
                # 更新进度条信息
                elapsed = time.time() - start_time
                remaining = (repeat_times - i - 1) * delay * 2
                with speed_info['lock']:
                    pbar.set_postfix_str(
                        f"⏱ {elapsed:.1f}s | ⏳ {remaining:.1f}s | ↑{COLOR_SPEED_DATA}{speed_info['upload']:.2f}MB/s{Fore.RESET}"
                    )
        
        # 网络监控显示
        print("\n📊 网络监控中，按任意键退出...")
        def on_press(_):
            return False
            
        with keyboard.Listener(on_press=on_press) as listener:
            while monitor_thread.is_alive():
                with speed_info['lock']:
                    print(
                        f"\r{COLOR_PROGRESS}网络速度: ↑{COLOR_SPEED_DATA}{speed_info['upload']:6.2f}MB/s{Fore.RESET} ↓{COLOR_SPEED_DATA}{speed_info['download']:6.2f}MB/s{Fore.RESET}",
                        end='', flush=True
                    )
                time.sleep(1)
        
        stop_event.set()
        
    except pyautogui.FailSafeException:
        print(f"\n{COLOR_ERROR}❌ 操作被意外中断：鼠标移至屏幕角落")
        sys.exit(1)
    except Exception as e:
        logging.exception("致命错误")
        print(f"\n{COLOR_ERROR}💥 发生未知错误: {e}")
        sys.exit(1)
    finally:
        stop_event.set()
        if monitor_thread.is_alive():
            monitor_thread.join(timeout=1)

# 主函数
def main():
    config = load_config()
    print_banner()
    screen = get_screen_resolution()
    
    # 获取发送数量
    while True:
        try:
            repeat_times = int(input(f"\n{COLOR_INPUT}📤 请输入要发送的文件数量（{Fore.CYAN}正整数{COLOR_INPUT}）[上次: {config['last_count']}]: ") or config['last_count'])
            if repeat_times > 0:
                config['last_count'] = repeat_times
                save_config(config)
                break
            print(f"{COLOR_ERROR}⚠ 必须是大于0的正整数！")
        except ValueError:
            print(f"{COLOR_ERROR}⚠ 请输入有效的数字！")
    
    # 获取坐标
    pos_a = get_coordinates("第一个文件", "pos_a", screen.width, screen.height, config)
    pos_b = get_coordinates("聊天框", "pos_b", screen.width, screen.height, config)
    pos_c = get_coordinates("发送区顶部", "pos_c", screen.width, screen.height, config)
    
    # 保存最终配置
    save_config(config)
    
    countdown()
    
    try:
        simulate_copy_paste_cycle(pos_a, pos_b, pos_c, repeat_times)
    except Exception as e:
        print(f"\n{COLOR_ERROR}💥 错误发生: {e}")
    finally:
        print(f"\n{COLOR_SUCCESS}🎉 所有文件发送完成！")
        input(f"{COLOR_INPUT}👉 按任意键退出程序...")

if __name__ == "__main__":
    main()