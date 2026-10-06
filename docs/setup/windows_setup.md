# Windowsでの初期設定

GitHubからtabsdkをダウンロードし、`scripts/tabsdk.bat`を起動するまでの手順です。コマンドはPowerShellに**1行ずつ入力してEnterキーを押し、処理が終わってから次へ進んでください**。

## 1. uvをインストールする

PowerShellを開き、次の1行を実行します。この操作はどのフォルダーからでもできます。`winget`は使いません。

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

これは[uv公式のWindows向けインストール方法](https://docs.astral.sh/uv/getting-started/installation/)です。完了したらPowerShellを開き直します。VS Codeのターミナルを使う場合は、VS Codeを完全に終了してから開き直してください。

次のコマンドで、uvのバージョンが表示されることを確認します。

```powershell
uv --version
```

## 2. tabsdkをダウンロードする

[tabsdkのGitHubページ](https://github.com/tomohiro-ono-works/tabsdk)を開き、**Code → Download ZIP**を選びます。

## 3. ZIPを展開する

ダウンロードしたZIPを右クリックして**すべて展開**を選びます。展開後、`pyproject.toml`と`scripts`フォルダーが入っている`tabsdk-main`フォルダーを開きます。

## 4. PowerShellでtabsdkフォルダーへ移動する

エクスプローラーで手順3の`tabsdk-main`フォルダーを開き、上部のアドレスバーに`powershell`と入力してEnterキーを押します。そのフォルダーを作業場所とするPowerShellが開きます。

すでにPowerShellを開いている場合は、実際の展開先に合わせて次のように移動できます。

```powershell
cd "C:\展開した場所\tabsdk-main"
```

## 5. パッケージをインストールする

`pyproject.toml`があるフォルダーで、次の1行を実行し、完了まで待ちます。

```powershell
uv sync --no-dev --system-certs
```

`--no-dev`は利用時に不要なテスト用パッケージを除外します。`--system-certs`はWindowsに登録された証明書を使ってパッケージをダウンロードします。

## 6. 利用方法に合わせて進む

GUI で使う場合は、次のコマンドでランチャーを起動し、[GUI 利用ガイド](../user/gui/usage.md)に進みます。
Python のコードから使う場合は、手順 5 までで環境の準備は完了です。
[ライブラリ利用ガイド](../user/library/usage.md)と[公開 API リファレンス](../user/library/api_reference.md)を参照してください。

同じPowerShellで次の1行を実行します。`1`、`2`、`3`、`4`、`9`のメニューが表示されたら、使いたい番号を入力してEnterキーを押します。`9`は終了です。

```powershell
.\scripts\tabsdk.bat
```

## うまくいかないとき

- **`uv`が見つからない:** VS CodeやPowerShellを完全に終了して開き直します。公式インストーラーの通常の配置先は`C:\Users\<ユーザー名>\.local\bin\uv.exe`です。ファイルが存在するのに見つからない場合は、その`bin`フォルダーをWindowsのユーザー環境変数`Path`に追加します。
- **`pyproject.toml`が見つからない:** 手順4で、`scripts`ではなく`pyproject.toml`が入っている`tabsdk-main`フォルダーへ移動します。
- **`invalid peer certificate: UnknownIssuer`が出る:** 手順5で`--system-certs`を付けたことを確認します。それでも同じエラーが出る場合は、ネットワーク管理者に`https://pypi.org/`への接続で証明書を信頼できないことを伝えてください。
