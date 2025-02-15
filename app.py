from flask import Flask, render_template, request, redirect, url_for
import requests
import threading
import time

app = Flask(__name__)

API_KEY = '463b8318bfa98dfa964b8ee76162e9e2'
CITY = 'Fukuoka'
CURRENT_URL = f'http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&lang=ja&units=metric'
FORECAST_URL = f'http://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={API_KEY}&units=metric&lang=ja'
LINE_TOKEN = 'mmlIXs9PvJ14qh63pSp7FHqauKfo38u9Ftiur00Q3VK'
LINE_URL = 'https://notify-api.line.me/api/notify'
HEADERS = {'Authorization': f'Bearer {LINE_TOKEN}'}

weather_stop_event = threading.Event()
hydration_stop_event = threading.Event()

def get_weather_data():
    """現在の天気を取得"""
    response = requests.get(CURRENT_URL)
    return response.json() if response.status_code == 200 else None

def get_forecast_data():
    """天気予報（最大5日間、3時間ごとのデータ）を取得"""
    response = requests.get(FORECAST_URL)
    return response.json() if response.status_code == 200 else None

def send_line_notify(message):
    payload = {'message': message}
    requests.post(LINE_URL, headers=HEADERS, data=payload)

def generate_hydration_message(temperature):
    """気温ごとの水分補給メッセージを作成"""
    if temperature >= 8:
        return f"現在の気温は{temperature}度です。🥵🥵🥵熱中症に注意し、10分.おきに水分補給をしてください！"
    elif temperature >= 7:
        return f"現在の気温は{temperature}度です。15分.おきに水分補給を心がけましょう。"
    else:
        return f"現在の気温は{temperature}度です。水分補給は20分.おきに、コップ一杯以上(200ml~)を心がけましょう。\nこの通知は20分ごとに繰り返します。"

def generate_weather_message(weather, forecast, interval):
    """現在、3時間後、6時間後の天気情報を含むメッセージを作成"""
    current_temp = weather['main']['temp']
    current_description = weather['weather'][0]['description']
    current_rain = weather.get('rain', {}).get('1h', 0)
    
    # メインメッセージ
    forecast_message = f"場所: {CITY}\n現在の天気: {current_description}, 気温: {current_temp}℃, 降雨量: {current_rain} mm/h\n"
    
    # 天気に応じた追加メッセージ
    if "rain" in current_description.lower():
        forecast_message += "☔☔傘を忘れずに！\n"
    elif "cloud" in current_description.lower():
        forecast_message += "今日は曇りです。過ごしやすい天気かもしれません。\n"
    elif "clear" in current_description.lower():
        forecast_message += "🌤いい天気です！外出に最適です。\n"
    else:
        forecast_message += "天気は落ち着いています。\n"
    
    # 気温に応じた追加メッセージ
    if current_temp >= 3:
        forecast_message += "🥵熱中症対策を忘れずに！\n\n\n"
    elif current_temp < 15:
        forecast_message += "🥶寒いです。暖かい服装でお過ごしください。\n\n\n"
    else:
        forecast_message += "今日は過ごしやすい気温です。\n\n\n"
    
    # 3時間後と6時間後の予報データ
    for i, hour in enumerate([3, 6], start=1):
        forecast_data = forecast['list'][i]
        temp = forecast_data['main']['temp']
        description = forecast_data['weather'][0]['description']
        rain = forecast_data.get('rain', {}).get('3h', 0)
        pop = forecast_data.get('pop', 0) * 100  # 降水確率 (0-1を%に変換)

        # 基本情報
        forecast_message += f"{hour}時間後の天気: {description}, 気温: {temp}℃, 降雨量: {rain} mm/3h, 降水確率: {pop:.1f}%\n"

        # 降水確率40%以上の場合の追加メッセージ
        if pop >= 40:
            forecast_message += "🌧 降水確率が40%以上です。傘☔の準備をお忘れなく！\n"

    forecast_message += f"この通知は{interval}時間ごとに繰り返されます。"
    return forecast_message




def start_hydration_notification():
    """水分補給通知を開始"""
    temperature = get_weather_data()['main']['temp']
    send_line_notify(generate_hydration_message(temperature))
    
    while not hydration_stop_event.is_set():
        if temperature >= 35:
            interval = 10 * 60
        elif temperature >= 30:
            interval = 15 * 60
        else:
            interval = 20 * 60
        time.sleep(interval)
        temperature = get_weather_data()['main']['temp']
        send_line_notify(generate_hydration_message(temperature))

def start_weather_notification(interval):
    """指定間隔で天気通知を送信"""
    weather = get_weather_data()
    forecast = get_forecast_data()
    if weather and forecast:
        send_line_notify(generate_weather_message(weather, forecast, interval))
    
    while not weather_stop_event.is_set():
        time.sleep(interval * 60 * 60)
        weather = get_weather_data()
        forecast = get_forecast_data()
        if weather and forecast:
            send_line_notify(generate_weather_message(weather, forecast, interval))

@app.route('/')
def index():
    current_weather = get_weather_data()
    forecast = get_forecast_data()
    return render_template('index.html', current_weather=current_weather, forecast=forecast)

@app.route('/start-hydration-notification', methods=['POST'])
def start_hydration():
    hydration_stop_event.clear()
    threading.Thread(target=start_hydration_notification).start()
    return redirect(url_for('index'))

@app.route('/stop-hydration-notification', methods=['POST'])
def stop_hydration():
    hydration_stop_event.set()
    send_line_notify("水分補給通知が停止されました。")
    return redirect(url_for('index'))

@app.route('/start-weather-notification/<int:interval>', methods=['POST'])
def start_weather(interval):
    weather_stop_event.clear()
    threading.Thread(target=start_weather_notification, args=(interval,)).start()
    return redirect(url_for('index'))

@app.route('/stop-weather-notification', methods=['POST'])
def stop_weather():
    weather_stop_event.set()
    send_line_notify("天気通知が停止されました。")
    return redirect(url_for('index'))



rain_alert_stop_event = threading.Event()

def start_rain_alert():
    """雨が降る前の通知を開始"""
    while not rain_alert_stop_event.is_set():
        forecast = get_forecast_data()
        if forecast:
            # 次の予報データを確認 (3時間以内の予報)
            for forecast_data in forecast['list'][:3]:
                rain = forecast_data.get('rain', {}).get('3h', 0)
                pop = forecast_data.get('pop', 0) * 100  # 降水確率をパーセントに変換
                time_text = forecast_data['dt_txt']  # 時間情報
                
                # 降水確率50%以上、または降雨量が一定値以上の場合通知
                if pop >= 50 or rain > 0:
                    message = (
                        f"雨の予報があります。\n"
                        f"予想時間: {time_text}\n"
                        f"降水確率: {pop:.1f}%\n"
                        f"予想降雨量: {rain:.1f} mm\n"
                        "傘を忘れずに！"
                    )
                    send_line_notify(message)
                    break  # 一度通知したら次回まで待つ
        
        time.sleep(30 * 60)  # 30分ごとにチェック

@app.route('/start-rain-alert', methods=['POST'])
def start_rain_alert_route():
    rain_alert_stop_event.clear()
    threading.Thread(target=start_rain_alert).start()
    send_line_notify("臨時雨通知が開始されました。\n雨の予報を監視中です。。")
    return redirect(url_for('index'))

@app.route('/stop-rain-alert', methods=['POST'])
def stop_rain_alert():
    rain_alert_stop_event.set()
    send_line_notify("臨時雨通知が停止されました。")
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)