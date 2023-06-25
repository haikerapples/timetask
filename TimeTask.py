# encoding:utf-8
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
import logging
from plugins import *
import logging
from plugins.timetask.TimeTaskTool import TaskManager
from plugins.timetask.config import conf, load_config
from plugins.timetask.Tool import TimeTaskModel

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
            #移除指令
            #示例：$time 明天 十点十分 提醒我健身
            content = query.replace(f"{command_prefix} ", "")
            content = content.replace(command_prefix, "")
            self.deal_timeTask(query, e_context)

    
    #处理时间任务
    def deal_timeTask(self, content, e_context: EventContext):
        
        #分割
        wordsArray = content.split(" ")
        if len(wordsArray) <= 2:
              logging.info("指令格式异常，请核查！示例: $time 明天 十点十分 提醒我健身")
              return
        
        #指令解析
        #周期
        circleStr = wordsArray[0]
        #时间
        timeStr = wordsArray[1]
        #事件
        eventStr = ','.join(map(str, wordsArray[2:]))
        
        #容错
        if len(circleStr) <= 0 or len(timeStr) <= 0 or len(eventStr) <= 0 :
            return
        
        #0：ID - 唯一ID (自动生成，无需填写) 
        #1：是否可用 - 0/1，0=不可用，1=可用
        #2：时间信息 - 格式为：HH:mm:ss
        #3：轮询信息 - 格式为：每天、每周X、YYYY-MM-DD
        #4：消息内容 - 消息内容
        #5：fromUser - 来源user
        #6：toUser - 发送给的user
        #7：isGroup - 0/1，是否群聊； 0=否，1=是
        #8：原始内容 - 原始的消息体
        msg: ChatMessage = e_context["context"]["msg"]
        taskInfo = ("",
                    "1", 
                    timeStr, 
                    circleStr, 
                    eventStr, 
                    msg.from_user_nickname,
                    msg.to_user_nickname, 
                    str(msg.is_group), 
                    str(msg))
        #model
        taskModel = TimeTaskModel(taskInfo, True)
        #容错
        if len(taskModel.timeStr) <= 0 or len(taskModel.circleTimeStr) <= 0:
            return
        
        #task入库
        taskId = self.taskManager.addTask(taskModel)
        #回消息
        self.replay_message(content, e_context, taskId)
          
    
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
