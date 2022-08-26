#!/usr/bin/env python3

from PIL import Image #Raspian: sudo apt install python3-pil
from PIL import ImageDraw #Raspian: sudo apt install python3-pil

import os
import glob
import time

import requests
from io import BytesIO

import json
import sys
import logging

_LOGGER = logging.getLogger(__name__)


class Snapshot():

    user_name=[str]
    user_pwd=[str]
    url=[str]

    topic_suffix=[str]
    filename=[str]
    path=str
    keep_count=int

    def __init__(self,configfile):
        self.configfile=configfile
        try:
            with open(self.configfile) as json_pcfg_file:
                pcfg = json.load(json_pcfg_file)
                snapshotConfigData = pcfg['snapshotConfigData']
                # configure snapshot source
                self.user_name = snapshotConfigData['camConfigData']['user_name']
                self.user_pwd =  snapshotConfigData['camConfigData']['user_pwd']
                self.url =  snapshotConfigData['camConfigData']['url']
                # configure snapshot target
                self.topic_suffix =  snapshotConfigData['snapshotTopicSuffix']['topic_suffix']
                self.filename =  snapshotConfigData['snapshotTopicSuffix']['filename']
                self.path =  snapshotConfigData['snapshotTopicSuffix']['path']
                self.keep_count =  int(snapshotConfigData['snapshotTopicSuffix']['keep_count'])

                #_LOGGER.debug(f"Username ({self.user_name}), Password({self.user_pwd}), User (url{self.url})")

        except Exception as e:
            _LOGGER.exception(str(e))


    def get_image(self,user_name, user_pwd, url):
        try:          
            response = requests.get(url, auth=requests.auth.HTTPDigestAuth(user_name, user_pwd),timeout=5)
            img = Image.open(BytesIO(response.content))

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(f"Failed to get snapshot from camera {url}, error: {ex}, Line: {exc_tb.tb_lineno}")
            img=self.creat_error_image(url,user_name)
        return img

    def creat_error_image(self,url,user_name):
        img=Image.new('RGB', (600, 200))
        ImageDraw.Draw(img).text((5, 60),"Failed to get snapshot from camera. Check URL, user & password",(255, 255, 255))   
        ImageDraw.Draw(img).text((5, 70),f"URL: {url}",(255, 255, 255))
        ImageDraw.Draw(img).text((5, 80),f"user: {user_name}",(255, 255, 255))
        return img

    def get_merged_image(self,img):
        try:
            img_count=len(img)
            new_image_size = img[0].size  
            new_image = Image.new('RGB',(new_image_size[0], img_count*new_image_size[1]), (250,250,250))

            for x in range(len(img)):
                if x > 0:  
                    img[x] = img[x].resize((new_image_size[0], new_image_size[1]))                
                new_image.paste(img[x],(0,(x)*new_image_size[1]))

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(f"Failed to merge images, error: {ex}, Line: {exc_tb.tb_lineno}")
        
        return new_image


    def backup_old_and_save_new_image(self,img,snapshot_name,keep_count):
        try:
            path=os.getenv('LBHOMEDIR')+self.path

            snapshots=glob.glob1(path,snapshot_name+"*")

            num_snapshots=len(snapshots)

            img_file=path+snapshot_name+".jpg"
            if os.path.isfile(img_file):
                timestamp=os.path.getmtime(img_file)
                convert_time = time.localtime(timestamp)
                timestr = time.strftime('%Y%m%d.%H%M%S', convert_time)
                os.rename(img_file,f"{path+snapshot_name}_{timestr}.jpg")            

            img.save(img_file,"JPEG")

            if num_snapshots >= keep_count:
                for n in range(1,num_snapshots-keep_count+2):
                    os.remove(path+sorted(snapshots)[n])


        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(f"Failed to back up old snapshot and save new snapshot, error: {ex}, Line: {exc_tb.tb_lineno}")



    def merge_snapshot(self,snapshot_name):
        try:
            img_count=len(self.user_name)
            img=[]
            for x in range(img_count):
                img.append(self.get_image(user_name=self.user_name[x], user_pwd=self.user_pwd[x], url=self.url[x]))     

            if img_count>1:
                new_image=self.get_merged_image(img)
                self.backup_old_and_save_new_image(img=new_image,snapshot_name=snapshot_name,keep_count=self.keep_count)
            else:
                new_image=img[0]


        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(f"Failed to save snapshot, error: {ex}, Line: {exc_tb.tb_lineno}")


    def get_snapshot(self,current_topic_suffix):
        try:
            if current_topic_suffix in self.topic_suffix:
                item_no=self.topic_suffix.index(current_topic_suffix)
                snapshot_name=self.filename[item_no]
                self.merge_snapshot(snapshot_name=snapshot_name)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(f"Failed to get snapshot, error: {ex}, Line: {exc_tb.tb_lineno}")
    
    def test_snapshots(self):
        response="Test failed: Check the log file"
        try:
            for current_topic_suffix in self.topic_suffix:
                self.get_snapshot(current_topic_suffix=current_topic_suffix)
            response="Test succeed: Check the snapshots in the snapshot folder"

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(f"Failed to test snapshots, error: {ex}, Line: {exc_tb.tb_lineno}")

        return response
