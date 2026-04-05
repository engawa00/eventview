import subprocess
import xml.etree.ElementTree as ET
import argparse
import datetime
import sys
import calendar
import tkinter as tk
from tkinter import ttk, messagebox

def local_to_utc_str(date_str, is_end_of_day=False):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    if is_end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999000)
    dt_aware = dt.astimezone()
    dt_utc = dt_aware.astimezone(datetime.timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def parse_utc_to_local(utc_str):
    if not utc_str:
        return ""

    if len(utc_str) >= 20 and utc_str[-1] == "Z" and utc_str[10] == "T":
        if "." in utc_str:
            try:
                dt_utc = datetime.datetime.strptime(utc_str[:26]+"Z", "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
                dt_local = dt_utc.astimezone()
                return dt_local.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        else:
            try:
                dt_utc = datetime.datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                dt_local = dt_utc.astimezone()
                return dt_local.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

    return utc_str

def get_wake_events(start_date=None, end_date=None):
    query = "*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and (EventID=1)"
    
    time_conds = []
    if start_date:
        utc_start = local_to_utc_str(start_date)
        time_conds.append(f"@SystemTime>='{utc_start}'")
    if end_date:
        utc_end = local_to_utc_str(end_date, is_end_of_day=True)
        time_conds.append(f"@SystemTime<='{utc_end}'")
        
    if time_conds:
        query += f" and TimeCreated[{' and '.join(time_conds)}]"
        
    query += "]]"
    
    cmd = ['wevtutil', 'qe', 'System', f'/q:{query}', '/f:xml']
    
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        
    try:
        result = subprocess.run(cmd, capture_output=True, creationflags=creationflags)
        
        # Windowsのコマンドプロンプト出力は通常cp932または適宜エンコーディングされるため、フォールバックしつつデコード
        try:
            xml_output = result.stdout.decode('cp932')
        except UnicodeDecodeError:
            xml_output = result.stdout.decode('utf-8', errors='replace')
            
    except Exception as e:
        return [{"error": str(e)}]
        
    if not xml_output.strip():
        return []

    # wevtutil qe outputs a sequence of <Event> but no root wrapper.
    xml_doc = f"<Events>{xml_output}</Events>"
    events_data = []
    
    try:
        root = ET.fromstring(xml_doc)
        ns = {'win': 'http://schemas.microsoft.com/win/2004/08/events/event'}
        
        for event in root.findall('win:Event', ns) or root.findall('.//Event') or root.findall('{http://schemas.microsoft.com/win/2004/08/events/event}Event'):
            sleep_time = ""
            wake_time = ""
            wake_reason = ""
            wake_type = ""
            
            event_data = event.find('win:EventData', ns)
            if event_data is None:
                event_data = event.find('{http://schemas.microsoft.com/win/2004/08/events/event}EventData')
            if event_data is None:
                event_data = event.find('EventData')
                
            if event_data is not None:
                # 名前空間あり・なし両方対応できるようにする
                for data in list(event_data):
                    name = data.get('Name')
                    text = data.text or ""
                    if name == 'SleepTime':
                        sleep_time = text
                    elif name == 'WakeTime':
                        wake_time = text
                    elif name == 'WakeSourceText':
                        wake_reason = text
                    elif name == 'WakeSourceType':
                        wake_type = text
            
            if not wake_reason:
                if wake_type == '0':
                    wake_reason = "不明 (Unknown)"
                elif wake_type == '1':
                    wake_reason = "電源ボタン (Power Button)"
                elif wake_type == '8':
                    wake_reason = "デバイス または API (Device / API)"
                elif wake_type:
                    wake_reason = f"Type {wake_type}"
                else:
                    wake_reason = "不明"
                    
            events_data.append({
                "SleepTime": parse_utc_to_local(sleep_time),
                "WakeTime": parse_utc_to_local(wake_time),
                "Reason": wake_reason
            })
            
    except ET.ParseError as e:
        events_data.append({"error": f"Failed to parse XML: {e}"})
        
    return events_data

def run_cli(start, end):
    print(f"スリープ復帰履歴を取得中... (開始: {start or '指定なし'}, 終了: {end or '指定なし'})")
    events = get_wake_events(start_date=start, end_date=end)
    
    if not events:
        print("指定された期間の復帰イベントは見つかりませんでした。")
        return
        
    if "error" in events[0]:
        print(f"エラー: {events[0]['error']}")
        return
        
    print("-" * 80)
    for i, ev in enumerate(events, 1):
        print(f"[{i}] スリープ日時: {ev.get('SleepTime')} | 復帰日時: {ev.get('WakeTime')} | 理由: {ev.get('Reason')}")
    print("-" * 80)

class CalendarDialog(tk.Toplevel):
    def __init__(self, parent, target_entry):
        super().__init__(parent)
        self.target_entry = target_entry
        self.title("日付選択")
        self.geometry("250x250")
        self.transient(parent)
        self.grab_set()

        self.year_var = tk.IntVar()
        self.month_var = tk.IntVar()

        current_date = target_entry.get().strip()
        now = datetime.datetime.now()
        y, m = now.year, now.month
        if current_date:
            try:
                dt = datetime.datetime.strptime(current_date, "%Y-%m-%d")
                y, m = dt.year, dt.month
            except ValueError:
                pass

        self.year_var.set(y)
        self.month_var.set(m)

        self.create_widgets()
        self.update_calendar()

    def create_widgets(self):
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=5)

        ttk.Button(header_frame, text="<", width=3, command=self.prev_month).pack(side=tk.LEFT, padx=5)
        self.month_label = ttk.Label(header_frame, text="", font=("", 10, "bold"))
        self.month_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(header_frame, text=">", width=3, command=self.next_month).pack(side=tk.RIGHT, padx=5)

        self.cal_frame = ttk.Frame(self)
        self.cal_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def prev_month(self):
        m = self.month_var.get() - 1
        y = self.year_var.get()
        if m < 1:
            m = 12
            y -= 1
        self.month_var.set(m)
        self.year_var.set(y)
        self.update_calendar()

    def next_month(self):
        m = self.month_var.get() + 1
        y = self.year_var.get()
        if m > 12:
            m = 1
            y += 1
        self.month_var.set(m)
        self.year_var.set(y)
        self.update_calendar()

    def update_calendar(self):
        for widget in self.cal_frame.winfo_children():
            widget.destroy()

        y = self.year_var.get()
        m = self.month_var.get()

        self.month_label.config(text=f"{y}年 {m}月")

        days = ["月", "火", "水", "木", "金", "土", "日"]
        for i, day in enumerate(days):
            ttk.Label(self.cal_frame, text=day).grid(row=0, column=i, padx=5, pady=2)

        cal = calendar.monthcalendar(y, m)
        for r, week in enumerate(cal, start=1):
            for c, day in enumerate(week):
                if day != 0:
                    btn = ttk.Button(self.cal_frame, text=str(day), width=3,
                                     command=lambda d=day: self.select_date(y, m, d))
                    btn.grid(row=r, column=c, padx=1, pady=1)

    def select_date(self, y, m, d):
        date_str = f"{y:04d}-{m:02d}-{d:02d}"
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, date_str)
        self.destroy()

