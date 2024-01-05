import dlib

# 各路径
data_father_path = '/home/412_pi/FlaskOnPi/data/face/'
data_dlib_path = '/home/412_pi/FlaskOnPi/myFunction/dlib_faceRecognition/data_dlib/'
shape_predictor_path = data_dlib_path + 'shape_predictor_68_face_landmarks.dat'
recognition_model_path = data_dlib_path + 'dlib_face_recognition_resnet_model_v1.dat'
csv_base_path = data_father_path + 'features.csv'                   # 存储人脸特征的csv路径
faceData_path = data_father_path + 'faceData/'                      # 存放各人脸图像的文件夹
points_faceData_path = data_father_path + 'faceData_points/'        # 存放人脸点图的文件夹
faceName_path = data_father_path + 'faceName.txt'                   # 存放人脸名字的txt
originFile_path = data_father_path + 'originFile'


# 各标志位
get_points_faceData_flag = True                                                     # 是否获取人脸点图

recognition_threshold = 0.43                                                        # 人脸识别阈值，过小会难以识别到

detector = dlib.get_frontal_face_detector()                                         # 人脸检测器
predictor = dlib.shape_predictor(shape_predictor_path)                              # 人脸68点提取器
recognition_model = dlib.face_recognition_model_v1(recognition_model_path)          # 128特征向量提取器
