import sys
import cv2 as cv
import os
import numpy as np
from . import config
from tqdm import tqdm
import shutil
import pymysql
sys.path.append('/home/412_pi/FlaskOnPi/config')
import dbConfig
        
def write2db(name, data):
    binary_data = data.tobytes()
    
    try:
        db = pymysql.connect(
            host=dbConfig.host,
            database=dbConfig.database,
            user=dbConfig.user,
            password=dbConfig.password
        )
        cursor = db.cursor()
        
        sql = """INSERT INTO FaceInformation (phone_number, face_data) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE face_data = VALUES(face_data);"""
        cursor.execute(sql, (name, binary_data))
        
        db.commit()

    except Exception as e:
        print(e)
        db.rollback()
        
    finally:
        if db is not None:
            # db.rollback()
            db.close
    

def get_128_features(person):                    # person代表"person_x"目录中的x
    num = 0
    features = []
    imgs_folder = 'person_0'
    points_faceImage_path = config.points_faceData_path + imgs_folder

    imgs_path = config.faceData_path + imgs_folder + '/'
    list_imgs = os.listdir(imgs_path)
    imgs_num = len(list_imgs)

    if os.path.exists(config.points_faceData_path + imgs_folder):
        shutil.rmtree(points_faceImage_path)
    os.makedirs(points_faceImage_path)
    print("人脸点图文件夹建立成功!!")

    with tqdm(total=imgs_num) as pbar:
        pbar.set_description(str(imgs_folder))
        for j in range(imgs_num):
            image = cv.imread(os.path.join(imgs_path, list_imgs[j]))

            faces = config.detector(image, 1)           # 经查阅资料，这里的1代表采样次数
            if len(faces) != 0:
                for z, face in enumerate(faces):
                    shape = config.predictor(image, face)       # 获取68点的坐标

                    w, h = (face.right() - face.left()), (face.bottom() - face.top())
                    left, right, top, bottom = face.left() - w // 4, face.right() + w // 4, face.top() - h // 2, face.bottom() + h // 4
                    im = image

                    cv.rectangle(im, (left, top), (right, bottom), (0, 0, 255))
                    cv.imwrite(points_faceImage_path + '/{}.png'.format(j), im)

                    if config.get_points_faceData_flag == True:
                        for p in range(0, 68):
                            cv.circle(image, (shape.part(p).x, shape.part(p).y), 2, (0,0,255))
                        cv.imwrite(points_faceImage_path + '/{}.png'.format(j), image)

                    the_features = list(config.recognition_model.compute_face_descriptor(image, shape)) # 获取128维特征向量
                    features.append(the_features)
                    #print("第{}张图片，第{}张脸,特征向量为:{}".format(j+1, z+1, the_features))
                    num += 1
            pbar.update(1)

    np_f = np.array(features)
    #res = np.mean(np_f, axis=0)
    res = np.median(np_f, axis=0)
    
    shutil.rmtree(config.faceData_path + imgs_folder)
    shutil.rmtree(points_faceImage_path)

    return res

def main():  
    with open(config.faceName_path, "r") as file:
        name = file.readline()
    clean_name = name.rstrip()
    
    try:
        res = get_128_features(0)
        write2db(clean_name, res)
        print("录入成功")
        # print("人脸特征向量为：{}".format(res))
    except Exception as e:
        print(e)
        return False
    
    with open(config.faceName_path, "w") as file:
        file.write('')
    return True

if __name__ == '__main__':
    main()
