import cv2
import numpy as np
from PIL import Image

image = Image.open("circle_alignment_reference_2.jpg")
known_min = 1
known_max = 2

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
gray = cv2.GaussianBlur(gray, (9, 9), 2)    # filter noise of image background

circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
                           param1=50, param2=30, minRadius=known_min, maxRadius=known_max)  # radius units in pixels

if circles is not None:
    circles = np.round(circles[0, :]).astype("int")
    circles = sorted(circles, key=lambda c: c[0])  # sort by x

    left, center, right = circles[:3]
    distance = np.linalg.norm(left[:2] - right[:2])
    print(f"Centers: Left={left[:2]}, Center={center[:2]}, Right={right[:2]}")
    print(f"Distance between left and right: {distance}")