import sys
import time
import numpy as np
from . import config
import cv2 as cv
from .collect_face_data import face_detect
import pymysql
sys.path.append('/home/412_pi/FlaskOnPi/config')
import dbConfig

timeout_second = 60

class face_recognition(face_detect):
    def __init__(self, cam):
        super(face_recognition, self).__init__()
        self.camera = cam
        self.available_max_face_num = 50        # 最大的人脸检测数量(不一定能达到)
        self.collect_face_data = False          # 人脸识别过程不采集数据，固定为False

        self.all_features = []                  # 存储库中所有特征向量
        self.check_features_from_cam = []       # 存储五次检测过程，每次得到的特征向量

        self.person_name = []                   # 存储人名
        self.all_name = []                      # 存储预测到的所有人名

        self.all_face_location = None           # 存储一帧中所有人脸的坐标
        self.middle_point = None                # 存储一张人脸的中心点坐标
        self.last_frame_middle_point = []       # 存储上一帧所有人脸的中心点坐标

        self.all_e_distance = []                # 存储当前人脸与库中所有人脸特征的欧氏距离
        self.num_of_person_in_lib = 0
        
        self.last_now_middlePoint_eDistance = [99999 for x in range(self.available_max_face_num)]   # 存储这帧与上一帧每张人脸中心点的欧氏距离

        for i in range(self.available_max_face_num):
            self.all_e_distance.append([])
            self.person_name.append([])
            self.check_features_from_cam.append([])
            self.last_frame_middle_point.append([])   

    def calculate_EuclideanDistance(self, feature1, feature2):          # 计算欧氏距离
        np_feature1 = np.array(feature1)
        np_feature2 = np.array(feature2)

        EuclideanDistance = np.sqrt(np.sum(np.square(np_feature1 - np_feature2)))

        return EuclideanDistance

    def meadian_filter(self, the_list, num_of_data):
        np_list = np.array(the_list)
        feature_max = np.max(np_list, axis=0)
        feature_min = np.min(np_list, axis=0)
        res = (np.sum(np_list, axis=0) - feature_max - feature_min) / (num_of_data-2)

        res.tolist()
        return res

    def middle_filter(self, the_list):
        np_list = np.array(the_list)
        return np.median(np_list, axis=0)

    def fetch_data_from_database(self):
        try:
            # 连接到数据库
            connection = pymysql.connect(
                host=dbConfig.host,
                database=dbConfig.database,
                user=dbConfig.user,
                password=dbConfig.password
            )

            cursor = connection.cursor()
            
            # 查询库中人数
            sql = "SELECT COUNT(*) FROM FaceInformation"
            cursor.execute(sql)
            self.num_of_person_in_lib = cursor.fetchone()[0]
            
            # 查询 phone_number 和 face_data 列
            query = "SELECT phone_number, face_data FROM FaceInformation"
            cursor.execute(query)

            # 获取查询结果
            results = cursor.fetchall()

            # 遍历结果
            for result in results:
                name = result[0]
                face_data_binary = result[1]

                # 解析二进制数据为浮点数列表
                face_data_floats = np.frombuffer(face_data_binary, dtype=np.float64)
                features = face_data_floats.tolist()

                # 处理结果
                # print("Phone Number:", name)
                # print("Face Data Array:", features)
                self.all_name.append(name)
                self.all_features.append(features)
               
            print("库中存在的人名有：{}".format(self.all_name))
            # print(self.all_features)

        except Exception as e:
            print(e)
        finally:
            # 关闭数据库连接
            if connection is not None:
                connection.close()
                print("数据库连接已关闭")
    
    def init_process(self):
        self.fetch_data_from_database()

    def track_link(self):           # 这个函数是为了让后续帧的序号与初始帧的序号对应
        for index in range(self.face_num):
            self.last_now_middlePoint_eDistance[index] = self.calculate_EuclideanDistance(self.middle_point,
                                                                              self.last_frame_middle_point[index])
        this_face_index = self.last_now_middlePoint_eDistance.index(min(self.last_now_middlePoint_eDistance))
        self.last_frame_middle_point[this_face_index] = self.middle_point

        return this_face_index

    def recognition_from_cam(self):
        self.init_process()
        start_time = time.time()
        while self.camera.isOpened() and not self.quit_flag:
            current_time = time.time()
            if current_time - start_time > timeout_second:
                print("Timeout!")
                raise TimeoutError
            
            val, self.image = self.camera.read()
            if val == False: continue

            res = self.face_detecting()         # 0.038s

            if res is not None:
                face, self.all_face_location = res

                for i in range(self.face_num):
                    [left, right, top, bottom] = self.all_face_location[i]
                    self.middle_point = [(left + right) /2, (top + bottom) / 2]

                    self.face_img = self.image[top:bottom, left:right]

                    cv.rectangle(self.image, (left, top), (right, bottom), (0, 0, 255))

                    shape = config.predictor(self.image, face[i])       # 0.002s

                    if self.face_num_change_flag == True or self.check_times <= 5:
                        if self.face_num_change_flag == True:       # 人脸数量有变化，重新进行五次检测
                            self.check_times = 0
                            self.last_now_middlePoint_eDistance = [99999 for _ in range(self.available_max_face_num)]
                            for z in range(self.available_max_face_num):
                                self.check_features_from_cam[z] = []

                        if self.check_times < 5:
                            the_features_from_cam = list(config.recognition_model.compute_face_descriptor(self.image, shape))   # 耗时主要在这步 0.32s
                            if self.check_times == 0:           # 初始帧
                                self.check_features_from_cam[i].append(the_features_from_cam)
                                self.last_frame_middle_point[i] = self.middle_point
                            else:
                                this_face_index = self.track_link()         # 后续帧需要与初始帧的人脸序号对应
                                self.check_features_from_cam[this_face_index].append(the_features_from_cam)

                        elif self.check_times == 5:
                            features_after_filter = self.middle_filter(self.check_features_from_cam[i])
                            self.check_features_from_cam[i] = []
                            for person in range(self.num_of_person_in_lib):
                                e_distance = self.calculate_EuclideanDistance(self.all_features[person],
                                                                              features_after_filter)  # 几乎不耗时

                                self.all_e_distance[i].append(e_distance)

                            if min(self.all_e_distance[i]) < config.recognition_threshold:
                                self.person_name[i] = self.all_name[self.all_e_distance[i].index(min(self.all_e_distance[i]))]
                            else:
                                self.person_name[i] = "Unknown"

                            print("预测结果为:{}, 与库中各人脸的欧氏距离为:{}".format(self.person_name[i], self.all_e_distance[i]))
                            return self.person_name[i]

                    else:
                        this_face_index = self.track_link()
                self.check_times += 1

                for j in range(self.available_max_face_num):
                    self.all_e_distance[j] = []


def main():
    try:
        cam = cv.VideoCapture(0)
        process = face_recognition(cam)
        # process.fetch_data_from_database()
        result = process.recognition_from_cam()
        return result
        
    except TimeoutError:
        return 'Timeout'
    except Exception as e:
        print(e)
    finally:
        cam.release()
        # print(result)
        
    
if __name__ == '__main__':
    main()