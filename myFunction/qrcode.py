import sys
import time
import cv2
import pymysql
from pyzbar import pyzbar
sys.path.append('/home/412_pi/FlaskOnPi/config')
import dbConfig

def decode_qr_code(frame):
    # 转换为灰度图像
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # 检测二维码
    barcodes = pyzbar.decode(gray)
    # 解码并返回结果
    qr_codes = []
    for barcode in barcodes:
        barcode_data = barcode.data.decode("utf-8")
        qr_codes.append(barcode_data)
    return qr_codes

def query(phone):
    try:
        db = pymysql.connect(
            host=dbConfig.host,
            database=dbConfig.database,
            user=dbConfig.user,
            password=dbConfig.password
        )
        cursor = db.cursor()
        sql = f"SELECT * FROM FaceInformation WHERE phone_number = '{phone}'"
        cursor.execute(sql)
        length = len(cursor.fetchall())
        # print(cursor.fetchone()[0])
        
        if length > 0:
            return True
        else:
            return False
    except Exception as e:
        print(e)
        return False
    finally:
        db.close()

def main():
    print("二维码识别")
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    start_time = time.time()
    timeout_time = 60
    try:
        while True:
            if time.time() - start_time > timeout_time:
                return 'Timeout'
                
            # 读取视频帧
            ret, frame = cap.read()

            # 解码二维码
            if ret:
                qr_codes = decode_qr_code(frame)
                
                for qr_code in qr_codes:
                    print(qr_code)
                    if query(qr_code):
                        return 'ok'
                    else:
                        return 'off-limits'
                        
    finally:
        cap.release()


if __name__ == '__main__':
    main()
