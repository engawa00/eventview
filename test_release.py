import pytest
from unittest.mock import patch
import os
import zipfile
import release

@patch('builtins.input')
def test_create_release_zip(mock_input):
    # Setup test variables
    test_version = "test-0.0.1"
    mock_input.return_value = test_version

    script_dir = os.path.dirname(os.path.abspath(release.__file__))
    expected_zip_path = os.path.join(script_dir, f"eventview_{test_version}.zip")

    # Ensure the zip file doesn't exist before the test
    if os.path.exists(expected_zip_path):
        os.remove(expected_zip_path)

    try:
        # Run the target function
        release.create_release_zip()

        # Verify the ZIP file was created in the correct location
        assert os.path.exists(expected_zip_path), f"Expected ZIP file at {expected_zip_path} was not found"

        # Verify the ZIP file contents
        with zipfile.ZipFile(expected_zip_path, 'r') as zipf:
            zip_contents = zipf.namelist()
            assert "event_viewer.py" in zip_contents
            assert "LICENSE" in zip_contents
            assert "README.md" in zip_contents
            assert "requirements.txt" in zip_contents
            assert len(zip_contents) == 4 # Ensure exactly 4 files are included

    finally:
        # Teardown: Clean up the generated ZIP file
        if os.path.exists(expected_zip_path):
            os.remove(expected_zip_path)

@patch('builtins.input')
@patch('builtins.print')
def test_create_release_zip_invalid_version(mock_print, mock_input):
    # ../1.0 is invalid due to path traversal characters
    test_version = "../1.0"
    mock_input.return_value = test_version

    # Before running, count zip files in the script directory
    script_dir = os.path.dirname(os.path.abspath(release.__file__))
    zip_files_before = [f for f in os.listdir(script_dir) if f.endswith(".zip")]

    release.create_release_zip()

    # Check for error message
    mock_print.assert_any_call("エラー: 不正なバージョン番号です。英数字、ドット(.)、ハイフン(-)のみ使用できます。")

    # Verify no new ZIP files were created
    zip_files_after = [f for f in os.listdir(script_dir) if f.endswith(".zip")]
    assert len(zip_files_before) == len(zip_files_after)

@pytest.mark.parametrize("empty_val", ["", "   ", "\t", "\n"])
@patch('builtins.input')
@patch('builtins.print')
def test_create_release_zip_empty_version(mock_print, mock_input, empty_val):
    # Empty string should be handled
    mock_input.return_value = empty_val

    release.create_release_zip()

    # Check for error message
    mock_print.assert_any_call("エラー: バージョン番号が入力されませんでした。")


@patch('builtins.input')
@patch('builtins.print')
@patch('os.path.exists')
def test_create_release_zip_missing_files(mock_exists, mock_print, mock_input):
    mock_input.return_value = "0.0.1"

    # Mock os.path.exists to return False for 'LICENSE' to trigger missing files error
    def exists_side_effect(path):
        if 'LICENSE' in path:
            return False
        return True

    mock_exists.side_effect = exists_side_effect

    release.create_release_zip()

    # Check for error message
    mock_print.assert_any_call("エラー: 以下の必須ファイルが見つかりません: LICENSE")
    mock_print.assert_any_call("リリース用ZIPの作成を中止します。")


@patch('builtins.input')
@patch('builtins.print')
@patch('zipfile.ZipFile')
def test_create_release_zip_exception(mock_zipfile, mock_print, mock_input):
    mock_input.return_value = "0.0.1"

    # Force an exception when creating the zip file
    mock_zipfile.side_effect = Exception("Test Exception")

    release.create_release_zip()

    # Check for error message
    mock_print.assert_any_call("\nエラー: ZIPファイルの作成中にエラーが発生しました: Test Exception")
