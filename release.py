import zipfile
import os
import re

class ReleasePackager:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.files_to_include = [
            "event_viewer.py",
            "LICENSE",
            "README.md",
            "requirements.txt"
        ]

    def _get_version(self) -> str | None:
        version = input("バージョン番号を入力してください (例: 0.2.3): ").strip()
        if not version:
            print("エラー: バージョン番号が入力されませんでした。")
            return None

        # セキュリティ対策: バージョン番号のバリデーション (パス・トラバーサル対策)
        # 英数字、ドット、ハイフンのみを許可する
        if not re.match(r"^[a-zA-Z0-9.-]+$", version):
            print("エラー: 不正なバージョン番号です。英数字、ドット(.)、ハイフン(-)のみ使用できます。")
            return None
        return version

    def _get_missing_files(self) -> list[str]:
        missing_files = []
        for f in self.files_to_include:
            target_path = os.path.join(self.script_dir, f)
            if not os.path.exists(target_path):
                missing_files.append(f)
        return missing_files

    def _create_zip(self, version: str) -> None:
        zip_filename = f"eventview_{version}.zip"
        zip_filepath = os.path.join(self.script_dir, zip_filename)

        print(f"\n作成するZIPファイル: {zip_filepath}")
        print("含めるファイル:")
        for f in self.files_to_include:
            print(f"  - {f}")

        try:
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in self.files_to_include:
                    target_path = os.path.join(self.script_dir, f)
                    # ZIP内のパスはファイル名だけにする
                    zipf.write(target_path, arcname=f)
            print(f"\n成功: {zip_filepath} を作成しました。")
        except Exception as e:
            print(f"\nエラー: ZIPファイルの作成中にエラーが発生しました: {e}")

    def run(self) -> None:
        print("リリース用ZIPファイルを作成します。")
        version = self._get_version()
        if not version:
            return

        missing_files = self._get_missing_files()
        if missing_files:
            print(f"エラー: 以下の必須ファイルが見つかりません: {', '.join(missing_files)}")
            print("リリース用ZIPの作成を中止します。")
            return

        self._create_zip(version)

def create_release_zip() -> None:
    ReleasePackager().run()

if __name__ == "__main__":
    create_release_zip()
    input("\n終了するには何かキーを押してください...")
