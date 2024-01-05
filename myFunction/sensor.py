import signal
import RPi.GPIO as GPIO
import dht11
import json
import time

def cleanup_handler(signum, frame):
    print("Received SIGTERM. Cleaning up...")
    raise KeyboardInterrupt
# 注册信号处理函数
signal.signal(signal.SIGTERM, cleanup_handler)

# initialize GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()

# 配置数据线的针
instance = dht11.DHT11(pin=17)

def sensor_loop():
    while True:
        result = instance.read()
        # 数据合法
        if result.is_valid():
            print('Got legal data!')

            # 创建包含温湿度和时间的字典
            data = {
                "temperature": result.temperature,
                "humidity": result.humidity,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            # 将字典转换为 JSON 字符串
            json_data = json.dumps(data)

            # 将 JSON 数据写入文件
            with open("FlaskOnPi/data/sensor/sensor_data.json", "w") as file:
                file.write(json_data)
        else:
            print('Data has problems!')

        time.sleep(1)

#程序入口
if __name__ == '__main__':
    try:
        sensor_loop()
    except KeyboardInterrupt:
        GPIO.cleanup()