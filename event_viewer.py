import subprocess

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
import argparse
import datetime
import os
import calendar
import itertools
import tkinter as tk
import threading
import functools
from typing import Optional, List, Dict, Any, NamedTuple, Tuple
from tkinter import ttk, messagebox

UTC_FORMATS = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ")


def local_to_utc_str(date_str: str, is_end_of_day: bool = False) -> str:
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{date_str}'. Please use YYYY-MM-DD."
        )
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


def parse_utc_str_to_datetime(utc_str: str) -> Optional[datetime.datetime]:
    if not utc_str:
        return None

    parsed_str = utc_str
    fmt_str = utc_str

    if len(utc_str) >= 20 and utc_str.endswith("Z") and "T" in utc_str:
        if "." in utc_str:
            base, frac = utc_str[:-1].split(".", 1)
            parsed_str = f"{base}.{frac[:6].ljust(6, '0')}+00:00"
            fmt_str = f"{base}.{frac[:6]}Z"
        else:
            parsed_str = f"{utc_str[:-1]}+00:00"

        try:
            return datetime.datetime.fromisoformat(parsed_str)
        except ValueError:
            pass

    for fmt in UTC_FORMATS:
        # Fast fail to avoid expensive exception handling for mismatches
        if len(fmt_str) < 19:
            continue
        if fmt.endswith("Z") and not fmt_str.endswith("Z"):
            continue
        if "T" in fmt and "T" not in fmt_str:
            continue

        try:
            dt_utc = datetime.datetime.strptime(fmt_str, fmt).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt_utc
        except ValueError:
            continue

    return None


def parse_utc_to_local(utc_str: str) -> str:
    if not utc_str:
        return ""
    dt = parse_utc_str_to_datetime(utc_str)
    if dt:
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return utc_str


@functools.lru_cache(maxsize=1)
def get_wevtutil_path() -> str:
    return os.path.join(
        os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wevtutil.exe"
    )


