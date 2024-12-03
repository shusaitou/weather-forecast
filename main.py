import flet as ft
import requests
from datetime import datetime

def main(page: ft.Page):

    page.title = "気象庁 天気予報アプリ"
    page.scroll = "auto"  # ページ全体にスクロールを許可

    # エリアデータを取得
    area_url = "https://www.jma.go.jp/bosai/common/const/area.json"
    area_data = requests.get(area_url).json()

    # officesから都道府県リストを取得
    offices = area_data['offices']

    # 都道府県リストの作成（名前が都道府県のものを対象）
    prefecture_list = []
    for code, data in offices.items():
        if data['name'].endswith(('都', '道', '府', '県')):
            prefecture_list.append((code, data['name'], data))

    # 都道府県リストをコード順にソート（北から南の順）
    prefecture_list.sort(key=lambda x: x[0])

    # タイトルを追加（背景色を緑に設定）
    title_container = ft.Container(
        content=ft.Text("天気予報アプリ", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        bgcolor=ft.colors.LIGHT_GREEN_100,
        padding=ft.padding.all(10),
        alignment=ft.alignment.center,
    )
    page.add(title_container)

    # 都道府県ドロップダウンの作成
    prefecture_dropdown = ft.Dropdown(
        label="都道府県を選択してください",
        options=[ft.dropdown.Option(code, name) for code, name, data in prefecture_list],
        width=300,
    )

    # 地域選択用のドロップダウン（初期状態では空）
    area_dropdown = ft.Dropdown(
        label="地域を選択してください",
        options=[],
        width=300,
    )

    # 天気予報表示用のコンテナ
    forecast_container = ft.Column(scroll="auto")  # スクロールを許可

    # イベントハンドラの設定はドロップダウン作成後に行う
    prefecture_dropdown.on_change = lambda e: on_prefecture_change(e.control.value)
    area_dropdown.on_change = lambda e: on_area_change(e.control.value)

    # ページに追加
    page.add(prefecture_dropdown)
    page.add(area_dropdown)
    page.add(forecast_container)

    # 地域コードから地域情報へのマッピングを作成
    class10s = area_data.get('class10s', {})
    class15s = area_data.get('class15s', {})
    class20s = area_data.get('class20s', {})

    # 全ての地域コードから地域情報へのマッピングを統合
    area_code_to_info = {}
    area_code_to_info.update(class10s)
    area_code_to_info.update(class15s)
    area_code_to_info.update(class20s)

    def on_prefecture_change(prefecture_code):
        if not prefecture_code:
            return
        # 選択された都道府県の子供の地域コードを取得
        children_codes = offices[prefecture_code].get('children', [])

        # 地域ドロップダウンを更新
        area_dropdown.options = [
            ft.dropdown.Option(code, area_code_to_info[code]['name'])
            for code in children_codes if code in area_code_to_info
        ]
        area_dropdown.value = None
        area_dropdown.update()

        # 天気予報をクリア
        forecast_container.controls.clear()
        forecast_container.update()

    def on_area_change(area_code):
        if not area_code:
            return

        # 選択された地域の情報を取得
        area_data_item = area_code_to_info.get(area_code)
        if not area_data_item:
            forecast_container.controls.clear()
            forecast_container.controls.append(ft.Text("選択された地域のデータが見つかりませんでした。", color="red"))
            forecast_container.update()
            return

        area_name = area_data_item['name']
        # 親コードから適切なoffice_codeを取得
        office_code = area_data_item.get('parent')

        # 天気予報を取得
        forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{office_code}.json"
        forecast_response = requests.get(forecast_url)

        if forecast_response.status_code != 200:
            forecast_container.controls.clear()
            forecast_container.controls.append(ft.Text("天気データの取得に失敗しました。", color="red"))
            forecast_container.update()
            return

        forecast_data = forecast_response.json()

        # 選択されたエリアの天気予報を抽出
        forecast_container.controls.clear()

        # タイトルを追加
        forecast_container.controls.append(
            ft.Text(f"{area_name}の天気予報", style=ft.TextThemeStyle.TITLE_MEDIUM)
        )

        found = False  # データが見つかったかのフラグ

        # 日付ごとにデータをまとめるための辞書
        forecast_by_date = {}

        # forecast_dataはリストになっている
        for series in forecast_data:
            time_series = series.get('timeSeries', [])
            for ts in time_series:
                timeDefines = ts.get('timeDefines', [])
                areas_in_ts = ts.get('areas', [])
                for area in areas_in_ts:
                    if area.get('area', {}).get('code') == area_code:
                        found = True  # データが見つかった
                        # キーを収集
                        data_keys = [key for key in area.keys() if key not in ['area']]
                        for i, time_define in enumerate(timeDefines):
                            dt_time_define = datetime.fromisoformat(time_define.replace('Z', '+00:00'))
                            date_str = dt_time_define.strftime('%Y-%m-%d')
                            time_str = dt_time_define.strftime('%H:%M')
                            # 日付ごとにデータをまとめる
                            if date_str not in forecast_by_date:
                                forecast_by_date[date_str] = []
                            # 各データを取得
                            data = {}
                            for key in data_keys:
                                values = area.get(key, [])
                                value = values[i] if i < len(values) else None
                                data[key] = value
                            # 時刻とデータを保存
                            forecast_by_date[date_str].append({'time': time_str, 'data': data})

        if not found:
            forecast_container.controls.append(ft.Text("天気データが見つかりませんでした。", color="red"))
        else:
            # 日付順にソート
            for date in sorted(forecast_by_date.keys()):
                day_data = forecast_by_date[date]
                # カードを作成
                card = ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text(f"{date}", weight=ft.FontWeight.BOLD, size=18),
                            ft.Divider(),
                            ft.Row([
                                create_forecast_column(item['time'], item['data']) for item in day_data
                            ], scroll="auto"),
                        ]),
                        padding=10,
                    )
                )
                forecast_container.controls.append(card)

        forecast_container.update()

    def create_forecast_column(time_str, data):
        # 各時間の予報をカードとして作成
        weather_code = data.get('weatherCodes', '0')
        if isinstance(weather_code, list):
            weather_code = weather_code[0]
        icon_url = f"https://www.jma.go.jp/bosai/forecast/img/{weather_code}.png"

        # キー名を日本語に変換
        key_labels = {
            'weathers': '天気',
            'winds': '風',
            'pops': '降水確率',
            'temps': '気温',
            'waves': '波'
        }

        content_controls = [
            ft.Text(f"{time_str}", weight=ft.FontWeight.BOLD, size=16),
            ft.Image(src=icon_url, width=50, height=50),
        ]

        for key in ['weathers', 'temps', 'pops', 'winds', 'waves']:
            value = data.get(key)
            if isinstance(value, list):
                value = value[0] if value else '---'
            if value is None:
                continue
            # フォーマット調整
            if key == 'pops' and value != '---':
                value += '%'
            elif key == 'temps' and value != '---':
                value += '℃'
            # ラベル
            label = key_labels.get(key, key)
            # テキストを追加
            content_controls.append(ft.Text(f"{label}: {value}", size=14))

        return ft.Container(
            content=ft.Column(content_controls, alignment=ft.MainAxisAlignment.CENTER),
            padding=5,
            alignment=ft.alignment.center,
            width=150,
            border=ft.border.all(0.5, ft.colors.GREY),
            border_radius=10,
        )

    page.update()


ft.app(target=main)