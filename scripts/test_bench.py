import os
import pytest
from unittest.mock import patch
from scripts.bench import original, cached

# テストの目的: os.environ から 'SystemRoot' が取得できるか、
# および取得できない場合のデフォルト値 ('C:\Windows') のフォールバックが機能するかを検証します。
#
# D:\WinNT を使用する理由:
# デフォルト値 ('C:\Windows') とは明確に異なる値をモックとして注入することで、
# 「環境変数が正しく読み取られた結果」なのか、「取得に失敗してデフォルト値が使われた結果」なのかを
# 区別して厳密にテストできるようにするためです。

@patch.dict(os.environ, {"SystemRoot": "D:\\WinNT"}, clear=True)
def test_original_with_systemroot():
    expected = os.path.join("D:\\WinNT", "System32", "wevtutil.exe")
    assert original() == expected

@patch.dict(os.environ, {}, clear=True)
def test_original_without_systemroot():
    expected = os.path.join("C:\\Windows", "System32", "wevtutil.exe")
    assert original() == expected

@patch.dict(os.environ, {"SystemRoot": "D:\\WinNT"}, clear=True)
def test_cached_with_systemroot():
    cached.cache_clear()
    expected = os.path.join("D:\\WinNT", "System32", "wevtutil.exe")
    assert cached() == expected

@patch.dict(os.environ, {}, clear=True)
def test_cached_without_systemroot():
    cached.cache_clear()
    expected = os.path.join("C:\\Windows", "System32", "wevtutil.exe")
    assert cached() == expected