def _build_wevtutil_query(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> str:
    query = (
        "*[System[("
        "(Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] "
        "and EventID=1) "
        "or (Provider[@Name='Microsoft-Windows-Kernel-Power'] "
        "and EventID=507)"
        ")"
    )

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

    error_msg = "アクセスが拒否されました。アプリケーションを管理者権限で実行してください。"

    try:
        result = subprocess.run(
            cmd, capture_output=True, creationflags=creationflags
        )
    except PermissionError:
        raise RuntimeError(error_msg)

    if result.returncode == 5:
        raise RuntimeError(error_msg)

    stderr_output = result.stderr.decode("utf-8", errors="ignore")
    if (
        "Access is denied" in stderr_output
        or "アクセスが拒否されました" in stderr_output
    ):
        raise RuntimeError(error_msg)

    # Windowsのコマンドプロンプト出力は通常cp932または適宜エンコーディングされるため、フォールバックしつつデコード
    try:
        xml_output = result.stdout.decode("cp932")
    except UnicodeDecodeError:
        xml_output = result.stdout.decode("utf-8", errors="replace")

    if (
        "Access is denied" in xml_output
        or "アクセスが拒否されました" in xml_output
    ):
        raise RuntimeError(error_msg)

    return xml_output


def _map_wake_reason(wake_reason: str, wake_type: str) -> str:
    if wake_reason:
        return wake_reason
    if wake_type == "0":
        return "不明 (Unknown)"
    elif wake_type == "1":
        return "電源ボタン (Power Button)"
    elif wake_type == "8":
        return "デバイス または API (Device / API)"
    elif wake_type:
        return f"Type {wake_type}"
    return "不明"


def _map_kp_507_reason(reason_str: str) -> str:
    if not reason_str:
        return "不明"

    if not reason_str.isdigit():
        return reason_str

    reason_code = int(reason_str)
    base_code = reason_code & 0xFFFF

    mapping = {
        0: "不明 (Unknown)",
        1: "電源ボタン (Power Button)",
        2: "スリープ解除デバイス (Wake Device)",
        3: "モニターパワーの変更 / カバー開閉 (SC_MONITORPOWER)",
        4: "ユーザー入力 (User Input)",
        5: "電源状態の変更 (AC/DC Display Burst)",
        11: "システム状態の変更 (System State Change)",
        12: "アプリケーション (Application)",
        13: "システムAPI (System API)",
        14: "画面タイムアウト (Screen Timeout)",
        15: "液晶カバーの開閉 (Lid)",
        16: "音声再生 (Audio Playing)",
        17: "ネットワーク接続 (Network Connection)",
        19: "Windows Update",
        21: "温度異常 (Thermal)",
        22: "バッテリー (Battery)",
        23: "電源プラン変更 (Power Scheme)",
        24: "リモートデスクトップ (Remote Desktop)",
        28: "電源状態の変更抑制 (AC/DC Display Burst Suppressed)",
        31: "キーボード入力 (Input Keyboard)",
        32: "マウス入力 (Input Mouse)",
        33: "タッチパッド入力 (Input Touchpad)",
        34: "タッチ入力 (Input Touch)",
        35: "ペン入力 (Input Pen)",
    }

    if reason_code == 16777220:
        return "自動メンテナンス (PDC Task Client: Maintenance Scheduler)"

    result = mapping.get(base_code)
    if result:
        return f"{result} (コード {reason_str})"

    return f"コード {reason_str}"


_EVENT_NS_URI = "http://schemas.microsoft.com/win/2004/08/events/event"
_EVENT_NS = {"win": _EVENT_NS_URI}


class _EventPaths(NamedTuple):
    system: str
    event_id: str
    time_created: str
    data: str


def _tag_candidates(tag: str) -> Tuple[str, str, str]:
    # 名前空間あり・なし両方対応できるようにする
    return (f"win:{tag}", tag, f"{{{_EVENT_NS_URI}}}{tag}")


def _resolve_tag_path(node: Any, tag: str) -> str:
    """候補パスのうち node 配下で最初に見つかるものを返す。

    見つからない場合は先頭の候補を返す。
    """
    candidates = _tag_candidates(tag)
    return next(
        (
            p
            for p in candidates
            if node is not None and node.find(p, _EVENT_NS) is not None
        ),
        candidates[0],
    )


def _resolve_event_paths(first_event: Any) -> _EventPaths:
    # 効率化のため、ループの外で一度だけ各要素のパスを特定する
    system_path = _resolve_tag_path(first_event, "System")
    first_system = first_event.find(system_path, _EVENT_NS)
    return _EventPaths(
        system=system_path,
        event_id=_resolve_tag_path(first_system, "EventID"),
        time_created=_resolve_tag_path(first_system, "TimeCreated"),
        data=_resolve_tag_path(first_event, "EventData"),
    )


def _get_event_id(event: Any, paths: _EventPaths, default: str = "") -> str:
    system_node = event.find(paths.system, _EVENT_NS)
    if system_node is None:
        return default
    event_id_node = system_node.find(paths.event_id, _EVENT_NS)
    if event_id_node is None:
        return default
    return event_id_node.text or default


def _get_event_data_values(event: Any, data_path: str) -> Dict[str, str]:
    event_data = event.find(data_path, _EVENT_NS)
    if event_data is None:
        return {}
    return {
        data.get("Name"): data.text or ""
        for data in event_data
        if data.get("Name")
    }


def _collect_kp_507_events(
    events: List[Any], paths: _EventPaths
) -> List[Dict[str, Any]]:
    """EventID=507 (Kernel-Power) のイベントを発生時刻付きで収集する。"""
    kp_events = []
    for event in events:
        if _get_event_id(event, paths) != "507":
            continue

        system_node = event.find(paths.system, _EVENT_NS)
        time_node = system_node.find(paths.time_created, _EVENT_NS)
        time_created_utc = ""
        if time_node is not None:
            time_created_utc = time_node.get("SystemTime") or ""

        dt_utc = parse_utc_str_to_datetime(time_created_utc)
        if dt_utc:
            values = _get_event_data_values(event, paths.data)
            kp_events.append(
                {"Time": dt_utc, "Reason": values.get("Reason", "")}
            )
    return kp_events


def _find_kp_507_reason(
    kp_events: List[Dict[str, Any]],
    wake_dt: Optional[datetime.datetime],
) -> Optional[str]:
    """復帰時刻に最も近い(5秒未満) 507 イベントの理由を返す。"""
    if not wake_dt:
        return None

    best_match = None
    min_diff = datetime.timedelta(seconds=5)
    for kp in kp_events:
        diff = abs(kp["Time"] - wake_dt)
        if diff < min_diff:
            min_diff = diff
            best_match = kp

    if best_match is None:
        return None
    return _map_kp_507_reason(best_match["Reason"])


def _parse_single_event(
    event: Any, paths: _EventPaths, kp_events: List[Dict[str, Any]]
) -> Dict[str, str]:
    values = _get_event_data_values(event, paths.data)
    reason = _map_wake_reason(
        values.get("WakeSourceText", ""), values.get("WakeSourceType", "")
    )

    if "不明" in reason or "Unknown" in reason:
        # 理由が不明な場合、直近の 507 イベントから復帰理由を補完する
        wake_dt = parse_utc_str_to_datetime(values.get("WakeTime", ""))
        friendly_reason = _find_kp_507_reason(kp_events, wake_dt)
        if friendly_reason:
            reason = f"{reason} [モダンスタンバイ復帰理由: {friendly_reason}]"

    return {
        "SleepTime": parse_utc_to_local(values.get("SleepTime", "")),
        "WakeTime": parse_utc_to_local(values.get("WakeTime", "")),
        "Reason": reason,
    }


def _parse_wake_events_xml(xml_output: str) -> List[Dict[str, str]]:
    if not xml_output.strip():
        return []

    # wevtutil qe outputs a sequence of <Event> but no root wrapper.
    xml_doc = f"<Events>{xml_output}</Events>"
    try:
        root = ET.fromstring(xml_doc)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse XML: {e}")

    events = next(
        (
            nodes
            for p in _tag_candidates("Event")
            if (nodes := root.findall(p, _EVENT_NS))
        ),
        [],
    )
    if not events:
        return []

    paths = _resolve_event_paths(events[0])

    # 1パス目: EventID=507 のイベントを収集する
    kp_events = _collect_kp_507_events(events, paths)

    # 2パス目: EventID=1 のイベントをパースし、507 の理由をマージする
    return [
        _parse_single_event(event, paths, kp_events)
        for event in events
        if _get_event_id(event, paths, default="1") == "1"
    ]


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
            f"[{i}] スリープ日時: {ev.get('SleepTime')} | "
            f"復帰日時: {ev.get('WakeTime')} | 理由: {ev.get('Reason')}"
        )
    print("-" * 80)


class CalendarDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        target_entry: ttk.Entry,
        trigger_widget: Optional[tk.Widget] = None,
    ) -> None:
        super().__init__(parent)
        self.target_entry = target_entry
        self.title("日付選択")
        self.withdraw()

        self._position_window(trigger_widget)

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
        self.deiconify()

    def _position_window(self, trigger_widget: Optional[tk.Widget]) -> None:
        self.update_idletasks()
        w, h = 250, 250
        if trigger_widget:
            x = trigger_widget.winfo_rootx()
            y = trigger_widget.winfo_rooty() + trigger_widget.winfo_height()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            if x + w > screen_w or y + h > screen_h:
                self.geometry(f"{w}x{h}+0+0")
            else:
                self.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.geometry(f"{w}x{h}")

    def create_widgets(self) -> None:
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            header_frame, text="<", width=3, command=self.prev_month
        ).pack(side=tk.LEFT, padx=5)
        self.month_label = ttk.Label(
            header_frame, text="", font=("", 10, "bold")
        )
        self.month_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(
            header_frame, text=">", width=3, command=self.next_month
        ).pack(side=tk.RIGHT, padx=5)

        self.cal_frame = ttk.Frame(self)
        self.cal_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        days = ["月", "火", "水", "木", "金", "土", "日"]
        for i, day in enumerate(days):
            ttk.Label(self.cal_frame, text=day).grid(
                row=0, column=i, padx=5, pady=2
            )

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

        for btn, day in itertools.zip_longest(
            self.date_buttons,
            itertools.chain.from_iterable(cal),
            fillvalue=0,
        ):
            if day != 0:
                btn.config(
                    text=str(day),
                    command=lambda d=day: self.select_date(y, m, d),
                    state=tk.NORMAL,
                )
            else:
                btn.config(text="", state=tk.DISABLED)

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

        self._create_input_frame()
        self._create_tree_view()
        self._create_details_view()

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def _create_input_frame(self) -> None:
        self.input_frame = ttk.Frame(self.frame)
        self.input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(self.input_frame, text="開始日 (YYYY-MM-DD):").pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.start_entry = ttk.Entry(self.input_frame, width=12)
        self.start_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.cal_btn_start = ttk.Button(
            self.input_frame,
            text="📅",
            width=3,
        )
        self.cal_btn_start.config(
            command=lambda: CalendarDialog(
                self.root, self.start_entry, self.cal_btn_start
            )
        )
        self.cal_btn_start.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(self.input_frame, text="終了日 (YYYY-MM-DD):").pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.end_entry = ttk.Entry(self.input_frame, width=12)
        self.end_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.cal_btn_end = ttk.Button(
            self.input_frame,
            text="📅",
            width=3,
        )
        self.cal_btn_end.config(
            command=lambda: CalendarDialog(
                self.root, self.end_entry, self.cal_btn_end
            )
        )
        self.cal_btn_end.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_fetch = ttk.Button(
            self.input_frame, text="検索", command=self.fetch_data
        )
        self.btn_fetch.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="準備完了")
        self.status_label = ttk.Label(
            self.input_frame, textvariable=self.status_var
        )
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

    def _create_tree_view(self) -> None:
        self.paned = ttk.PanedWindow(self.frame, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.tree_frame = ttk.Frame(self.paned)
        self.paned.add(self.tree_frame, weight=3)

        columns = ("SleepTime", "WakeTime", "Reason")
        self.tree = ttk.Treeview(
            self.tree_frame, columns=columns, show="headings"
        )
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

    def _create_details_view(self) -> None:
        self.details_frame = ttk.Frame(self.paned)
        self.paned.add(self.details_frame, weight=1)

        ttk.Label(self.details_frame, text="復帰理由 詳細:").pack(
            anchor=tk.W, pady=(5, 2)
        )
        self.details_text = tk.Text(
            self.details_frame, height=5, wrap=tk.WORD, state=tk.DISABLED
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)

    def on_tree_select(self, _event: Any) -> None:
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

        self.btn_fetch.config(state=tk.DISABLED)
        self.status_var.set("取得中...")
        self.root.update()

        threading.Thread(
            target=self.fetch_task, args=(start_val, end_val), daemon=True
        ).start()

    def fetch_task(self, start: Optional[str], end: Optional[str]) -> None:
        try:
            events = get_wake_events(start, end)
            self.root.after(0, self._on_fetch_success, events)
        except Exception as e:
            self.root.after(0, self._on_fetch_error, str(e))

    def _on_fetch_error(self, err_msg: str) -> None:
        messagebox.showerror(
            "エラー", f"イベントの取得に失敗しました:\n{err_msg}"
        )
        self.btn_fetch.config(state="normal")
        self.status_var.set("取得失敗")

    def _on_fetch_success(self, events: List[Dict[str, str]]) -> None:
        self.btn_fetch.config(state=tk.NORMAL)
        self.status_var.set("取得完了")

        if not events:
            messagebox.showinfo(
                "結果", "指定された期間の復帰イベントは見つかりませんでした。"
            )
            return

        for ev in events:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    ev.get("SleepTime"),
                    ev.get("WakeTime"),
                    ev.get("Reason"),
                ),
            )


def run_gui() -> None:
    root = tk.Tk()
    WakeEventViewerApp(root)
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
        "--start",
        metavar="YYYY-MM-DD",
        help="開始日 (例: 2023-10-01)",
        default="",
    )
    parser.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        help="終了日 (例: 2023-10-31)",
        default="",
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
