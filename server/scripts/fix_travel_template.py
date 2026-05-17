"""Fix travel template scoring to 0-100 scale matching code threshold (score >= 40)."""
import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

DB = 'server/app/data/dy_auto.db'
conn = sqlite3.connect(DB)
row = conn.execute("SELECT content FROM prompt_templates WHERE industry='travel'").fetchone()
content = json.loads(row[0])

# --- analysis ---
content['analysis']['scoringRules'] = [
    "高价值信号每命中1个 +20分，信号可累积",
    "携带询问价格/费用/预算意图 +15分",
    "携带行程/时间/路线咨询意图 +12分",
    "携带明确目的地或景点名称 +10分",
    "倾向positive或curious +5分",
    "倾向negative -10分",
    "低价值信号每命中1个 -5分，如纯赞美、表情包、无关闲聊",
    "总分低于20分为低价值，20-39中等价值，40分及以上高价值"
]

content['analysis']['tiers'] = {
    "high_value": "score>=40: 主动提供专业建议、个性化方案，使用您，提供一站式服务引导",
    "medium_value": "score 20-39: 友好互动、信息提供，进一步了解需求，使用你/您均可",
    "low_value": "score<20: 简短互动、礼貌回应，如谢谢支持"
}

content['analysis']['replyRules'] = [
    "对高价值用户(score>=40)：先肯定其兴趣，了解具体需求，提供个性化建议方向",
    "对中等价值用户(20-39)：提供1-2个关键信息点，引导进一步互动",
    "对低价值用户(<20)：简单互动或不回复，保持礼貌",
    "回复中禁止直接报价，应引导私信进一步沟通",
    "情绪为负面时，先共情再尝试扭转"
]

content['analysis']['intents'] = [
    "inquiry_price: 询问价格、费用、预算、人均消费、性价比",
    "inquiry_itinerary: 询问行程天数、路线安排、游玩项目、景点推荐",
    "inquiry_logistics: 询问交通、住宿、餐饮、签证等出行细节",
    "express_interest: 表达兴趣或向往，如想去/好想去/计划中",
    "planning: 提及具体出行时间、人数、目的地等规划要素",
    "experience_sharing: 分享个人经历，如去过/那边的确不错",
    "comparison: 对比不同选项，如跟团vs自由行/A地vs B地",
    "concern: 表达顾虑或担忧，如安全/被宰/语言不通"
]

content['analysis']['sentiments'] = [
    "positive: 兴奋、期待、赞美",
    "neutral: 客观咨询，无情绪倾向",
    "negative: 抱怨、担忧、失望",
    "curious: 好奇、探索，如真的吗/详细说说"
]

# --- semanticGuide ---
content['semanticGuide']['highValueSignals'] = [
    "明确目的地需求：提到具体地点如贵州/云南/日本 或 景点名称 — 有真实目的地意向",
    "询问具体费用：问多少钱/贵不贵/预算/人均消费 — 有购买意向",
    "询问行程安排：问几天/怎么玩/什么项目/路线规划 — 深度需求",
    "提及出行时间：五一/暑假/国庆/几月份去最好/最近想去 — 时效性需求",
    "提及同行人群：带娃/老人/情侣/一个人/朋友一起 — 可定位人群",
    "求推荐/求攻略：有什么推荐/怎么安排/第一次去/不了解 — 信息需求强",
    "对比选择：跟团还是自由行/哪个好玩/A和B选哪个 — 决策阶段",
    "信任/安全顾虑：靠谱吗/安全吗/会不会被宰 — 需要建立信任"
]

content['semanticGuide']['lowValueSignals'] = [
    "纯表情或纯标点评论：😊/666/👍 — 无实质内容",
    "简单赞美视频画面：好美/真漂亮/拍摄得不错 — 无旅游需求",
    "与旅游无关的闲聊：今天天气不错/这背景音乐叫什么 — 偏离主题",
    "纯广告或引流：加微信/看我主页 — 竞品/垃圾",
    "负能量发泄无建设性：无聊/浪费时间 — 非目标用户"
]

content['semanticGuide']['keyExamples'] = [
    "评论'想去贵州，一周大概多少钱？有哪些必去的景点？' — 高价值信号：目的地+费用+行程 — 预计score 55-65",
    "评论'暑假想带孩子去，有亲子团吗？几月份去最好？' — 高价值信号：时间+人群+产品类型 — 预计score 50-60",
    "评论'好美啊！一直想去都没去成' — 中等价值信号：表达兴趣但无具体需求 — 预计score 25-35",
    "评论'太漂亮了' — 低价值信号：纯赞美 — 预计score 5-10",
    "评论'跟团好还是自由行好？求过来人给个建议' — 高价值信号：对比决策+求推荐 — 预计score 45-55",
    "评论'刚去过，千万不要跟团，坑死了！自由行香多了' — 中等价值：经验分享负面情绪 — 预计score 25-35"
]

conn.execute("UPDATE prompt_templates SET content = ? WHERE industry='travel'",
             [json.dumps(content, ensure_ascii=True)])
conn.commit()
print("Updated travel template scoring to 0-100 scale.")
conn.close()
