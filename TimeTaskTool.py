# encoding:utf-8

from plugins.timetask.Tool import ExcelTool
import logging
import arrow
import time
import threading
import re
from plugins.timetask.config import conf, load_config


class TaskManager(object):
    #内存中定时任务的二维数组，数据格式：[[是否可用, 时间信息, 轮询信息, 消息内容, fromUser, toUser, isGroup, 原始内容]]
    #0：ID - 唯一ID (自动生成，无需填写)
    #1：是否可用 - 0/1，0=不可用，1=可用
    #2：时间信息 - 格式为：HH:mm:ss
    #3：轮询信息 - 格式为：每天、每周N、YYYY-MM-DD
    #4：消息内容 - 消息内容
    #5：fromUser - 来源user
    #6：toUser - 发送给的user
    #7：isGroup - 0/1，是否群聊； 0=否，1=是
    #8：原始内容 - 原始的消息体
    
    def __init__(self):
        super().__init__()
        logging.info("[TimeTask] inited")
        obj = ExcelTool()
        obj.create_excel()
        self.timeTasks = obj.readExcel()
        load_config()
        self.conf = conf()
        
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
        
        timeObjArray = self.timeTasks
        if len(timeObjArray) <= 0:
            return
        
        #临时数组
        tempArray = []
        #当前待消费数组
        currentExpendArray=[]
        #遍历检查时间
        for exItem in timeObjArray:
         #enable
         item_enable = exItem[1]
         #time
         item_time = exItem[2]
         # 将待比较的时间字符串转换为Arrow对象
         isTimeGood = arrow.get(item_time, 'HH:mm:ss').time() > arrow.now().time()
         isTimeCurrent = arrow.now().format('HH:mm:ss') == item_time
         if item_enable == "1" and (isTimeGood or isTimeCurrent):
             if isTimeCurrent:
                 currentExpendArray.append(exItem)
             elif isTimeGood:
                 tempArray.append(exItem)
                 
                 
        #将数组赋值数组，提升性能(若self.timeTasks 未被多线程更新，赋值为待执行任务组)
        if self.timeTasks == timeObjArray and self.timeTasks != tempArray:
            self.timeTasks = tempArray
        
        #当前无待消费任务     
        if len(currentExpendArray) <= 0:
            debug = conf().get("debug", False)
            if debug:
                logging("[timetask][定时检测]：当前时刻 - 无定时任务...")
            return
        
        #执行task
        print(f"[timetask][定时检测]：当前时刻 - 存在定时任务, 准备执行: {currentExpendArray}")
        self.runTaskArray(currentExpendArray)
          
    #执行task
    def runTaskArray(self, timeObjArray):
        
        if len(timeObjArray) <= 0:
            return
        
        # 当前时间
        current_time = arrow.now() 
        for exItem in timeObjArray:
          #轮询信息
          item_circle = exItem[3]
          if self.is_valid_date(item_circle):
                #日期相等
                if item_circle == current_time.format('YYYY-MM-DD'):
                    #今天要出发的任务
                    print(f"[定时任务执行][类型-录入日期]：即将执行任务, 日期信息：{item_circle}")
                    self.runTaskItem(exItem)
                else:
                    #其他时间待出发
                    print(f"[定时任务执行][类型-录入日期]：非法任务，日期信息：{item_circle}")
          elif "每天" in item_circle:
              #今天要出发的任务
              print(f"[定时任务执行][类型-每天]：即将执行任务")
              self.runTaskItem(exItem)
          elif "每周" in item_circle or "每星期" in item_circle:
              if self.is_today_weekday(item_circle):
                    print(f"[定时任务执行][类型-每周]：即将执行任务")
                    self.runTaskItem(exItem)
              else:
                    print(f"[定时任务执行][类型-每周]：非法任务，日期信息为：{item_circle}")     
                
                
    #执行task
    def runTaskItem(self, item):
        #元素
        #time
        time = item[2]
        #循环信息
        cycleTimeInfo = item[3]
        #消息内容
        messageInfo = item[4]
        #@用户
        toUser = item[6]
        #isGroup
        isGroup = item[7]
        
        print("触发了定时任务：{}".format(item))
        
        #发消息
        
        #任务消费
        ExcelTool().disableItemToExcel(item)
        
    #添加任务
    def addTask(self, task):
        taskId, taskList = ExcelTool().addItemToExcel(task)
        self.timeTasks = taskList
        return taskId    
                
    def is_today_weekday(self, weekday_str):
        # 将中文数字转换为阿拉伯数字
        weekday_dict = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7}
        weekday_num = weekday_dict.get(weekday_str[-1])
        if weekday_num is None:
            return False
        
        # 判断今天是否是指定的星期几
        today = arrow.now()
        return today.weekday() == weekday_num - 1        
        
      
    def is_valid_date(self, date_string):
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        match = pattern.match(date_string)
        return match is not None