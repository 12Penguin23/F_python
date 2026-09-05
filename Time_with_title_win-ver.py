import asyncio
import threading
import time
import tkinter as tk
import pyautogui as pagui
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

screen_w, screen_h = pagui.size()  # 獲取螢幕解析度
bg_color = "#304989"
bg_color_push = "#3F60B4"
pagui.FAILSAFE = True  # 關閉滑鼠移動到螢幕角落的安全機制
pause_button_state = False  # 用於追蹤播放/暫停狀態


class DesktopClockMediaWidget:

    def __init__(self, root):
        self.root = root

        # 1. 視窗樣式：無邊框、最上層、半透明
        self.root.overrideredirect(1)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.7)
        # 稍微加高視窗高度至 150 以放得下按鈕
        self.root.geometry(f"300x150+{screen_w // 8 * 3}+{screen_h // 4 * 3}")

        # 2. Canvas 畫布 UI
        self.canvas = tk.Canvas(
            root, bg=bg_color, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.now_playing = "No Music Playing"
        self.is_playing = False

        # 3. Canvas 文字元件
        # 時間文字 (上方)
        self.time_text = self.canvas.create_text(
            150,
            30,
            text="",
            font=("DepartureMono Nerd Font", 28, "bold"),
            fill="#CDD6F4",
        )

        # 曲名 / 歌手文字 (中間)
        self.song_text = self.canvas.create_text(
            150,
            68,
            text=self.now_playing,
            font=("yahei ui", 11, "bold"),
            fill="#FFBF7F",
            width=300,  # 自動換行
        )

        # 4. 建立暫停 / 播放控制按鈕 (下方)
        self.pause_button = tk.Button(
            self.root,
            text="⏸" if pause_button_state else "▶️",
            font=("Segoe UI Emoji", 14, "bold"),
            bg=bg_color,
            fg="#CDD6F4",
            activebackground=bg_color_push,
            activeforeground="#FFFFFF",
            bd=0,
            command=self.toggle_pause,
        )
        self.next_button = tk.Button(
            self.root,
            text="⏭️",
            font=("Segoe UI Emoji", 14, "bold"),
            bg=bg_color,
            fg="#CDD6F4",
            activebackground=bg_color_push,
            activeforeground="#FFFFFF",
            bd=0,
            command=self.toggle_next,
        )
        self.last_button = tk.Button(
            self.root,
            text="⏮️",
            font=("Segoe UI Emoji", 14, "bold"),
            bg=bg_color,
            fg="#CDD6F4",
            activebackground=bg_color_push,
            activeforeground="#FFFFFF",
            bd=0,
            command=self.toggle_last,
        )

        # 將按鈕放入 Canvas 底層
        self.canvas.create_window(
            150, 115, window=self.pause_button, width=30, height=30
        )
        self.canvas.create_window(
            180, 115, window=self.next_button, width=30, height=30
        )
        self.canvas.create_window(
            120, 115, window=self.last_button, width=30, height=30
        )

        # 5. 事件綁定：拖曳與右鍵關閉
        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind(
            "<Button-3>", lambda e: self.root.destroy()
        )  # 右鍵關閉視窗

        # 6. 啟動背景線程來監聽與輪詢媒體資訊
        self.loop = None  # 儲存背景 asyncio loop 引用
        self.start_media_listener()

        # 7. 啟動 UI 時鐘與狀態刷新循環
        self.update_loop()

    # --- Windows Media 控制與監聽邏輯 ---

    def start_media_listener(self):
        """在背景 Daemon Thread 中執行 asyncio 事件循環"""

        def run_asyncio_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.fetch_media_info_loop())

        threading.Thread(target=run_asyncio_loop, daemon=True).start()

    def toggle_pause(self):
        """按下按鈕時觸發：安全地將非同步工作提交給背景 asyncio 事件循環"""
        global pause_button_state
        pause_button_state = not pause_button_state  # 切換播放/暫停狀態
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.async_toggle_play_pause(), self.loop
            )

    def toggle_next(self):
        """按下按鈕時觸發：安全地將非同步工作提交給背景 asyncio 事件循環"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.async_toggle_next(), self.loop
            )

    def toggle_last(self):
        """按下按鈕時觸發：安全地將非同步工作提交給背景 asyncio 事件循環"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.async_toggle_last(), self.loop
            )

    async def async_toggle_play_pause(self):
        """直接透過 Windows GSMTC API 切換播放/暫停"""
        try:
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            if current_session:
                await current_session.try_toggle_play_pause_async()
        except Exception as e:
            print(f"Toggle error: {e}")

    async def async_toggle_next(self):
        """直接透過 Windows GSMTC API 切換下一首"""
        try:
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            if current_session:
                await current_session.try_skip_next_async()
        except Exception as e:
            print(f"Next error: {e}")

    async def async_toggle_last(self):
        """直接透過 Windows GSMTC API 切換上一首"""
        try:
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            if current_session:
                await current_session.try_skip_previous_async()
        except Exception as e:
            print(f"Last error: {e}")

    async def fetch_media_info_loop(self):
        """定期輪詢當前播放的歌名與歌手"""
        while True:
            try:
                sessions = await MediaManager.request_async()
                current_session = sessions.get_current_session()

                if current_session:
                    # 1. 取得歌曲資訊
                    info = (
                        await current_session.try_get_media_properties_async()
                    )
                    title = info.title if info.title else ""
                    artist = info.artist if info.artist else ""

                    if title:
                        new_text = (
                            f"🎵 {title} - {artist}"
                            if artist
                            else f"🎵 {title}"
                        )
                    else:
                        new_text = "🎵 Playing Music..."

                    # 2. 取得播放/暫停狀態（放出來，確保 current_session 存在時一定會執行）
                    playback_info = current_session.get_playback_info()
                    if playback_info:
                        self.is_playing = (
                            playback_info.playback_status
                            == PlaybackStatus.PLAYING
                        )
                    else:
                        self.is_playing = False
                else:
                    new_text = "❌ No Music Playing"
                    self.is_playing = False

                self.now_playing = new_text
            except Exception as e:
                self.now_playing = "❌ No Music Playing"
                self.is_playing = False

            await asyncio.sleep(1)  # 每秒更新一次

    # --- UI 刷新循環 ---
    def update_loop(self):
        # 更新時間顯示
        self.canvas.itemconfig(
            self.time_text, text=time.strftime("%H:%M:%S")
        )

        # 更新目前播放歌曲資訊
        self.canvas.itemconfig(self.song_text, text=self.now_playing)

        # 動態更新按鈕圖示
        if self.is_playing:
            self.pause_button.config(text="⏸")  # 正在播放時顯示暫停鍵
        else:
            self.pause_button.config(text="▶️")  # 暫停時顯示播放鍵

        # 30 FPS 刷新率 (約 33 毫秒)
        self.root.after(33, self.update_loop)

    # --- 視窗拖曳邏輯 ---
    def start_move(self, event):
        self._x = event.x
        self._y = event.y

    def do_move(self, event):
        x = self.root.winfo_x() + (event.x - self._x)
        y = self.root.winfo_y() + (event.y - self._y)
        self.root.geometry(f"+{x}+{y}")


try:
    if __name__ == "__main__":
        root = tk.Tk()
        app = DesktopClockMediaWidget(root)
        root.mainloop()
except KeyboardInterrupt:
    root.destroy()
    print("app_has_been_shut_down\nerror: KeyboardInterrupt")
