"""
Face detection
"""
import cv2
import os
from time import sleep
import numpy as np
import argparse
from wide_resnet import WideResNet
from keras.utils import get_file
import matplotlib.pyplot as plt
import pylab
from utils import load_image
import dlib
import copy
from utils import display_cv2_image
from src.utils.inference import apply_offsets

from face_reco_base import FaceRecognizer
from src.utils.preprocessor import preprocess_input
from src.utils.datasets import get_labels
from keras.models import load_model
#import src.emotionpred as emotion


import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

emotion_model_path = 'C:/Projects\Minor Project/Face-Recognition-Model-with-Gender-Age-and-Emotions-Estimations-master/trained_models/emotion_models/fer2013_mini_XCEPTION.102-0.66.hdf5'
emotion_labels = get_labels('fer2013')
emotion_classifier = load_model(emotion_model_path, compile=False)
emotion_target_size = emotion_classifier.input_shape[1:3]
emotion_offsets = (20, 40)

# Flag to recognize faces 
# This requires face_reco_base.py to be run in console first
RECOGNIZE_FACES = True

# Transparency level for text overlay
OVERLAY_ALPHA = 0.5

# Display image via OpenCV or matplotlib
DISPLAY_CV_IMAGE=True

# Test FaceImage class
TEST_FACE_IMAGE=False

