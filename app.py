import json
import os
import subprocess
import time
import pymysql
import werkzeug
import threading
from flask import Flask
from flask.json import jsonify
from requests import request
from myFunction.dlib_faceRecognition import get_128_features
from myFunction.dlib_faceRecognition import collect_face_data
from myFunction.dlib_faceRecognition import face_recognition
from myFunction.vpr import license_recognition
from myFunction import qrcode
from myFunction.led import color
from config import dbConfig

led_process = None
is_led_running = False

smoke_process = None
is_smoke_running = False

sensor_process = None
is_sensor_running = False

app = Flask(__name__)
lock = threading.Lock()

@app.route('/')
def hello():
    return 'Welcome to 412!'

# 开启led
@app.route('/led/on', methods=['GET'])
def led_on():
    global led_process
    global is_led_running
    if is_led_running == False:
        is_led_running = True
        led_process = subprocess.Popen(['python', 'myFunction/led.py'])
        print("Led is on!")
        return "Led is on!"
    else:
        print("Led is already on!")
        return "Led is already on!", 503
        

# 关闭led
@app.route('/led/off', methods=['GET'])
def led_off():
    global led_process
    global is_led_running
    if is_led_running:
        is_led_running = False
        led_process.terminate()
        led_process.wait()
        print("Led process terminated.")
        return 'Led is off!'
    else:
        print("Led process not running.")
        return 'Led has not turned on!', 503

# 开启温湿度检测程序
@app.route('/sensor/on', methods=['GET'])
def sensor_on():
    global sensor_process
    global is_sensor_running
    if is_sensor_running == False:
        is_sensor_running = True
        sensor_process = subprocess.Popen(['python', 'myFunction/sensor.py'])
                       #, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("Sensor is on!")
        return "Sensor is on!"
    else:
        print("Sensor is already on!")
        return "Sensor is already on!", 503

# 关闭温湿度检测
@app.route('/sensor/off', methods=['GET'])
def sensor_off():
    global sensor_process
    global is_sensor_running
    if is_sensor_running:
        is_sensor_running = False
        sensor_process.terminate()
        sensor_process.wait()
        print("Sensor process terminated.")
        return 'Sensor is off!'
    else:
        print("Sensor process not running.")
        return 'Sensor has not turned on!', 503


# 获取传感器数据
@app.route('/sensor/data', methods=['GET'])
def sensor_data():
    # 读取传感器数据文件
    data_file = 'FlaskOnPi/data/sensor/sensor_data.json'
    with open(data_file, 'r') as file:
        sensor_data = json.load(file)

    # 返回 JSON 数据
    response = jsonify(sensor_data)
    # 允许所有域访问
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


# 开启烟雾报警器
@app.route('/smoke/on', methods=['GET'])
def smoke_on():
    global smoke_process
    global is_smoke_running
    if is_smoke_running == False:
        is_smoke_running = True
        smoke_process = subprocess.Popen(['python', 'FlaskOnPi/myFunction/smoke.py'])
        print("Smoke is on!")
        return "Smoke is on!"
    else:
        print("Smoke is already on!")
        return "Smoke is already on!", 503
    
# 关闭烟雾报警器
@app.route('/smoke/off', methods=['GET'])
def smoke_off():
    global smoke_process
    global is_smoke_running
    if is_smoke_running:
        is_smoke_running = False
        smoke_process.terminate()
        smoke_process.wait()
        print("Smoke process terminated.")
        return 'Smoke is off!'
    else:
        print("smoke process not running.")
        return 'smoke has not turned on!', 503
    
# 获取人脸照片并处理
@app.route('/upload', methods=['POST'])
def upload_file():
    with lock:
        path_to_save = 'FlaskOnPi/data/face/originFile'
    
        if 'file' not in request.files:
            return 'No file part', 400
        file = request.files['file']
        filename = request.form.get('filename', None)
        print(filename)
        if file.filename == '':
           return 'No selected file', 400
        if file and filename:
            filename = werkzeug.utils.secure_filename(filename)
            file.save(os.path.join(path_to_save, filename))
            print('File saved successfully')
        
            isOK = collect_face_data.main()
            if isOK == False:
                print("识别错误！")
                return 'No face', 400
        
            print("识别成功！获取特征值！")
        
            isOK = get_128_features.main()
            if isOK == False:
                print("获取特征值出错！")
                return 'Something went wrong', 400
        
            print("人脸录入成功！")
            return 'File saved successfully'
        
        else:
            return 'Something went wrong', 400
        
# 人脸识别程序
@app.route('/face/on', methods=['GET'])
def face_on():
    face_info = face_recognition.main()
    if face_info is None:
        return 'Something went wrong', 503
    if face_info == "Timeout":
        return 'Timeout', 504
    if face_info == "Unknown":
        color(0) # 亮红灯
        return 'Unknown'
    
    data = {
        "phone_number" : face_info,
        "timestamp" : time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    color(1) # 亮绿灯
    return jsonify(data)

# 删除人脸数据
@app.route('/face/delete/<phone_number>')
def face_delete(phone_number):
    if phone_number is None:
        return 'Bad request', 400
    try:
        db = pymysql.connect(
            host=dbConfig.host,
            database=dbConfig.database,
            user=dbConfig.user,
            password=dbConfig.password
        )
        cursor = db.cursor()
        sql = f"DELETE FROM FaceInformation WHERE phone_number = '{phone_number}'"
        cursor.execute(sql)
        if cursor.rowcount == 0:
            return f'{phone_number} is not exists!', 400
        db.commit()
        return 'ok'
    except Exception as e:
        print(e)
        db.rollback()
        return 'Something went wrong', 503
    finally:
        db.close()
        
        
# 车牌识别
@app.route('/license', methods=['GET'])
def license():
    license_info = license_recognition.main()
    if license_info is None:
        return 'Something went wrong', 503
    if license_info == "Timeout":
        return 'Timeout', 504
    
    data = {
        "license" : license_info,
        "timestamp" : time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    color(1) # 亮绿灯
    return jsonify(data)

# 二维码识别
@app.route('/qrcode', methods=['GET'])
def qrcode_request():
    qrInfo = qrcode.main()
    if qrInfo == 'Timeout':
        return 'Timeout', 504
    
    if qrInfo == 'ok':
        color(1) # 亮绿灯
    else:
        color(0) # 亮红灯
    return qrInfo

if __name__ == '__main__':
    # cd FlaskOnPi
    # sudo flask run --host=0.0.0.0 --port=5000
    # 因为需要调用摄像头，所以需要sudo权限
    app.run()