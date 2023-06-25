# encoding:utf-8

from plugins.timetask.Tool import ExcelTool
from plugins.timetask.Tool import TimeTaskModel
import logging
import arrow
import time
import threading
import re
from plugins.timetask.config import conf, load_config


class TaskManager(object):
    
    def __init__(self):
        super().__init__()
        logging.info("[TimeTask] inited")
        
        #excel创建
        obj = ExcelTool()
        obj.create_excel()
        #任务数组
        tempArray = obj.readExcel()
        self.convetDataToModelArray(tempArray)
        
        #配置加载
        load_config()
        self.conf = conf()
        self.debug = self.conf.get("debug", False)
        
        # 创建子线程
        t = threading.Thread(target=self.pingTimeTask_in_sub_thread)
        t.start()
        
    # 定义子线程函数
    def pingTimeTask_in_sub_thread(self):
        while True:
            # 定时检测
            self.timeCheck()
            #默认每秒检测一次
            time_check_rate = self.conf.get("time_check_rate", 1)
            time.sleep(int(time_check_rate))
    
    #时间检查
    def timeCheck(self):
        
        modelArray = self.timeTasks
        if len(modelArray) <= 0:
            return
        
        #临时数组
        tempArray = []
        #当前待消费数组
        currentExpendArray=[]
        #遍历检查时间
        for model in modelArray:
            #是否现在时刻
            is_nowTime = model.is_nowTime()
            #是否未来时间
            is_featureTime = model.is_featureTime()
            if model.enable and (is_nowTime or is_featureTime):
                if is_nowTime:
                    currentExpendArray.append(model)
                elif is_featureTime:
                    tempArray.append(model)
                 
                 
        #将数组赋值数组，提升性能(若self.timeTasks 未被多线程更新，赋值为待执行任务组)
        if self.timeTasks == modelArray and self.timeTasks != tempArray:
            #将任务数组 更新为 待执行数组； 本次任务在下面执行消费逻辑
            self.timeTasks = tempArray
        
        #当前无待消费任务     
        if len(currentExpendArray) <= 0:
            if self.debug:
                logging("[timetask][定时检测]：当前时刻 - 无定时任务...")
            return
        
        #消费本次task
        print(f"[timetask][定时检测]：当前时刻 - 存在定时任务, 准备消费: {currentExpendArray}")
        self.runTaskArray(currentExpendArray)
          
    #执行task
    def runTaskArray(self, modelArray: list[TimeTaskModel]):
        
        if len(modelArray) <= 0:
            return
        
        #执行任务列表
        for model in modelArray:
          #日期是否今天
          if model.is_today():
              self.runTaskItem(model)
                
    #执行task
    def runTaskItem(self, model : TimeTaskModel):
        #元素
        #time
        time = model.timeStr
        #循环信息
        cycleTimeInfo = model.circleTimeStr
        #消息内容
        messageInfo = model.eventStr
        #@用户
        toUser = model.toUser
        #isGroup
        isGroup = model.isGroup
        
        print("触发了定时任务：{}".format(model))
        
        #发消息
        
        #任务消费
        ExcelTool().disableItemToExcel(model.get_formatItem())
        
    #添加任务
    def addTask(self, taskModel: TimeTaskModel):
        taskList = ExcelTool().addItemToExcel(taskModel.get_formatItem())
        self.convetDataToModelArray(taskList)
        return taskModel.taskId   
    
     #model数组转换
    def convetDataToModelArray(self, dataArray):
        tempArray = []
        for item in dataArray:
            model = TimeTaskModel(item, False)
            tempArray.append(model)
        #赋值
        self.timeTasks : list[TimeTaskModel] = tempArray