class FaceImage(object):
    """
    Singleton class for face recognition task
    """
    CASE_PATH = "./models/haarcascade_frontalface_alt.xml"
    WRN_WEIGHTS_PATH = "https://github.com/Tony607/Keras_age_gender/releases/download/V1.0/weights.18-4.06.hdf5"


    def __new__(cls, weight_file=None, depth=16, width=8, face_size=64):
        if not hasattr(cls, 'instance'):
            cls.instance = super(FaceImage, cls).__new__(cls)
        return cls.instance

    def __init__(self, depth=16, width=8, face_size=64):
        self.face_size = face_size
        print("Loading WideResNet model...")
        self.model = WideResNet(face_size, depth=depth, k=width)()
        model_dir = os.path.join(os.getcwd(), "models").replace("//", "\\")
        fpath = get_file('weights.18-4.06.hdf5',
                         self.WRN_WEIGHTS_PATH,
                         cache_subdir=model_dir)
        self.model.load_weights(fpath)
        print("Loaded WideResNet model")
        
        # Load emotion models
       # print("Loading emotion model...")
        #self.emotion_model = emotion.load_model_dir("models")
        #print("Loaded emotion model")
        
        
        if RECOGNIZE_FACES:
            print("Loading face recognizer...")
            self.face_recognizer = FaceRecognizer()
            print("Loaded face recognizer")
            
          
    @classmethod
    def draw_label_top(cls, image, point, label, font=cv2.FONT_HERSHEY_SIMPLEX,
                   font_scale=1, thickness=2, alpha=OVERLAY_ALPHA):
        size = cv2.getTextSize(label, font, font_scale, thickness)[0]
        x, y = point
        overlay = image.copy()
        cv2.rectangle(overlay, (x, y - size[1]), (x + size[0], y), (255, 0, 0), cv2.FILLED)
        cv2.putText(overlay, label, point, font, font_scale, (255, 255, 255), thickness)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    @classmethod
    def draw_label_bottom(cls, image, point, label, font=cv2.FONT_HERSHEY_SIMPLEX,
                   font_scale=0.5, thickness=1, row_index=0, alpha=OVERLAY_ALPHA):
        size = cv2.getTextSize(label, font, font_scale, thickness)[0]
        point = (point[0], point[1] + (row_index * size[1]))
        x, y = point
        overlay = image.copy()
        cv2.rectangle(overlay, (x, y), (x + size[0], y + size[1]), (255, 0, 0), cv2.FILLED)
        point = x, y+size[1]
        cv2.putText(overlay, label, point, font, font_scale, (255, 255, 255), thickness)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        
    def get_regular_face(self, img, bb):
        return img[bb.top():bb.bottom()+1, bb.left():bb.right()+1, :]

    def get_expanded_face(self, img, bb):
        img_h, img_w, _ = np.shape(img)
        x1, y1, x2, y2, w, h = bb.left(), bb.top(), bb.right() + 1, bb.bottom() + 1, bb.width(), bb.height()
        xw1 = max(int(x1 - 0.4 * w), 0)
        yw1 = max(int(y1 - 0.4 * h), 0)
        xw2 = min(int(x2 + 0.4 * w), img_w - 1)
        yw2 = min(int(y2 + 0.4 * h), img_h - 1)
        return cv2.resize(img[yw1:yw2 + 1, xw1:xw2 + 1, :], (self.face_size, self.face_size))

    def detect_face(self, img):
        # workaround for CV2 bug
        img = copy.deepcopy(img)
        
        # for face detection
        detector = dlib.get_frontal_face_detector()
            
        input_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_h, img_w, _ = np.shape(input_img)


        # detect faces using dlib detector
        if RECOGNIZE_FACES == True:
            face_bbs, identities = self.face_recognizer.identify_image_faces(img)
        else:
            face_bbs = detector(input_img, 1)
        expanded_face_imgs = np.empty((len(face_bbs), self.face_size, self.face_size, 3))
        emotion2_results = []
  
        # Get face images      
        for i, bb in enumerate(face_bbs):
            x1, y1, x2, y2, w, h = bb.left(), bb.top(), bb.right() + 1, bb.bottom() + 1, bb.width(), bb.height()
            expanded_face_imgs[i, :, :, :] = self.get_expanded_face(img, bb)
            reg_face = self.get_regular_face(img, bb)
            gray_face = gray_image[y1:y2, x1:x2]
            
            try:
                gray_face = cv2.resize(gray_face, (emotion_target_size))
            except:
               continue
            #reg_face = copy.deepcopy(reg_face)
            gray_face = preprocess_input(gray_face, True)
            gray_face = np.expand_dims(gray_face, 0)
            gray_face = np.expand_dims(gray_face, -1)
            emotion_prediction = emotion_classifier.predict(gray_face)
            emotion_probability = np.max(emotion_prediction)
            emotion_label_arg = np.argmax(emotion_prediction)
            emotion_text = emotion_labels[emotion_label_arg]
            emotion2_results.append(emotion_text)
          #  emotion2_results.append(emotion.emotionof(self.emotion_model, reg_face)[0])

        
        if len(expanded_face_imgs) > 0:
            # predict ages and genders of the detected faces
            results = self.model.predict(expanded_face_imgs)
            predicted_genders = results[0]
            ages = np.arange(0, 101).reshape(101, 1)
            predicted_ages = results[1].dot(ages).flatten()
            
        # draw results
        for i, bb in enumerate(face_bbs):
            
            if RECOGNIZE_FACES == True:
                # Display name

                label12 = "{}".format(identities[i])
                label1="{}, {}".format(int(predicted_ages[i]),
                                                 "F" if predicted_genders[i][0] > 0.5 else "M")

                self.draw_label_bottom(img, (bb.left(), bb.bottom()), label1,row_index=2)
                self.draw_label_bottom(img, (bb.left(), bb.bottom() + 1), label12, row_index=0)
                ## Display emotion
                if identities[i] == "Unknown" or "customer" in identities[i]:
                    label2 = "{}".format(emotion2_results[i])
                else:
                    try:
                        label2 = "{}".format(emotion2_results[i])
                    except:
                        label2 = "{}".format('normal')
                self.draw_label_bottom(img, (bb.left(), bb.bottom()+1), label2, row_index=1)
            else:
                ## Display age, gender and emotion
                label2 = "{}".format(emotion2_results[i])
                self.draw_label_bottom(img, (bb.left(), bb.bottom()), label2, row_index=0)

        # draw face rectangles
        for i, bb in enumerate(face_bbs):
            x1, y1, x2, y2, w, h = bb.left(), bb.top(), bb.right() + 1, bb.bottom() + 1, bb.width(), bb.height()             
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 2)

        return img
    def detect_face_info(self, file_path):
        
        img = cv2.imread(file_path)
        print(img)
        # workaround for CV2 bug
        img = copy.deepcopy(img)
        
        # for face detection
        detector = dlib.get_frontal_face_detector()
            
        input_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_h, img_w, _ = np.shape(input_img)


        # detect faces using dlib detector
        if RECOGNIZE_FACES == True:
            face_bbs, identities = self.face_recognizer.identify_image_faces(img)
        else:
            face_bbs = detector(input_img, 1)
        expanded_face_imgs = np.empty((len(face_bbs), self.face_size, self.face_size, 3))
        emotion2_results = []
  
        # Get face images      
        for i, bb in enumerate(face_bbs):
            x1, y1, x2, y2, w, h = bb.left(), bb.top(), bb.right() + 1, bb.bottom() + 1, bb.width(), bb.height()
            expanded_face_imgs[i, :, :, :] = self.get_expanded_face(img, bb)
            reg_face = self.get_regular_face(img, bb)
            gray_face = gray_image[y1:y2, x1:x2]
            
            try:
                gray_face = cv2.resize(gray_face, (emotion_target_size))
            except:
               continue
            #reg_face = copy.deepcopy(reg_face)
            gray_face = preprocess_input(gray_face, True)
            gray_face = np.expand_dims(gray_face, 0)
            gray_face = np.expand_dims(gray_face, -1)
            emotion_prediction = emotion_classifier.predict(gray_face)
            emotion_probability = np.max(emotion_prediction)
            emotion_label_arg = np.argmax(emotion_prediction)
            emotion_text = emotion_labels[emotion_label_arg]
            emotion2_results.append(emotion_text)
            
          #  emotion2_results.append(emotion.emotionof(self.emotion_model, reg_face)[0])

        
        if len(expanded_face_imgs) > 0:
            # predict ages and genders of the detected faces
            results = self.model.predict(expanded_face_imgs)
            predicted_genders = results[0]
            ages = np.arange(0, 101).reshape(101, 1)
            predicted_ages = results[1].dot(ages).flatten()
            
        all_faces_info=[]    
        # draw results
        for i, bb in enumerate(face_bbs):
                 face_info = {'Name':identities[i], 'Age':int(predicted_ages[i]),
                              'Gender':"F" if predicted_genders[i][0] > 0.5 else "M",
                              'Imotion':emotion2_results[i]}
                 all_faces_info.append(face_info)
           
  
        return all_faces_info    


def display_labeled_image(face, file_path):
    img = load_image(file_path)
    image = face.detect_face(img)
    if DISPLAY_CV_IMAGE == True:
        display_cv2_image(image, is_rgb=True)
    else:
        plt.figure()
        plt.imshow(image)

def display_labeled_images(face, dir_path):
    files = os.listdir(dir_path)
    for i, file in enumerate(files):
        print("Displaying image {}".format(i+1))
        file_path = os.path.join(dir_path, file)
        display_labeled_image(face, file_path)

if TEST_FACE_IMAGE:
    face = FaceImage()
    display_labeled_image(face, "C:\Projects\Minor Project\Face-Recognition-Model-with-Gender-Age-and-Emotions-Estimations-master\sample/Input/Virat.jpg")
    
