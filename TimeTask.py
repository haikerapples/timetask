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
                    msg.other_user_id, 
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
        
        
    #执行定时task
    def runTimeTask(self, model: TimeTaskModel):
        
        print("触发了定时任务：{}".format(model))
        
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
              if event_content.startswith(key_word):
                index = event_content.find(key_word)
                event_content = event_content[:index] + func_command_prefix + key_word + event_content[index+len(key_word):]
                break
            
            #找到了拓展功能
            isFindExFuc = model.eventStr != event_content
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
            if len(reply_text) <= 0:
                reply_text = "⏰定时任务，时间已到啦~\n" + "【任务详情】：" + model.eventStr
                  
            #群聊处理
            if model.isGroup:
                reply_text = "@" + model.fromUser + "\n" + reply_text.strip()
                reply_text = conf().get("group_chat_reply_prefix", "") + reply_text + conf().get("group_chat_reply_suffix", "")
            else:
                reply_text = conf().get("single_chat_reply_prefix", "") + reply_text + conf().get("single_chat_reply_suffix", "")
            receiver = model.other_user_id
            itchat.send(reply_text, toUserName=receiver)


    #help信息
    def get_help_text(self, **kwargs):
        h_str = "🎉功能一：添加定时任务\n"
        codeStr = "【指令】：$time 周期 时间 事件\n"
        circleStr = "【周期支持】：今天、明天、后天、每天、工作日、每周X（如：每周三）、YYYY-MM-DD的日期\n"
        timeStr = "【时间支持】：X点X分（如：十点十分）、HH:mm:ss的时间\n"
        exampleStr = "\n👉示例：$time 明天 十点十分 提醒我健身\n\n\n"
        tempStr = h_str + codeStr + circleStr + timeStr + exampleStr
        
        h_str1 = "🎉功能二：取消定时任务\n"
        codeStr1 = "【指令】：$time 取消任务 任务ID\n"
        taskId1 = "【任务ID】：任务ID（添加任务成功时，机器人回复中有）\n"
        exampleStr1 = "\n👉示例：$time 取消任务 urwOi0he\n\n\n"
        tempStr1 = h_str1 + codeStr1 + taskId1 + exampleStr1
        
        h_str2 = "🎉功能三：获取任务列表\n"
        codeStr2 = "【指令】：$time 任务列表\n"
        exampleStr2 = "\n👉示例：$time 任务列表\n\n\n"
        tempStr2 = h_str2 + codeStr2 + exampleStr2
        
        headStr = "📌 功能介绍：添加定时任务、取消定时任务，获取任务列表。\n\n"
        help_text = headStr + tempStr + tempStr1 + tempStr2
        return help_text
