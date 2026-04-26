import subprocess

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
import argparse
import datetime
import os
import calendar
import tkinter as tk
import threading
import functools
from typing import Optional, List, Dict, Any
from tkinter import ttk, messagebox


def local_to_utc_str(date_str: str, is_end_of_day: bool = False) -> str:

    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: '{date_str}'. Please use YYYY-MM-DD.")
    if is_end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999000)
    dt_aware = dt.astimezone()
    dt_utc = dt_aware.astimezone(datetime.timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def validate_date(date_str: Optional[str]) -> bool:
    if date_str:
        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    return True


def parse_utc_to_local(utc_str: str) -> str:
    if not utc_str:
        return ""

    if len(utc_str) >= 20 and utc_str[-1] == "Z" and utc_str[10] == "T":
        if "." in utc_str:
            try:
                base, frac = utc_str[:-1].split(".", 1)
                frac = frac[:6]
                dt_utc = datetime.datetime.strptime(
                    f"{base}.{frac}Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=datetime.timezone.utc)
                dt_local = dt_utc.astimezone()
                return dt_local.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        else:
            try:
                dt_utc = datetime.datetime.strptime(
                    utc_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=datetime.timezone.utc)
                dt_local = dt_utc.astimezone()
                return dt_local.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

    return utc_str


@functools.lru_cache(maxsize=1)
def get_wevtutil_path() -> str:
    return os.path.join(
        os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wevtutil.exe"
    )


def _build_wevtutil_query(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> str:
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
    return query


def _execute_wevtutil_query(query: str) -> str:
    # Hardcode the absolute path to wevtutil to prevent PATH hijacking
    wevtutil_path = get_wevtutil_path()

    cmd = [wevtutil_path, "qe", "System", f"/q:{query}", "/f:xml"]

    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, capture_output=True, creationflags=creationflags)
    except PermissionError:
        raise RuntimeError(
            "アクセスが拒否されました。アプリケーションを管理者権限で実行してください。"
        )

    # Windowsのコマンドプロンプト出力は通常cp932または適宜エンコーディングされるため、フォールバックしつつデコード
    try:
        xml_output = result.stdout.decode("cp932")
    except UnicodeDecodeError:
        xml_output = result.stdout.decode("utf-8", errors="replace")

    if (
        result.returncode == 5
        or "Access is denied" in xml_output
        or "アクセスが拒否されました" in xml_output
        or "Access is denied" in result.stderr.decode("utf-8", errors="ignore")
        or "アクセスが拒否されました" in result.stderr.decode("utf-8", errors="ignore")
    ):
        raise RuntimeError(
            "アクセスが拒否されました。アプリケーションを管理者権限で実行してください。"
        )

    return xml_output


def _parse_wake_events_xml(xml_output: str) -> List[Dict[str, str]]:
    if not xml_output.strip():
        return []

    # wevtutil qe outputs a sequence of <Event> but no root wrapper.
    xml_doc = f"<Events>{xml_output}</Events>"
    events_data = []

    try:
        root = ET.fromstring(xml_doc)
        ns = {"win": "http://schemas.microsoft.com/win/2004/08/events/event"}

        event_paths = (
            "win:Event",
            "Event",
            "{http://schemas.microsoft.com/win/2004/08/events/event}Event",
        )
        events = next(
            (nodes for p in event_paths if (nodes := root.findall(p, ns))), []
        )

        data_paths = (
            "win:EventData",
            "{http://schemas.microsoft.com/win/2004/08/events/event}EventData",
            "EventData",
        )
        # 効率化のため、ループの外で正しいパスを特定する
        data_path = next(
            (p for p in data_paths if events and events[0].find(p, ns) is not None),
            data_paths[0],
        )

        for event in events:
            sleep_time = ""
            wake_time = ""
            wake_reason = ""
            wake_type = ""
            event_data = event.find(data_path, ns)

            if event_data is not None:
                # 名前空間あり・なし両方対応できるようにする
                for data in event_data:
                    name = data.get("Name")
                    text = data.text or ""
                    if name == "SleepTime":
                        sleep_time = text
                    elif name == "WakeTime":
                        wake_time = text
                    elif name == "WakeSourceText":
                        wake_reason = text
                    elif name == "WakeSourceType":
                        wake_type = text

            if not wake_reason:
                if wake_type == "0":
                    wake_reason = "不明 (Unknown)"
                elif wake_type == "1":
                    wake_reason = "電源ボタン (Power Button)"
                elif wake_type == "8":
                    wake_reason = "デバイス または API (Device / API)"
                elif wake_type:
                    wake_reason = f"Type {wake_type}"
                else:
                    wake_reason = "不明"

            events_data.append(
                {
                    "SleepTime": parse_utc_to_local(sleep_time),
                    "WakeTime": parse_utc_to_local(wake_time),
                    "Reason": wake_reason,
                }
            )

    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse XML: {e}")

    return events_data


def get_wake_events(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> List[Dict[str, str]]:
    query = _build_wevtutil_query(start_date, end_date)
    xml_output = _execute_wevtutil_query(query)
    return _parse_wake_events_xml(xml_output)


def run_cli(start: Optional[str], end: Optional[str]) -> None:
    print(
        f"スリープ復帰履歴を取得中... (開始: {start or '指定なし'}, 終了: {end or '指定なし'})"
    )
    try:
        events = get_wake_events(start_date=start, end_date=end)
    except Exception as e:
        print(f"エラー: {e}")
        return

    if not events:
        print("指定された期間の復帰イベントは見つかりませんでした。")
        return

    print("-" * 80)
    for i, ev in enumerate(events, 1):
        print(
            f"[{i}] スリープ日時: {ev.get('SleepTime')} | 復帰日時: {ev.get('WakeTime')} | 理由: {ev.get('Reason')}"
        )
    print("-" * 80)


class CalendarDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, target_entry: ttk.Entry) -> None:
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

    def create_widgets(self) -> None:
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=5)

        ttk.Button(header_frame, text="<", width=3, command=self.prev_month).pack(
            side=tk.LEFT, padx=5
        )
        self.month_label = ttk.Label(header_frame, text="", font=("", 10, "bold"))
        self.month_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(header_frame, text=">", width=3, command=self.next_month).pack(
            side=tk.RIGHT, padx=5
        )

        self.cal_frame = ttk.Frame(self)
        self.cal_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        days = ["月", "火", "水", "木", "金", "土", "日"]
        for i, day in enumerate(days):
            ttk.Label(self.cal_frame, text=day).grid(row=0, column=i, padx=5, pady=2)

        self.date_buttons = []
        for r in range(1, 7):
            for c in range(7):
                btn = ttk.Button(self.cal_frame, width=3)
                btn.grid(row=r, column=c, padx=1, pady=1)
                self.date_buttons.append(btn)

    def add_months(self, delta: int) -> None:
        total_months = self.month_var.get() + delta - 1
        y = self.year_var.get() + total_months // 12
        m = total_months % 12 + 1

        self.month_var.set(m)
        self.year_var.set(y)
        self.update_calendar()

    def prev_month(self) -> None:
        self.add_months(-1)

    def next_month(self) -> None:
        self.add_months(1)

    def update_calendar(self) -> None:
        y = self.year_var.get()
        m = self.month_var.get()

        self.month_label.config(text=f"{y}年 {m}月")

        cal = calendar.monthcalendar(y, m)
        flat_cal = [day for week in cal for day in week]

        for i, btn in enumerate(self.date_buttons):
            if i < len(flat_cal) and flat_cal[i] != 0:
                day = flat_cal[i]
                btn.config(text=str(day), command=lambda d=day: self.select_date(y, m, d))
                btn.grid()
            else:
                btn.grid_remove()

    def select_date(self, y: int, m: int, d: int) -> None:
        date_str = f"{y:04d}-{m:02d}-{d:02d}"
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, date_str)
        self.destroy()


class WakeEventViewerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Windows Wake Event Viewer")
        self.root.geometry("700x550")

        self.frame = ttk.Frame(self.root, padding="10")
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.input_frame = ttk.Frame(self.frame)
        self.input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(self.input_frame, text="開始日 (YYYY-MM-DD):").pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.start_entry = ttk.Entry(self.input_frame, width=12)
        self.start_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            self.input_frame,
            text="📅",
            width=3,
            command=lambda: CalendarDialog(self.root, self.start_entry),
        ).pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(self.input_frame, text="終了日 (YYYY-MM-DD):").pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.end_entry = ttk.Entry(self.input_frame, width=12)
        self.end_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            self.input_frame,
            text="📅",
            width=3,
            command=lambda: CalendarDialog(self.root, self.end_entry),
        ).pack(side=tk.LEFT, padx=(0, 15))

        self.fetch_btn = ttk.Button(
            self.input_frame, text="検索", command=self.fetch_data
        )
        self.fetch_btn.pack(side=tk.LEFT)

        self.paned = ttk.PanedWindow(self.frame, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.tree_frame = ttk.Frame(self.paned)
        self.paned.add(self.tree_frame, weight=3)

        columns = ("SleepTime", "WakeTime", "Reason")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        self.tree.heading("SleepTime", text="スリープ日時")
        self.tree.heading("WakeTime", text="復帰日時")
        self.tree.heading("Reason", text="復帰理由")

        self.tree.column("SleepTime", width=160, anchor="center")
        self.tree.column("WakeTime", width=160, anchor="center")
        self.tree.column("Reason", width=300, anchor="w")

        self.scrollbar = ttk.Scrollbar(
            self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscroll=self.scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.details_frame = ttk.Frame(self.paned)
        self.paned.add(self.details_frame, weight=1)

        ttk.Label(self.details_frame, text="復帰理由 詳細:").pack(
            anchor=tk.W, pady=(5, 2)
        )
        self.details_text = tk.Text(
            self.details_frame, height=5, wrap=tk.WORD, state=tk.DISABLED
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def on_tree_select(self, event: Any) -> None:
        selected = self.tree.selection()
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        if selected:
            item = self.tree.item(selected[0])
            reason = item["values"][2] if len(item["values"]) > 2 else ""
            self.details_text.insert(tk.END, reason)
        self.details_text.config(state=tk.DISABLED)

    def fetch_data(self) -> None:
        self.tree.delete(*self.tree.get_children())

        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        self.details_text.config(state=tk.DISABLED)

        start_val = self.start_entry.get().strip() or None
        end_val = self.end_entry.get().strip() or None

        if not validate_date(start_val) or not validate_date(end_val):
            messagebox.showerror(
                "入力エラー", "日付は YYYY-MM-DD の形式で入力してください。"
            )
            return

        self.fetch_btn.config(state=tk.DISABLED)
        self.root.update()

        def fetch_task() -> None:
            try:
                events = get_wake_events(start_val, end_val)
                self.root.after(0, self._on_fetch_success, events)
            except Exception as e:
                self.root.after(0, self._on_fetch_error, e)

        threading.Thread(target=fetch_task, daemon=True).start()

    def _on_fetch_error(self, e: Exception) -> None:
        self.fetch_btn.config(state=tk.NORMAL)
        messagebox.showerror("エラー", str(e))

    def _on_fetch_success(self, events: List[Dict[str, str]]) -> None:
        self.fetch_btn.config(state=tk.NORMAL)

        if not events:
            messagebox.showinfo(
                "結果", "指定された期間の復帰イベントは見つかりませんでした。"
            )
            return

        for ev in events:
            self.tree.insert(
                "",
                tk.END,
                values=(ev.get("SleepTime"), ev.get("WakeTime"), ev.get("Reason")),
            )


def run_gui() -> None:
    root = tk.Tk()
    app = WakeEventViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    epilog_text = (
        "使い方（CLI）:\n"
        "  python event_viewer.py --start 2023-10-01 --end 2023-10-31\n"
        "  python event_viewer.py --cli  # 全期間の履歴を取得して表示\n\n"
        "引数を指定せずに実行すると、GUIモードで起動します。"
    )
    parser = argparse.ArgumentParser(
        description="Windows Wake Event Viewer",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=epilog_text,
    )
    parser.add_argument(
        "--start", metavar="YYYY-MM-DD", help="開始日 (例: 2023-10-01)", default=""
    )
    parser.add_argument(
        "--end", metavar="YYYY-MM-DD", help="終了日 (例: 2023-10-31)", default=""
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="CLIモードで明示的に実行します（全期間取得用）",
    )

    args = parser.parse_args()

    if args.start or args.end or args.cli:
        run_cli(args.start, args.end)
    else:
        run_gui()
