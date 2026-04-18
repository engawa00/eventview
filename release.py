import zipfile
import os

def create_release_zip():
    print("リリース用ZIPファイルを作成します。")
    version = input("バージョン番号を入力してください (例: 0.2.3): ").strip()

    if not version:
        print("エラー: バージョン番号が入力されませんでした。")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    zip_filename = f"eventview_{version}.zip"
    zip_filepath = os.path.join(script_dir, zip_filename)

    # スクリプトディレクトリからの相対パスでファイルを探す
    files_to_include = [
        "event_viewer.py",
        "LICENSE",
        "README.md"
    ]

    # 必須ファイルの存在確認
    missing_files = []
    for f in files_to_include:
        target_path = os.path.join(script_dir, f)
        if not os.path.exists(target_path):
            missing_files.append(f)

    if missing_files:
        print(f"エラー: 以下の必須ファイルが見つかりません: {', '.join(missing_files)}")
        print("リリース用ZIPの作成を中止します。")
        return

    print(f"\n作成するZIPファイル: {zip_filepath}")
    print("含めるファイル:")
    for f in files_to_include:
        print(f"  - {f}")

    try:
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in files_to_include:
                target_path = os.path.join(script_dir, f)
                # ZIP内のパスはファイル名だけにする
                zipf.write(target_path, arcname=f)
        print(f"\n成功: {zip_filepath} を作成しました。")
    except Exception as e:
        print(f"\nエラー: ZIPファイルの作成中にエラーが発生しました: {e}")

if __name__ == "__main__":
    create_release_zip()
    input("\n終了するには何かキーを押してください...")
