# encoding:utf-8

from plugins.timetask.Tool import ExcelTool
from plugins.timetask.Tool import TimeTaskModel
import logging
import time
import arrow
import threading
from plugins.timetask.config import conf, load_config

class TaskManager(object):
    
    def __init__(self, timeTaskFunc):
        super().__init__()
        #保存定时任务回调
        self.timeTaskFunc = timeTaskFunc
        
        # 创建子线程
        t = threading.Thread(target=self.pingTimeTask_in_sub_thread)
        t.setDaemon(True) 
        t.start()
        
    # 定义子线程函数
    def pingTimeTask_in_sub_thread(self):
        
        #配置加载
        load_config()
        self.conf = conf()
        self.debug = self.conf.get("debug", False)
        #迁移任务的时间
        self.move_historyTask_time = self.conf.get("move_historyTask_time", "04:00:00")
        #默认每秒检测一次
        self.time_check_rate = self.conf.get("time_check_rate", 1)
        #是否需要将过期任务移除近历史数据
        self.isMoveTask_toHistory = False
        
        #excel创建
        obj = ExcelTool()
        obj.create_excel()
        #任务数组
        tempArray = obj.readExcel()
        #转化数组
        self.convetDataToModelArray(tempArray)
        #过期任务数组、现在待消费数组、未来任务数组
        historyArray, currentExpendArray, featureArray = self.getFuncArray(self.timeTasks)
        #启动时，默认迁移一次过期任务
        obj.moveTasksToHistoryExcel(historyArray)
        #赋值数组
        self.timeTasks = currentExpendArray + featureArray
        
        #循环
        while True:
            # 定时检测
            self.timeCheck()
            time.sleep(int(self.time_check_rate))
    
    #时间检查
    def timeCheck(self):
        #任务数组
        modelArray = self.timeTasks
        if len(modelArray) <= 0:
            return
        
        #过期任务数组、现在待消费数组、未来任务数组
        historyArray, currentExpendArray, featureArray = self.getFuncArray(modelArray)
        
        #是否目标时间
        if self.is_targetTime(self.move_historyTask_time):
            self.isMoveTask_toHistory = True
                        
        #迁移过期任务
        if self.isMoveTask_toHistory and len(historyArray) > 0:
            self.isMoveTask_toHistory = False
            newTimeTask = ExcelTool().moveTasksToHistoryExcel(historyArray)
            #数据刷新
            self.convetDataToModelArray(newTimeTask)
                    
        #将数组赋值数组，提升性能(若self.timeTasks 未被多线程更新，赋值为待执行任务组)
        timeTask_ids = '😄'.join(item.taskId for item in self.timeTasks)
        modelArray_ids = '😄'.join(item.taskId for item in modelArray)
        featureArray_ids = '😄'.join(item.taskId for item in featureArray)
        if timeTask_ids == modelArray_ids and timeTask_ids != featureArray_ids:
            #将任务数组 更新为 待执行数组； 当前任务在下面执行消费逻辑
            self.timeTasks = featureArray
            print(f"内存任务更新：原任务列表 -> 待执行任务列表")
            print(f"原任务ID列表：{timeTask_ids}")
            print(f"待执行任务ID列表：{featureArray_ids}")
        
        #当前无待消费任务     
        if len(currentExpendArray) <= 0:
            if self.debug:
                logging.info("[timetask][定时检测]：当前时刻 - 无定时任务...")
            return
        
        #消费当前task
        print(f"[timetask][定时检测]：当前时刻 - 存在定时任务, 执行消费 当前时刻任务")
        self.runTaskArray(currentExpendArray)
        
    #获取功能数组    
    def getFuncArray(self, modelArray):
        #待消费数组
        featureArray = []
        #当前待消费数组
        currentExpendArray=[]
        #过期任务数组
        historyArray=[]
        #遍历检查时间
        for model in modelArray:
            #是否现在时刻
            is_nowTime = model.is_nowTime()
            #是否未来时刻
            is_featureTime = model.is_featureTime()
            #是否today
            is_today = model.is_today()
            #是否未来day
            is_featureDay = model.is_featureDay()
            if model.enable:
                if is_nowTime and is_today:
                    currentExpendArray.append(model)
                elif (is_featureTime and is_today) or is_featureDay:
                    featureArray.append(model)
                else:
                    historyArray.append(model.get_formatItem())
            else:
                historyArray.append(model.get_formatItem())  
        
        return  historyArray, currentExpendArray, featureArray     
        
          
    #执行task
    def runTaskArray(self, modelArray: list[TimeTaskModel]):
        
        #执行任务列表
        for index, model in enumerate(modelArray):
            self.runTaskItem(model)
                
    #执行task
    def runTaskItem(self, model: TimeTaskModel):
        print(f"😄执行定时任务:【{model.taskId}】，任务详情：{model.circleTimeStr} {model.timeStr} {model.eventStr}")
        #回调定时任务执行
        self.timeTaskFunc(model)
        
        #任务消费
        if not model.is_featureDay():
            obj = ExcelTool()
            obj.disableItemToExcel(model.taskId)
            #重载内存数组
            tempArray = obj.readExcel()
            self.convetDataToModelArray(tempArray)
        
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
        
    #是否目标时间      
    def is_targetTime(self, timeStr):
        tempTimeStr = timeStr
        #如果以00结尾，对比精准度为分钟
        if tempTimeStr.count(":") == 2 and tempTimeStr.endswith("00"):
           return (arrow.now().format('HH:mm') + ":00") == tempTimeStr
        #对比精准到秒 
        tempValue = arrow.now().format('HH:mm:ss') == tempTimeStr
        return tempValue     