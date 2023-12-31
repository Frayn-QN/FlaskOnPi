#!/usr/bin/python
# -*- coding: utf-8 -*-
import cv2
import numpy as np
from numpy.linalg import norm
import os
import json
import copy

SZ = 20                # 训练图片长宽
MAX_WIDTH = 1000       # 原始图片最大宽度
Min_Area =  2000       # 车牌区域至少的像素面积，车牌在图像中所占的面积显然与距离有关
PROVINCE_START = 1000

# 定义路径
svmdir_path = '/home/412_pi/FlaskOnPi/data/license/svm'
svm_path = os.path.join(svmdir_path, 'svm.dat')
svmzh_path = os.path.join(svmdir_path, 'svmchinese.dat')
config_path = '/home/412_pi/FlaskOnPi/myFunction/vpr/config.js'

def imreadex(filename):
    return cv2.imdecode(np.fromfile(filename, dtype=np.uint8), cv2.IMREAD_COLOR)


def point_limit(point):
    if point[0] < 0:
        point[0] = 0
    if point[1] < 0:
        point[1] = 0


# 根据设定的阈值和图片直方图，找出波峰，用于分隔字符
def find_waves(threshold, histogram):
    up_point = -1  # 上升点
    is_peak = False
    if histogram[0] > threshold:
        up_point = 0
        is_peak = True
    wave_peaks = []
    for i, x in enumerate(histogram):
        if is_peak and x < threshold:
            if i - up_point > 2:
                is_peak = False
                wave_peaks.append((up_point, i))
        elif not is_peak and x >= threshold:
            is_peak = True
            up_point = i
    if is_peak and up_point != -1 and i - up_point > 4:
        wave_peaks.append((up_point, i))
    return wave_peaks


# 根据找出的波峰，分隔图片，从而得到逐个字符图片
def seperate_card(img, waves):
    part_cards = []
    for wave in waves:
        part_cards.append(img[:, wave[0]:wave[1]])
    return part_cards


# 返回一个列表中出现次数最多的字符串
def findmaxstr(lt):
    index1 = 0  # 记录出现次数最多的元素下标
    max = 0     # 记录最大的元素出现次数
    for i in range(len(lt)):
        flag = 0              # 记录每一个元素出现的次数
        for j in range(i + 1, len(lt)):  # 遍历i之后的元素下标
            if lt[j] == lt[i]:
                flag += 1  # 每当发现与自己相同的元素，flag+1
        if flag > max:     # 如果此时元素出现的次数大于最大值，记录此时元素的下标
            max = flag
            index1 = i
    return lt[index1]      # 返回出现最多的元素

#================================================================================
# 来自opencv的sample，用于svm训练
def deskew(img):
    m = cv2.moments(img)
    if abs(m['mu02']) < 1e-2:
        return img.copy()
    skew = m['mu11'] / m['mu02']
    M = np.float32([[1, skew, -0.5 * SZ * skew], [0, 1, 0]])
    img = cv2.warpAffine(img, M, (SZ, SZ), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR)
    return img


# 来自opencv的sample，用于svm训练
def preprocess_hog(digits):
    samples = []
    for img in digits:
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1)
        mag, ang = cv2.cartToPolar(gx, gy)
        bin_n = 16
        bin = np.int32(bin_n * ang / (2 * np.pi))
        bin_cells = bin[:10, :10], bin[10:, :10], bin[:10, 10:], bin[10:, 10:]
        mag_cells = mag[:10, :10], mag[10:, :10], mag[:10, 10:], mag[10:, 10:]
        hists = [np.bincount(b.ravel(), m.ravel(), bin_n) for b, m in zip(bin_cells, mag_cells)]
        hist = np.hstack(hists)

        # transform to Hellinger kernel
        eps = 1e-7
        hist /= hist.sum() + eps
        hist = np.sqrt(hist)
        hist /= norm(hist) + eps

        samples.append(hist)
    return np.float32(samples)

#================================================================================

