# encoding:utf-8
import plugins
from bridge.context import ContextType, Context
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
import logging
from plugins import *
import logging
from plugins.timetask.TimeTaskTool import TaskManager
from plugins.timetask.config import conf, load_config
from plugins.timetask.Tool import TimeTaskModel
from lib import itchat
from lib.itchat.content import *
import re
import arrow
from plugins.timetask.Tool import ExcelTool

class TimeTaskRemindType(Enum):
    NO_Task = 1           #无任务
    Add_Success = 2       #添加任务成功
    Add_Failed = 3        #添加任务失败
    Cancel_Success = 4    #取消任务成功
    Cancel_Failed = 5     #取消任务失败
    TaskList_Success = 6  #查看任务列表成功
    TaskList_Failed = 7   #查看任务列表失败

@plugins.register(
    name="timetask",
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
        load_config()
        self.conf = conf()
        self.taskManager = TaskManager(self.runTimeTask)
        
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
            #移除指令
            #示例：$time 明天 十点十分 提醒我健身
            content = query.replace(f"{command_prefix} ", "")
            content = content.replace(command_prefix, "")
            self.deal_timeTask(content, e_context)

    #处理时间任务
    def deal_timeTask(self, content, e_context: EventContext):
        
        if content.startswith("取消任务"):
            self.cancel_timeTask(content, e_context)
            
        elif content.startswith("任务列表"):
            self.get_timeTaskList(content, e_context)
            
        else:
            self.add_timeTask(content, e_context)
        
    #取消任务
    def cancel_timeTask(self, content, e_context: EventContext):
        #分割
        wordsArray = content.split(" ")
        #任务Id
        taskId = wordsArray[1]
        isExist,taskContent = ExcelTool().disableItemToExcel(taskId)
        
        #回消息
        reply_text = ""
        tempStr = ""
        #文案
        if isExist:
            tempStr = self.get_default_remind(TimeTaskRemindType.Cancel_Success)
            reply_text = "⏰定时任务，取消成功~\n" + "【任务ID】：" + taskId + "\n" + "【任务详情】：" + taskContent
        else:
            tempStr = self.get_default_remind(TimeTaskRemindType.Cancel_Failed)
            reply_text = "⏰定时任务，取消失败😭，未找到任务ID，请核查\n" + "【任务ID】：" + taskId
        
        #拼接提示
        reply_text = reply_text + tempStr
        #回复
        self.replay_use_default(reply_text, e_context)  
        
        
    #获取任务列表
    def get_timeTaskList(self, content, e_context: EventContext):
        
        #任务列表
        taskArray = ExcelTool().readExcel()
        tempArray = []
        for item in taskArray:
            model = TimeTaskModel(item, False)
            if model.enable and model.taskId and len(model.taskId) > 0:
                isToday = model.is_today()
                isNowOrFeatureTime = model.is_featureTime() or model.is_nowTime()
                isCircleFeatureDay = model.is_featureDay()
                if (isToday and isNowOrFeatureTime) or isCircleFeatureDay:
                    tempArray.append(model)
        
        #回消息
        reply_text = ""
        tempStr = ""
        if len(tempArray) <= 0:
            tempStr = self.get_default_remind(TimeTaskRemindType.NO_Task)
            reply_text = "⏰当前无待执行的任务列表"
        else:
            tempStr = self.get_default_remind(TimeTaskRemindType.TaskList_Success)
            reply_text = "⏰定时任务列表如下：\n\n"
            #根据时间排序
            sorted_times = sorted(tempArray, key=lambda x: self.custom_sort(x.timeStr))
            for taskModel in sorted_times:
                reply_text = reply_text + f"【{taskModel.taskId}】@{taskModel.fromUser}: {taskModel.circleTimeStr} {taskModel.timeStr} {taskModel.eventStr}\n"   
            #移除最后一个换行    
            reply_text = reply_text.rstrip('\n')
            
        #拼接提示
        reply_text = reply_text + tempStr
        
        #回复
        self.replay_use_default(reply_text, e_context)    
        
          
    #添加任务
    def add_timeTask(self, content, e_context: EventContext):
        #失败时，默认提示
        defaultErrorMsg = "⏰定时任务指令格式异常😭，请核查！" + self.get_default_remind(TimeTaskRemindType.Add_Failed)
        #分割
        wordsArray = content.split(" ")
        if len(wordsArray) <= 2:
              logging.info("指令格式异常，请核查")
              self.replay_use_default(defaultErrorMsg)
              return
        
        #指令解析
        #周期
        circleStr = wordsArray[0]
        #时间
        timeStr = wordsArray[1]
        #事件
        eventStr = ' '.join(map(str, wordsArray[2:]))
        
        #容错
        if len(circleStr) <= 0 or len(timeStr) <= 0 or len(eventStr) <= 0 :
            self.replay_use_default(defaultErrorMsg)
            return
        
        #0：ID - 唯一ID (自动生成，无需填写) 
        #1：是否可用 - 0/1，0=不可用，1=可用
        #2：时间信息 - 格式为：HH:mm:ss
        #3：轮询信息 - 格式为：每天、每周X、YYYY-MM-DD
        #4：消息内容 - 消息内容
        #5：fromUser - 来源user
        #6：toUser - 发送给的user
        #7：other_user_id - other_user_id
        #8：isGroup - 0/1，是否群聊； 0=否，1=是
        #9：原始内容 - 原始的消息体
        msg: ChatMessage = e_context["context"]["msg"]
        taskInfo = ("",
                    "1", 
                    timeStr, 
                    circleStr, 
                    eventStr, 
                    msg.from_user_nickname,
                    msg.to_user_nickname, 
                    msg.other_user_id, 
                    str(msg.is_group), 
                    str(msg))
        #model
        taskModel = TimeTaskModel(taskInfo, True)
        #容错
        if len(taskModel.timeStr) <= 0 or len(taskModel.circleTimeStr) <= 0:
            self.replay_use_default(defaultErrorMsg)
            return
        
        #task入库
        taskId = self.taskManager.addTask(taskModel)
        #回消息
        reply_text = ""
        tempStr = ""
        if len(taskId) > 0:
            tempStr = self.get_default_remind(TimeTaskRemindType.Add_Success)
            reply_text = f"恭喜你，⏰定时任务已创建成功🎉~\n【任务ID】：{taskId}\n【任务详情】：{taskModel.eventStr}"
        else:
            tempStr = self.get_default_remind(TimeTaskRemindType.Add_Failed)
            reply_text = f"sorry，⏰定时任务创建失败😭"
            
        #拼接提示
        reply_text = reply_text + tempStr
            
        #回复
        self.replay_use_default(reply_text, e_context)
        
        
    #使用默认的回复
    def replay_use_default(self, reply_message, e_context: EventContext):
        #回复内容
        reply = Reply()
        reply.type = ReplyType.TEXT
        reply.content = reply_message
        e_context["reply"] = reply
        e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
        
    #执行定时task
    def runTimeTask(self, model: TimeTaskModel):
        
        print("触发了定时任务：{} , 任务详情：{}".format(model.taskId, model.eventStr))
        
        #去除多余字符串
        orgin_string = model.originMsg.replace("ChatMessage:", "")
        # 使用正则表达式匹配键值对
        pattern = r'(\w+)\s*=\s*([^,]+)'
        matches = re.findall(pattern, orgin_string)
        # 创建字典
        content_dict = {match[0]: match[1] for match in matches}
        
        #查看配置中是否开启拓展功能
        is_open_extension_function = self.conf.get("is_open_extension_function", True)
        #需要拓展功能
        if is_open_extension_function:
            #事件字符串
            event_content = model.eventStr
            #支持的功能
            funcArray = self.conf.get("extension_function", [])
            for item in funcArray:
              key_word = item["key_word"]
              func_command_prefix = item["func_command_prefix"]
              #匹配到了拓展功能
              isFindExFuc = False
              if event_content.startswith(key_word):
                index = event_content.find(key_word)
                event_content = event_content[:index] + func_command_prefix + key_word + event_content[index+len(key_word):]
                isFindExFuc = True
                break
            
            #找到了拓展功能
            e_context = None
            if isFindExFuc:
                #替换源消息中的指令
                content_dict["content"] = event_content
                #添加必要key
                content_dict["receiver"] = model.other_user_id
                content_dict["session_id"] = model.other_user_id
                context = Context(ContextType.TEXT, event_content, content_dict)
                #检测插件是否会消费该消息
                e_context = PluginManager().emit_event(
                    EventContext(
                        Event.ON_HANDLE_CONTEXT,
                        {"channel": self, "context": context, "reply": Reply()},
                    )
                )
        
        #未找到拓展功能 或 未开启拓展功能，则发源消息
        if not isFindExFuc or e_context:
            #回复原消息
            if e_context:
                reply_text = e_context["reply"].content
                
            #默认文案
            if reply_text and len(reply_text) <= 0:
                reply_text = "⏰叮铃铃，定时任务时间已到啦~\n" + "【任务详情】：" + model.eventStr
                  
            #群聊处理
            if model.isGroup:
                reply_text = "@" + model.fromUser + "\n" + reply_text.strip()
                
            receiver = model.other_user_id
            itchat.send(reply_text, toUserName=receiver)


    # 自定义排序函数，将字符串解析为 arrow 对象，并按时间进行排序
    def custom_sort(self, time):
        return arrow.get(time, "HH:mm:ss")
    
    # 默认的提示
    def get_default_remind(self, currentType: TimeTaskRemindType):
        #head
        head = "\n\n【温馨提示】\n"
        addTask = "👉添加任务：$time 明天 十点十分 提醒我健身" + "\n"
        cancelTask = "👉取消任务：$time 取消任务 任务ID" + "\n"
        taskList = "👉任务列表：$time 任务列表" + "\n"
        more = "👉更多功能：#help timetask"
        
        # NO_Task = 1           #无任务
        # Add_Success = 2       #添加任务成功
        # Add_Failed = 3        #添加任务失败
        # Cancel_Success = 4    #取消任务成功
        # Cancel_Failed = 5     #取消任务失败
        # TaskList_Success = 6  #查看任务列表成功
        # TaskList_Failed = 7   #查看任务列表失败
    
        #组装
        tempStr = head
        if currentType == TimeTaskRemindType.NO_Task:
           tempStr = tempStr + addTask + cancelTask + taskList
            
        elif currentType == TimeTaskRemindType.Add_Success:
            tempStr = tempStr + cancelTask + taskList
            
        elif currentType == TimeTaskRemindType.Add_Failed:
            tempStr = tempStr + addTask + cancelTask + taskList
            
        elif currentType == TimeTaskRemindType.Cancel_Success:
            tempStr = tempStr + addTask + taskList 
            
        elif currentType == TimeTaskRemindType.Cancel_Failed:
            tempStr = tempStr + addTask + cancelTask + taskList
            
        elif currentType == TimeTaskRemindType.TaskList_Success:
            tempStr = tempStr + addTask + cancelTask
            
        elif currentType == TimeTaskRemindType.TaskList_Failed:
            tempStr = tempStr + addTask + cancelTask + taskList   
                      
        else:
          tempStr = tempStr + addTask + cancelTask + taskList
          
        #拼接help指令
        tempStr = tempStr + more
          
        return tempStr
    
    #help信息
    def get_help_text(self, **kwargs):
        h_str = "🎉功能一：添加定时任务\n"
        codeStr = "【指令】：$time 周期 时间 事件\n"
        circleStr = "【周期支持】：今天、明天、后天、每天、工作日、每周X（如：每周三）、YYYY-MM-DD的日期\n"
        timeStr = "【时间支持】：X点X分（如：十点十分）、HH:mm:ss的时间\n"
        enventStr = "【事件支持】：早报、点歌、搜索、文案提醒（如：提醒我健身）\n"
        exampleStr = "\n👉示例：$time 明天 十点十分 提醒我健身\n\n\n"
        tempStr = h_str + codeStr + circleStr + timeStr + enventStr + exampleStr
        
        h_str1 = "🎉功能二：取消定时任务\n"
        codeStr1 = "【指令】：$time 取消任务 任务ID\n"
        taskId1 = "【任务ID】：任务ID（添加任务成功时，机器人回复中有）\n"
        exampleStr1 = "\n👉示例：$time 取消任务 urwOi0he\n\n\n"
        tempStr1 = h_str1 + codeStr1 + taskId1 + exampleStr1
        
        h_str2 = "🎉功能三：获取任务列表\n"
        codeStr2 = "【指令】：$time 任务列表\n"
        exampleStr2 = "\n👉示例：$time 任务列表\n\n\n"
        tempStr2 = h_str2 + codeStr2 + exampleStr2
        
        headStr = "📌 功能介绍：添加定时任务、取消定时任务、获取任务列表。\n\n"
        help_text = headStr + tempStr + tempStr1 + tempStr2
        return help_text