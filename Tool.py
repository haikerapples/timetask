#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
from openpyxl import Workbook
from openpyxl import load_workbook
import hashlib
import base64

class ExcelTool(object):
    __file_name = "timeTask.xlsx"
    __sheet_name = "定时任务"
    __dir_name = "taskFile"
    
    # 新建工作簿
    def create_excel(self, file_name: str = __file_name, sheet_name=__sheet_name):
        # 文件路径
        workbook_file_path = self.get_file_path(file_name)

        # 创建Excel
        if not os.path.exists(workbook_file_path):
            wb = Workbook()
            wb.create_sheet(sheet_name, 0)
            wb.save(workbook_file_path)
            print("定时Excel创建成功，文件路径为：{}".format(workbook_file_path))
        else:
            print("timeTask文件已存在, 无需创建")
                

    # 读取内容,返回元组列表
    def readExcel(self, file_name=__file_name, sheet_name=__sheet_name):
        # 文件路径
        workbook_file_path = self.get_file_path(file_name)
        
        # 文件存在
        if os.path.exists(workbook_file_path):
            wb = load_workbook(workbook_file_path)
            ws = wb[sheet_name]
            data = list(ws.values)
            #print(data)
            return data
        else:
            print("timeTask文件不存在, 读取数据为空")
            return []


    # 写入列表，返回元组列表
    def addItemToExcel(self, item, file_name=__file_name, sheet_name=__sheet_name):
        # 文件路径
        workbook_file_path = self.get_file_path(file_name)
        
        #计算内容ID
        temp_content='_'.join(item)
        short_id = self.get_short_id(temp_content)
        print(f'消息体：{temp_content}， 唯一ID：{short_id}')
        newItem = (short_id,) + item
        print(f"新元组为：{newItem}")
        # 如果文件存在,就执行
        if os.path.exists(workbook_file_path):
            wb = load_workbook(workbook_file_path)
            ws = wb[sheet_name]
            ws.append(newItem)
            wb.save(workbook_file_path)
            
            # 列表
            data = list(ws.values)
            #print(data)
            return short_id,data
        else:
            print("timeTask文件不存在, 添加数据失败")
            return "",[]
        
        
    # 置为失效
    def disableItemToExcel(self, item, file_name=__file_name, sheet_name=__sheet_name):
        #读取数据
        data = self.readExcel(file_name, sheet_name)
        if len(data) > 0:
            # 表格对象
            workbook_file_path = self.get_file_path(file_name)
            wb = load_workbook(workbook_file_path)
            ws = wb[sheet_name]
            #遍历
            for index, hisItem in enumerate(data):
                 if hisItem == item:
                    #置为已消费：即0
                    ws.cell(index, 1).value = "0"
            #保存
            wb.save(workbook_file_path)
        else:
            print("timeTask文件无数据, 消费数据失败")
            
            
    #计算唯一ID        
    def get_short_id(self, string):
        # 使用 MD5 哈希算法计算字符串的哈希值
        hash_value = hashlib.md5(string.encode()).digest()
    
        # 将哈希值转换为一个 64 进制的短字符串
        short_id = base64.urlsafe_b64encode(hash_value)[:8].decode()
        return short_id
    
    
    #获取文件路径      
    def get_file_path(self, file_name=__file_name):
        # 文件路径
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        workbook_file_path = current_dir + "/" + self.__dir_name + "/" + file_name
        
        # 工作簿当前目录
        workbook_dir_path = os.path.dirname(workbook_file_path)
        # 创建目录
        if not os.path.exists(workbook_dir_path):
            # 创建工作簿路径,makedirs可以创建级联路径
            os.makedirs(workbook_dir_path)
            
        return workbook_file_path
        