# 不能保证包括所有省份
provinces = [
    "zh_cuan", "川","zh_e",    "鄂",
    "zh_gan",  "赣","zh_gan1", "甘",
    "zh_gui",  "贵", "zh_gui1","桂",
    "zh_hei",  "黑","zh_hu",   "沪",
    "zh_ji",   "冀","zh_jin",  "津",
    "zh_jing", "京","zh_jl",   "吉",
    "zh_liao", "辽","zh_lu",   "鲁",
    "zh_meng", "蒙","zh_min",  "闽",
    "zh_ning", "宁","zh_qing", "靑",
    "zh_qiong","琼","zh_shan", "陕",
    "zh_su",   "苏","zh_sx",   "晋",
    "zh_wan",  "皖","zh_xiang","湘",
    "zh_xin",  "新","zh_yu",   "豫",
    "zh_yu1",  "渝","zh_yue",  "粤",
    "zh_yun",  "云","zh_zang", "藏",
    "zh_zhe",  "浙"
]


class StatModel(object):
    def load(self, fn):
        self.model = self.model.load(fn)

    def save(self, fn):
        self.model.save(fn)


class SVM(StatModel):       # SVM设置
    def __init__(self, C=1, gamma=0.5):
        self.model = cv2.ml.SVM_create()
        self.model.setGamma(gamma)
        self.model.setC(C)
        self.model.setKernel(cv2.ml.SVM_RBF)
        self.model.setType(cv2.ml.SVM_C_SVC)

    # 训练svm
    def train(self, samples, responses):
        self.model.train(samples, cv2.ml.ROW_SAMPLE, responses)

    # 字符识别
    def predict(self, samples):
        r = self.model.predict(samples)
        return r[1].ravel()

