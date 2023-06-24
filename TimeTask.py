# encoding:utf-8
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
import logging
from plugins import *
import logging
import arrow
import re
from plugins.timetask.TimeTaskTool import TaskManager
from plugins.timetask.config import conf, load_config

@plugins.register(
    name="TimeTask",
    desire_priority=0,
    hidden=True,
    desc="定时任务系统，可定时处理事件",
    version="0.1",
    author="haikerwang",
)
class TimeTask(Plugin):
    
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logging.info("[TimeTask] inited")
        self.taskManager = TaskManager()
        load_config()
        self.conf = conf()
        
        
    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
        ]:
            return
        
        #查询内容
        query = e_context["context"].content
        logging.info("定时任务的输入信息为:{}".format(query))
        #指令前缀
        command_prefix = self.conf.get("command_prefix", "$time")
        
        #需要的格式：$time 时间 事件
        if query.startswith(command_prefix) :
            #处理任务
            print("[TimeTask] 捕获到定时任务:{}".format(query))
            self.deal_timeTask(query, e_context)


    
    #处理时间任务
    def deal_timeTask(self, query, e_context: EventContext):
        #移除指令
        #示例：$time 明天 十点十分 提醒我健身
        content = query.replace("$time ", "")
        content = content.replace("$time", "")
        #分割
        wordsArray = content.split(" ")
        if len(wordsArray) <= 2:
              logging.info("定时任务的输入信息格式异常，请核查！示例:【$time 明天 十点十分 提醒我健身】，录入字符串：{}".format(query))
              return
        #周期
        circleStr = wordsArray[0]
        #时间
        timeStr = wordsArray[1]
        #事件
        eventStr = ','.join(map(str, wordsArray[2:]))
        
        #容错
        if len(circleStr) <= 0 or len(timeStr) <= 0 or len(eventStr) <= 0 :
            return
        
        #入库的周期、time
        g_circle = self.get_cicleDay(circleStr)
        g_time = self.get_time(timeStr)
        
        #时间非法
        if len(g_circle) <= 0 or len(g_time) <= 0:
            return
            
        #1：是否可用 - 0/1，0=不可用，1=可用
        #2：时间信息 - 格式为：HH:mm:ss
        #3：轮询信息 - 格式为：每天、每周N、YYYY-MM-DD
        #4：消息内容 - 消息内容
        #5：fromUser - 来源user
        #6：toUser - 发送给的user
        #7：isGroup - 0/1，是否群聊； 0=否，1=是
        #8：原始内容 - 原始的消息体
        msg: ChatMessage = e_context["context"]["msg"]
        taskInfo = ("1", g_time, g_circle, eventStr, msg.from_user_nickname,msg.to_user_nickname, str(msg.is_group), str(msg))
        taskId = self.taskManager.addTask(taskInfo)
        #回消息
        self.replay_message(query, e_context, taskId)   
          
    #获取周期
    def get_cicleDay(self, circleStr):
        # 定义正则表达式
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        # 是否符合 YYYY-MM-DD 格式的日期
        isGoodDay = re.match(pattern, circleStr)
        
        g_circle = ""
        #如果可被解析为具体日期
        if circleStr in ['今天', '明天', '后天']:
              #今天
              today = arrow.now('local')
              if circleStr == '今天':
                    # 将日期格式化为 YYYY-MM-DD 的格式
                    formatted_today = today.format('YYYY-MM-DD')
                    g_circle = formatted_today
                    
              elif circleStr == '明天':
                    tomorrow = today.shift(days=1)
                    formatted_tomorrow = tomorrow.format('YYYY-MM-DD')
                    g_circle = formatted_tomorrow
                    
              elif circleStr == '后天':
                    after_tomorrow = today.shift(days=2)
                    formatted_after_tomorrow = after_tomorrow.format('YYYY-MM-DD')
                    g_circle = formatted_after_tomorrow
              else:
                  print('暂不支持的格式')
                   
                    
        #YYYY-MM-DD 格式
        elif isGoodDay:
            g_circle = circleStr
            
        #每天、每周、工作日
        elif circleStr in ["每天", "每周", "工作日"]:
                g_circle = circleStr
        
        #每周X
        elif circleStr in ["每周一", "每周二", "每周三", "每周四", "每周五", "每周六","每周日","每周天", 
                           "每星期一", "每星期二","每星期三", "每星期四", "每星期五","每星期六", "每星期日", "每星期天"]:       
            #每天、每周X等
            g_circle = circleStr
            
        else:
            print('暂不支持的格式')
            
        return g_circle
    
    #获取时间
    def get_time(self, timeStr):
        pattern1 = r'^\d{2}:\d{2}:\d{2}$'
        pattern2 = r'^\d{2}:\d{2}$'
        # 是否符合 HH:mm:ss 格式
        time_good1 = re.match(pattern1, timeStr)
        # 是否符合 HH:mm 格式
        time_good2 = re.match(pattern2, timeStr)
        
        g_time = ""
        if time_good1 :
            g_time = timeStr
            
        elif time_good2:
            g_time = timeStr + ":00"
        
        elif '点' in timeStr or '分' in timeStr or '秒' in timeStr :
            content = timeStr.replace("点", ":")
            content = content.replace("分", ":")
            content = content.replace("秒", "")
            wordsArray = content.split(":")
            hour = "0"
            minute = "0"
            second = "0"
            digits = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, 
                '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15, '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20, 
                '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25, '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30, 
                '三十一': 31, '三十二': 32, '三十三': 33, '三十四': 34, '三十五': 35, '三十六': 36, '三十七': 37, '三十八': 38, '三十九': 39, '四十': 40, 
                '四十一': 41, '四十二': 42, '四十三': 43, '四十四': 44, '四十五': 45, '四十六': 46, '四十七': 47, '四十八': 48, '四十九': 49, '五十': 50, 
                '五十一': 51, '五十二': 52, '五十三': 53, '五十四': 54, '五十五': 55, '五十六': 56, '五十七': 57, '五十八': 58, '五十九': 59, '六十': 60, '半': 30}
            for index, item in enumerate(wordsArray):
                if index == 0 and len(item) > 0:
                    if re.search('[\u4e00-\u9fa5]', item):
                        hour = str(digits[item])
                    else:
                         hour = item   
                            
                elif index == 1 and len(item) > 0:
                    if re.search('[\u4e00-\u9fa5]', item):
                        minute = str(digits[item])
                    else:
                        minute = item
                        
                elif index == 2 and len(item) > 0:
                    if re.search('[\u4e00-\u9fa5]', item):
                        second = str(digits[item])
                    else:
                        second = item    
                        
            if int(hour) == 0:
                  hour = "00"
            if int(minute) == 0:
                  minute = "00"
            if int(second) == 0:
                  second = "00"            
            g_time = hour + ":" + minute + ":" + second                                       
            
        else:
            print('暂不支持的格式')
            
        #检测转换的时间是否合法    
        time_good1 = re.match(pattern1, g_time)
        if time_good1:
              return g_time
                 
        return ""
        
          
    
    #回复消息
    def replay_message(self, query, e_context: EventContext, taskID):
        reply_message = ""
        if len(taskID) > 0:
            reply_message = f"恭喜你，定时任务已创建成功🎉~\n【任务ID】：{taskID}\n【任务详情】：{query}"
        else:
            reply_message = f"sorry，定时任务创建失败😭" 

        #回复内容
        reply = Reply()
        reply.type = ReplyType.TEXT
        reply.content = reply_message
        e_context["reply"] = reply
        e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑


    #help信息
    def get_help_text(self, **kwargs):
        exampleStr = "示例：$time 明天 十点十分 提醒我健身\n"
        circleStr = "周期支持：今天、明天、后天、每天、每周X、YYYY-MM-DD的日期\n"
        timeStr = "时间支持：X点X分（如：十点十分）、HH:mm:ss的时间\n"
        help_text = "输入以下格式：$time 周期 时间 事件，将会启动指定的时间，启动任务。\n" + exampleStr + circleStr + timeStr
        return help_text
