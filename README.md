# WallDeck

Windows の仮想デスクトップと物理モニターごとに壁紙を管理する常駐アプリケーションです。

- 仮想デスクトップごとに、各モニターの壁紙を設定
- デスクトップ切替を監視して自動適用
- モニター名、番号、解像度を階層表示
- Center / Tile / Stretch / Fit / Fill / Span の共通設定
- タスクトレイ常駐

## 開発環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m walldeck
```

診断用の読み取り専用COMプローブと仮想デスクトップ監視:

```powershell
python -m walldeck --probe
python -m walldeck --watch
```

設定は `%LOCALAPPDATA%\WallDeck\config.json` に保存されます。

## Windows実行ファイルの作成

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\WallDeck.spec
```

単一ファイルの実行可能ファイルが `dist\WallDeck.exe` に生成されます。
