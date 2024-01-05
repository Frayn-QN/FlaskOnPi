import cv2 as cv
import os
from . import config

class face_detect():
    def __init__(self):
        self.start_time = 0                     # 用于计算帧率
        self.fps = 0                            # 帧率

        self.image = None
        self.face_img = None

        self.face_num = 0                       # 这一帧的人脸个数
        self.last_face_num = 0                  # 上一帧的人脸个数

        self.face_num_change_flag = False       # 当前帧人脸数量变化的标志位，用于后续人脸识别提高帧率
        self.quit_flag = False                  # 退出程序标志位
        self.buildNewFolder = False             # 按下"n"新建文件夹标志位
        self.save_flag = False                  # 按下“s”保存人脸数据标志位
        self.face_flag = False                  # 人脸检测标志位

        self.img_num = 0                        # 人脸数据文件夹内的图像个数

        self.collect_face_data = True           # 是否进行人脸数据的采集，只有为真时才会进行采集

    def save_face(self):
        if self.collect_face_data == True:
            self.save_flag = True
            if self.buildNewFolder == False:
                if os.path.exists(config.faceData_path + 'person_0') == False:
                    os.makedirs(config.faceData_path + 'person_0')
                print("新文件夹建立成功!!")
                self.buildNewFolder = True

            if self.face_img.size > 0 and self.img_num < 10:
                # print("1")
                cv.imwrite(
                    config.faceData_path + 'person_0/{}.png'.format(self.img_num),
                    self.face_img)
                self.img_num += 1
            elif self.img_num == 10:
                print("扫描完成")
                self.quit_flag = True


    def face_detecting(self):
        face_location = []
        all_face_location = []

        faces = config.detector(self.image, 0)
        self.face_num = len(faces)

        if self.face_num != self.last_face_num:
            self.face_num_change_flag = True
            print("脸数改变，由{}张变为{}张".format(self.last_face_num, self.face_num))
            self.check_times = 0
            self.last_face_num = self.face_num
        else:
            self.face_num_change_flag = False

        if len(faces) != 0:
            self.face_flag = True

            for i, face in enumerate(faces):
                face_location.append(face)
                w, h = (face.right() - face.left()), (face.bottom() - face.top())
                left, right, top, bottom = face.left() - w//4, face.right() + w//4, face.top() - h//2, face.bottom() + h//4

                all_face_location.append([left, right, top, bottom])

            return face_location, all_face_location
        else:
            self.face_flag = False

        return None

    def fromimg(self, img):
        patience = 0
        while img is not None and not self.quit_flag:
            self.image = img
            if self.image is None: continue

            res = self.face_detecting()
            if res is not None:
                # print("1")
                _, all_face_location = res

                for i in range(self.face_num):
                    [left, right, top, bottom] = all_face_location[i]
                    self.face_img = self.image[top:bottom, left:right]
                    cv.rectangle(self.image, (left, top), (right, bottom), (0, 0, 255))
                    self.save_face()
            else:
                patience += 1
                if patience > 10:
                    message = '识别失败！'
                    return message

        return None


def main():
    
    for filename in os.listdir(config.originFile_path):
        if filename.endswith(".jpg"):
            print("采集程序启动！")
            # 添加完整路径
            file_path = os.path.join(config.originFile_path, filename)
            # 读取图片
            image = cv.imread(file_path)
            
            # 图像处理
            message = face_detect().fromimg(image)

            # 获取不包含后缀的文件名，即为该人员的手机号
            file_name_without_extension = os.path.splitext(filename)[0]

            # 处理完后删除文件
            os.remove(file_path)

            if message is not None:
                print(filename + message)
                return False

            # print(f"Processed and deleted: {file_name_without_extension}")
            with open(config.faceName_path, 'w') as file:
                file.write(file_name_without_extension + '\n')
                
            return True



if __name__ == '__main__':
    main()