def run_gui():
    root = tk.Tk()
    root.title("Windows Wake Event Viewer")
    root.geometry("700x550")
    
    frame = ttk.Frame(root, padding="10")
    frame.pack(fill=tk.BOTH, expand=True)
    
    input_frame = ttk.Frame(frame)
    input_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(input_frame, text="開始日 (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(0, 5))
    start_entry = ttk.Entry(input_frame, width=12)
    start_entry.pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(input_frame, text="📅", width=3, command=lambda: CalendarDialog(root, start_entry)).pack(side=tk.LEFT, padx=(0, 15))
    
    ttk.Label(input_frame, text="終了日 (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(0, 5))
    end_entry = ttk.Entry(input_frame, width=12)
    end_entry.pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(input_frame, text="📅", width=3, command=lambda: CalendarDialog(root, end_entry)).pack(side=tk.LEFT, padx=(0, 15))
    
    fetch_btn = ttk.Button(input_frame, text="検索")
    fetch_btn.pack(side=tk.LEFT)
    
    paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
    paned.pack(fill=tk.BOTH, expand=True)
    
    tree_frame = ttk.Frame(paned)
    paned.add(tree_frame, weight=3)
    
    columns = ("SleepTime", "WakeTime", "Reason")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    tree.heading("SleepTime", text="スリープ日時")
    tree.heading("WakeTime", text="復帰日時")
    tree.heading("Reason", text="復帰理由")
    
    tree.column("SleepTime", width=160, anchor="center")
    tree.column("WakeTime", width=160, anchor="center")
    tree.column("Reason", width=300, anchor="w")
    
    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    details_frame = ttk.Frame(paned)
    paned.add(details_frame, weight=1)
    
    ttk.Label(details_frame, text="復帰理由 詳細:").pack(anchor=tk.W, pady=(5, 2))
    details_text = tk.Text(details_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
    details_text.pack(fill=tk.BOTH, expand=True)
    
    def on_tree_select(event):
        selected = tree.selection()
        details_text.config(state=tk.NORMAL)
        details_text.delete(1.0, tk.END)
        if selected:
            item = tree.item(selected[0])
            reason = item['values'][2] if len(item['values']) > 2 else ""
            details_text.insert(tk.END, reason)
        details_text.config(state=tk.DISABLED)
        
    tree.bind('<<TreeviewSelect>>', on_tree_select)
    
    def fetch_data():
        for item in tree.get_children():
            tree.delete(item)
            
        details_text.config(state=tk.NORMAL)
        details_text.delete(1.0, tk.END)
        details_text.config(state=tk.DISABLED)
            
        start_val = start_entry.get().strip() or None
        end_val = end_entry.get().strip() or None
        
        def validate(date_str):
            if date_str:
                try:
                    datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    return True
                except ValueError:
                    return False
            return True
            
        if not validate(start_val) or not validate(end_val):
            messagebox.showerror("入力エラー", "日付は YYYY-MM-DD の形式で入力してください。")
            return
            
        fetch_btn.config(state=tk.DISABLED)
        root.update()
        
        events = get_wake_events(start_val, end_val)
        
        fetch_btn.config(state=tk.NORMAL)
        
        if events and "error" in events[0]:
            messagebox.showerror("エラー", events[0]["error"])
            return
        
        if not events:
            messagebox.showinfo("結果", "指定された期間の復帰イベントは見つかりませんでした。")
            return
            
        for ev in events:
            tree.insert("", tk.END, values=(ev.get("SleepTime"), ev.get("WakeTime"), ev.get("Reason")))
            
    fetch_btn.config(command=fetch_data)
    
    root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Windows スリープ復帰履歴ビューア")
    parser.add_argument("--start", help="開始日 (YYYY-MM-DD)", default="")
    parser.add_argument("--end", help="終了日 (YYYY-MM-DD)", default="")
    parser.add_argument("--cli", action="store_true", help="CLIモードで明示的に実行します（全期間取得用）")
    
    args = parser.parse_args()
    
    if args.start or args.end or args.cli:
        run_cli(args.start, args.end)
    else:
        run_gui()