# 将图片识别的函数与属性封装起来
class CardPredictor:
    def __init__(self):
        self.model = SVM(C=1, gamma=0.5)        # 识别英文字母和数字
        self.modelchinese = SVM(C=1, gamma=0.5) # 识别中文
        # 车牌识别的部分参数保存在js中，便于根据图片分辨率做调整
        f = open(config_path)
        j = json.load(f)
        for c in j["config"]:
            print(c)
            if c["open"]:
                self.cfg = c.copy()
                break
        else:
            raise RuntimeError('没有设置有效配置参数')

    def __del__(self):
        self.save_traindata()

    def train_svm(self):# 保存svm训练数据
        
        if os.path.exists(svm_path):
            self.model.load(svm_path)
        else: # 训练数据，可直接使用数据
            chars_train = []
            chars_label = []
            for root, dirs, files in os.walk("./lib_Pic/train/chars2"):
                if len(os.path.basename(root)) > 1:
                    continue
                root_int = ord(os.path.basename(root))
                for filename in files:
                    filepath = os.path.join(root, filename)
                    digit_img = cv2.imread(filepath)
                    digit_img = cv2.cvtColor(digit_img, cv2.COLOR_BGR2GRAY)
                    chars_train.append(digit_img)
                    # chars_label.append(1)
                    chars_label.append(root_int)
            chars_train = list(map(deskew, chars_train))
            chars_train = preprocess_hog(chars_train)
            # chars_train = chars_train.reshape(-1, 20, 20).astype(np.float32)
            chars_label = np.array(chars_label)
            print(chars_train.shape)
            self.model.train(chars_train, chars_label)

        if os.path.exists(svmzh_path):
            self.modelchinese.load(svmzh_path)
        else: # 同上
            chars_train = []
            chars_label = []
            for root, dirs, files in os.walk("./lib_Pic/train/charsChinese"):
                if not os.path.basename(root).startswith("zh_"):
                    continue
                pinyin = os.path.basename(root)
                index = provinces.index(pinyin) + PROVINCE_START + 1  # 1是拼音对应的汉字
                for filename in files:
                    filepath = os.path.join(root, filename)
                    digit_img = cv2.imread(filepath)
                    digit_img = cv2.cvtColor(digit_img, cv2.COLOR_BGR2GRAY)
                    chars_train.append(digit_img)
                    # chars_label.append(1)
                    chars_label.append(index)
            chars_train = list(map(deskew, chars_train))
            chars_train = preprocess_hog(chars_train)
            # chars_train = chars_train.reshape(-1, 20, 20).astype(np.float32)
            chars_label = np.array(chars_label)
            print(chars_train.shape)
            self.modelchinese.train(chars_train, chars_label)

    def save_traindata(self): # 保存svm训练数据
        if not os.path.exists(svm_path):
            self.model.save(svm_path)
        if not os.path.exists(svmzh_path):
            self.modelchinese.save(svmzh_path)

    def accurate_place(self, card_img_hsv, limit1, limit2, color):
        row_num, col_num = card_img_hsv.shape[:2]
        xl = col_num
        xr = 0
        yh = 0
        yl = row_num
        # col_num_limit = self.cfg["col_num_limit"]
        row_num_limit = self.cfg["row_num_limit"]
        col_num_limit = col_num * 0.8 if color != "green" else col_num * 0.5  # 绿色有渐变
        for i in range(row_num):
            count = 0
            for j in range(col_num):
                H = card_img_hsv.item(i, j, 0)
                S = card_img_hsv.item(i, j, 1)
                V = card_img_hsv.item(i, j, 2)
                if limit1 < H <= limit2 and 34 < S and 46 < V:
                    count += 1
            if count > col_num_limit:
                if yl > i:
                    yl = i
                if yh < i:
                    yh = i
        for j in range(col_num):
            count = 0
            for i in range(row_num):
                H = card_img_hsv.item(i, j, 0)
                S = card_img_hsv.item(i, j, 1)
                V = card_img_hsv.item(i, j, 2)
                if limit1 < H <= limit2 and 34 < S and 46 < V:
                    count += 1
            if count > row_num - row_num_limit:
                if xl > j:
                    xl = j
                if xr < j:
                    xr = j
        return xl, xr, yh, yl

    def predict(self, car_pic):
        # step1-图像缩放
        if type(car_pic) == type(''):
            img = imreadex(car_pic)
        else:
            img = car_pic
        # cv2.imshow("树莓派车牌识别", img)
        pic_hight, pic_width = img.shape[:2]
        if pic_width > MAX_WIDTH:
            resize_rate = MAX_WIDTH / pic_width
            img = cv2.resize(img, (MAX_WIDTH, int(pic_hight * resize_rate)), interpolation=cv2.INTER_AREA)

        # step2-高斯去噪 & 除掉图像中不会是车牌的区域
        blur = self.cfg["blur"]
        if blur > 0:
            img = cv2.GaussianBlur(img, (blur, blur), 0)  # 图像分辨率调整
        oldimg = img
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)       # 图像转灰度图

        kernel = np.ones((20, 20), np.uint8)
        img_opening = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)  # 图像滤波
        img_opening = cv2.addWeighted(img, 1, img_opening, -1, 0)    # 图像融合

        # step3-找到图像边缘
        ret, img_thresh = cv2.threshold(img_opening, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img_edge = cv2.Canny(img_thresh, 100, 200)     # 边缘检测
        # 使用开运算和闭运算让图像边缘成为一个整体
        kernel = np.ones((self.cfg["morphologyr"], self.cfg["morphologyc"]), np.uint8)
        img_edge1 = cv2.morphologyEx(img_edge, cv2.MORPH_CLOSE, kernel)
        img_edge2 = cv2.morphologyEx(img_edge1, cv2.MORPH_OPEN, kernel)

        # step4-查找图像边缘整体形成的矩形区域，可能有很多，车牌就在其中一个矩形区域中
        contours, hierarchy = cv2.findContours(img_edge2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = [cnt for cnt in contours if cv2.contourArea(cnt) > Min_Area]
        # print(u'检测到可能的车牌区域数目：{0:d}'.format(len(contours)))
        car_contours = []                          # 保存确定的车牌区域
        oldimg1 = copy.copy(oldimg)                # 拷贝一份
        for cnt in contours:                       # 逐一排除不是车牌的矩形区域
            rect = cv2.minAreaRect(cnt)            # 图像区域的最小外接矩形；rect包含中心点坐标，宽高，旋转角度信息
            area_width, area_height = rect[1]
            if area_width < area_height:           # 防止图像中车牌竖放的情况
                area_width, area_height = area_height, area_width
            wh_ratio = area_width / area_height   # 要求矩形区域长宽比在2到5.5之间，2到5.5是车牌的长宽比，其余的矩形排除
            if wh_ratio > 2 and wh_ratio < 5.5:
                car_contours.append(rect)
                box = cv2.boxPoints(rect)          # 获取矩形四个顶点，浮点型
                box = np.int0(box)                 # 取整
                oldimg = cv2.drawContours(oldimg, [box], 0, (0, 0, 255), 2)   # 框选出识别的车牌
            # cv2.imshow("树莓派车牌识别", oldimg)
        # print(u'精确定位后车牌区域数目：{0:d}'.format(len(car_contours)))

        # step5-矩形区域可能是倾斜的矩形，需要进行矫正
        card_imgs = []
        for rect in car_contours:
            if rect[2] > -1 and rect[2] < 1:  # 创造角度，使得左、高、右、低拿到正确的值
                angle = 1
            else:
                angle = rect[2]
            rect = (rect[0], (rect[1][0] + 5, rect[1][1] + 5), angle)   # 扩大范围，避免车牌边缘被排除

            box = cv2.boxPoints(rect)
            heigth_point = right_point = [0, 0]
            left_point = low_point = [pic_width, pic_hight]
            for point in box:
                if left_point[0] > point[0]:
                    left_point = point
                if low_point[1] > point[1]:
                    low_point = point
                if heigth_point[1] < point[1]:
                    heigth_point = point
                if right_point[0] < point[0]:
                    right_point = point

            if left_point[1] <= right_point[1]:  # 正角度
                new_right_point = [right_point[0], heigth_point[1]]
                pts2 = np.float32([left_point, heigth_point, new_right_point])  # 字符只是高度需要改变
                pts1 = np.float32([left_point, heigth_point, right_point])
                M = cv2.getAffineTransform(pts1, pts2)                          # 计算变换矩阵
                dst = cv2.warpAffine(oldimg1, M, (pic_width, pic_hight))         # 进行仿射变换
                point_limit(new_right_point)
                point_limit(heigth_point)
                point_limit(left_point)
                card_img = dst[int(left_point[1]):int(heigth_point[1]), int(left_point[0]):int(new_right_point[0])]
                card_imgs.append(card_img)

            elif left_point[1] > right_point[1]:  # 负角度
                new_left_point = [left_point[0], heigth_point[1]]
                pts2 = np.float32([new_left_point, heigth_point, right_point])  # 字符只是高度需要改变
                pts1 = np.float32([left_point, heigth_point, right_point])
                M = cv2.getAffineTransform(pts1, pts2)
                dst = cv2.warpAffine(oldimg1, M, (pic_width, pic_hight))
                point_limit(right_point)
                point_limit(heigth_point)
                point_limit(new_left_point)
                card_img = dst[int(right_point[1]):int(heigth_point[1]), int(new_left_point[0]):int(right_point[0])]
                card_imgs.append(card_img)

        # step6-1-根据车牌颜色定位，用来排除不是车牌的区域，目前只识别蓝、绿、黄车牌
        colors = []
        for card_index, card_img in enumerate(card_imgs):            # 对提取的每个车牌区域进行识别
            green = yello = blue = black = white = 0
            card_img_hsv = cv2.cvtColor(card_img, cv2.COLOR_BGR2HSV) # 颜色空间转换，由于上一步矫正矩形的原因，有转换失败的可能，
            if card_img_hsv is None:
                continue
            row_num, col_num = card_img_hsv.shape[:2]
            card_img_count = row_num * col_num      
            for i in range(row_num):                # 对该车牌区域的每个像素点进行H色度、S饱和度、V亮度的判断
                for j in range(col_num):
                    H = card_img_hsv.item(i, j, 0)
                    S = card_img_hsv.item(i, j, 1)
                    V = card_img_hsv.item(i, j, 2)
                    if 11 < H <= 34 and S > 34:     # 图片分辨率调整
                        yello += 1
                    elif 35 < H <= 99 and S > 34:   # 图片分辨率调整
                        green += 1
                    elif 99 < H <= 124 and S > 34:  # 图片分辨率调整
                        blue += 1
                    if 0 < H < 180 and 0 < S < 255 and 0 < V < 46:
                        black += 1
                    elif 0 < H < 180 and 0 < S < 43 and 221 < V < 225:
                        white += 1

            color = "no"
            limit1 = limit2 = 0
            if yello * 2 >= card_img_count:  # 某种颜色成分占50%以上
                color = "yello"
                limit1 = 11
                limit2 = 34      # 黄：有的图片有色偏偏绿
            elif green * 2 >= card_img_count:
                color = "green"
                limit1 = 35
                limit2 = 99      # 绿：有的图片有色偏偏绿
            elif blue * 2 >= card_img_count:
                color = "blue"
                limit1 = 100
                limit2 = 124     # 蓝：有的图片有色偏偏紫
            elif black + white >= card_img_count * 0.7:  # TODO
                color = "bw"     # 黑白
            if limit1 == 0:      # 未检测出颜色，直接跳过该车牌区域，不做进一部处理
                continue
            colors.append(color) # 保存该车牌区域的识别颜色结果
            print(u'检测到的车牌(编号{0:d})颜色为{1}'.format(card_index+1,color))
            print(u'|蓝色：{0:.1%}|绿色：{1:.1%}|黄色：{2:.1%}|黑色：{3:.1%}|白色：{4:.1%}|'.format(float(blue)/card_img_count,
                float(green)/card_img_count,float(yello)/card_img_count, float(black)/card_img_count,float(white)/card_img_count))

            # step6-2-以下为根据检测出的车牌颜色再定位，缩小边缘非车牌边界
            xl, xr, yh, yl = self.accurate_place(card_img_hsv, limit1, limit2, color)
            if yl == yh and xl == xr:
                continue
            need_accurate = False
            if yl >= yh:
                yl = 0
                yh = row_num
                need_accurate = True
            if xl >= xr:
                xl = 0
                xr = col_num
                need_accurate = True
            card_imgs[card_index] = card_img[yl:yh, xl:xr] if color != "green" or yl < (yh - yl) // 4 else card_img[yl - (yh - yl) // 4:yh,xl:xr]
            if need_accurate:  # 可能x或y方向未缩小，需要再试一次
                card_img = card_imgs[card_index]
                card_img_hsv = cv2.cvtColor(card_img, cv2.COLOR_BGR2HSV)
                xl, xr, yh, yl = self.accurate_place(card_img_hsv, limit1, limit2, color)
                if yl == yh and xl == xr:
                    continue
                if yl >= yh:
                    yl = 0
                    yh = row_num
                if xl >= xr:
                    xl = 0
                    xr = col_num
            card_imgs[card_index] = card_img[yl:yh, xl:xr] if color != "green" or yl < (yh - yl) // 4 else card_img[yl - (yh - yl) // 4:yh,xl:xr]

        # step7-以上为车牌定位，以下为车牌字符识别
        predict_result = []
        predict_result_group = []
        LRPresult = None
        roi = None
        card_color = None
        for i, color in enumerate(colors):
            if color in ("blue", "yello", "green"):
                card_img = card_imgs[i]
                cv2.imwrite("output.jpg", card_img)
                gray_img = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
                if color == "green" or color == "yello":    # 黄、绿车牌字符比背景暗，与蓝车牌刚好相反，所以黄、绿车牌需要反向
                    gray_img = cv2.bitwise_not(gray_img)
                ret, gray_img = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # step7-1 查找水平直方图波峰，因为处理后文字区域正常都是白色，那么在直方图上就显示为波峰，波峰数目就是字符数目
                x_histogram = np.sum(gray_img, axis=1)
                x_min = np.min(x_histogram)
                x_average = np.sum(x_histogram) / x_histogram.shape[0]
                x_threshold = (x_min + x_average) / 2
                wave_peaks = find_waves(x_threshold, x_histogram)
                if len(wave_peaks) == 0:                          # 正常应该为1，这里为0不正常跳过
                    print(u'查找水平直方图波峰结果异常：{0:d}处(应为1处\n)'.format(len(wave_peaks)))
                    continue
                wave = max(wave_peaks, key=lambda x: x[1] - x[0]) # 认为水平方向，最大的波峰为车牌区域
                gray_img = gray_img[wave[0]:wave[1]]

                # step7-2 查找垂直直方图波峰
                row_num, col_num = gray_img.shape[:2]
                gray_img = gray_img[1:row_num - 1]                # 去掉车牌上下边缘1个像素，避免白边影响阈值判断
                y_histogram = np.sum(gray_img, axis=0)
                y_min = np.min(y_histogram)
                y_average = np.sum(y_histogram) / y_histogram.shape[0]
                y_threshold = (y_min + y_average) / 5             # U和0要求阈值偏小，否则U和0会被分成两半
                wave_peaks = find_waves(y_threshold, y_histogram)
                if len(wave_peaks) <= 6:                          # 车牌字符数应为7  赣A 17544
                    print(u'查找垂直直方图波峰结果异常：{0:d}处(应为7处)\n'.format(len(wave_peaks)))
                    continue
                wave = max(wave_peaks, key=lambda x: x[1] - x[0])
                max_wave_dis = wave[1] - wave[0]
                # 判断是否是左侧车牌边缘
                if wave_peaks[0][1] - wave_peaks[0][0] < max_wave_dis / 3 and wave_peaks[0][0] == 0:
                    wave_peaks.pop(0)

                # step7-3 组合分离汉字
                cur_dis = 0
                for i, wave in enumerate(wave_peaks):
                    if wave[1] - wave[0] + cur_dis > max_wave_dis * 0.6:
                        break
                    else:
                        cur_dis += wave[1] - wave[0]
                if i > 0:
                    wave = (wave_peaks[0][0], wave_peaks[i][1])
                    wave_peaks = wave_peaks[i + 1:]
                    wave_peaks.insert(0, wave)

                # 去除车牌上的分隔点
                point = wave_peaks[2]
                if point[1] - point[0] < max_wave_dis / 3:
                    point_img = gray_img[:, point[0]:point[1]]
                    if np.mean(point_img) < 255 / 5:
                        wave_peaks.pop(2)
                if len(wave_peaks) <= 6 or len(wave_peaks) >= 9:
                    print(u'查找垂直直方图波峰结果异常：{0:d}处(应为7处)\n'.format(len(wave_peaks)))
                    continue
                part_cards = seperate_card(gray_img, wave_peaks)  # 返回分割后的字符区域图像

                for k in range(25):      # 取25次中的模态
                    for i, part_card in enumerate(part_cards):        # 字符识别
                        if np.mean(part_card) < 255 / 5:              # 可能是固定车牌的铆钉，都抛弃
                            print(u'识别出点状图像')
                            continue
                        part_card_old = part_card
                        w = abs(part_card.shape[1] - SZ) // 2
                        part_card = cv2.copyMakeBorder(part_card, 0, 0, w, w, cv2.BORDER_CONSTANT, value=[0, 0, 0])
                        part_card = cv2.resize(part_card, (SZ, SZ), interpolation=cv2.INTER_AREA)
                        # part_card = deskew(part_card)
                        part_card = preprocess_hog([part_card])
                        if i == 0:  # 第一个字符显然是中文
                            resp = self.modelchinese.predict(part_card)
                            charactor = provinces[int(resp[0]) - PROVINCE_START]
                        else:       # 字母与数字
                            resp = self.model.predict(part_card)
                            charactor = chr(resp[0])
                        # 判断最后一个数是否是车牌边缘，假设车牌边缘被认为是1
                        if charactor == "1" and i == len(part_cards) - 1:
                            if part_card_old.shape[0] / part_card_old.shape[1] >= 7:  # 1太细，认为是边缘
                                continue
                        predict_result.append(charactor)

                    LRPresult = ''.join(predict_result)
                    predict_result_group.append(LRPresult)

                LRPresult = findmaxstr(predict_result_group)               # 取出出现最多的识别结果
                roi = card_img
                card_color = color
                break

        return LRPresult, roi, card_color  # 识别到的字符、定位的车牌图像、车牌颜色

##================================== FILE END ===================================
