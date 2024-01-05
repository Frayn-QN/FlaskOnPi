#!/usr/bin/python
# -*- coding:UTF-8 -*-
##===============================================================================
# | file       :   main.py
# | author     :   Wang-wonk(CSDN); ZhengHao; Waveshare .Ltd
# | date       :   2020-04-27
# | function   :   执行车牌识别的主代码，使用一块1.54英寸的墨水屏显示指示，工作后
#                  自动将处理画面和识别结果显示HDMI屏和墨水屏上，运行前请检查本代
#                  码基于opencv 3.4.1和python 2.7。
##===============================================================================
#
#=============================== PART-1 模块导入 ================================
import logging
import time
import cv2
from . import predict

#=============================== PART-2 主函数 ==================================
def main():
    try:
        # 摄像头
        camera = cv2.VideoCapture(0)     # 定义摄像头对象，参数0表示第一个摄像头，默认640x480
        camera.set(cv2.CAP_PROP_FRAME_WIDTH,  960)  # 重设获取图像分辨率(predict.py设定了最大1000)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)  # 图像越大处理速度越慢，树莓派不开超频时会卡
        if camera is None:               # 摄像头打开失败
            print(u'检测摄像头是否连接正常!')
            exit()
        fps = 24                         # 帧率

        # 向量机图像学习分类训练
        predictor = predict.CardPredictor()
        predictor.train_svm()
        logging.info(u'SVM学习训练完毕')

        start_time = time.time()
        timeout_second = 60
        while True:
            res, cur_frame = camera.read()             # 读取视频流
            if res != True:
                break
            
            if time.time() - start_time > timeout_second:
                raise TimeoutError
            
            # img = cv2.imread('./lib_Pic/test/timg.jpg')
            cv2.imwrite("/home/412_pi/FlaskOnPi/data/license/output.jpg", cur_frame)
            # 车牌识别
            carchar, roi, color = predictor.predict(cur_frame)              # 返回识别到的字符，定位的车牌图像，车牌颜色
            # 此处进行简单的过滤
            if carchar is not None and carchar[1].isdigit() == False and\
               carchar.count('1') <= 5 and len(carchar) >= 7 and\
               len(carchar) <= 8:
                print(u'识别结果:{0:s}\n'.format(carchar))
                return carchar

    # 异常处理
    except TimeoutError:
        return 'Timeout'
    except IOError as e:
        logging.info(e)
    except KeyboardInterrupt:
        logging.info("ctrl + c:")
        exit()
    finally:
        camera.release()                # 释放摄像头
    

if __name__ == '__main__':
    main()

##================================== FILE END ===================================

