import zipfile
import os

def create_release_zip():
    print("リリース用ZIPファイルを作成します。")
    version = input("バージョン番号を入力してください (例: 0.2.3): ").strip()

    if not version:
        print("エラー: バージョン番号が入力されませんでした。")
        return

    zip_filename = f"eventview_{version}.zip"

    files_to_include = [
        "event_viewer.py",
        "LICENSE",
        "README.md"
    ]

    # 必須ファイルの存在確認
    missing_files = []
    for f in files_to_include:
        if not os.path.exists(f):
            missing_files.append(f)

    if missing_files:
        print(f"エラー: 以下の必須ファイルが見つかりません: {', '.join(missing_files)}")
        print("リリース用ZIPの作成を中止します。")
        return

    print(f"\n作成するZIPファイル: {zip_filename}")
    print("含めるファイル:")
    for f in files_to_include:
        print(f"  - {f}")

    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in files_to_include:
                zipf.write(f)
        print(f"\n成功: {zip_filename} を作成しました。")
    except Exception as e:
        print(f"\nエラー: ZIPファイルの作成中にエラーが発生しました: {e}")

if __name__ == "__main__":
    create_release_zip()
