"""Seed database from YAML config files. Idempotent — safe to run multiple times."""
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.db_models import Account, SensitiveWord, UISelector, PromptTemplate
from app.config import load_accounts_config, load_selectors_config


def seed_accounts(db: Session) -> int:
    """Import accounts from accounts.yaml. Skips existing (by id)."""
    accounts = load_accounts_config()
    added = 0
    for acc in accounts:
        existing = db.query(Account).filter(Account.id == acc["id"]).first()
        if existing:
            continue
        db.add(Account(
            id=acc["id"],
            nickname=acc.get("nickname", ""),
            douyin_id=acc.get("douyin_id", ""),
            group=acc.get("group", "default"),
            status=acc.get("status", "active"),
            daily_limits=acc.get("daily_limits", {
                "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
            }),
        ))
        added += 1
    db.commit()
    return added


def seed_selectors(db: Session) -> tuple[int, int]:
    """Import selectors from selectors.yaml. Returns (added, updated) counts.

    Only updates strategies if YAML version is higher than the existing version.
    This prevents seed from overwriting manual edits made via the API.
    """
    version, selectors = load_selectors_config()
    added = 0
    updated = 0
    for sel in selectors:
        existing = db.query(UISelector).filter(
            UISelector.action_name == sel["action_name"],
            UISelector.platform_version == sel.get("platform_version", "default"),
        ).first()
        if existing:
            # Only update if YAML version is higher (prevents overwriting manual edits)
            if version > existing.version:
                existing.strategies = sel["strategies"]
                existing.version = version
                updated += 1
            continue
        db.add(UISelector(
            action_name=sel["action_name"],
            platform_version=sel.get("platform_version", "default"),
            strategies=sel["strategies"],
            version=version,
        ))
        added += 1
    db.commit()
    return added, updated


def seed_prompt_templates(db: Session) -> int:
    """Create default prompt template if none exist."""
    existing = db.query(PromptTemplate).first()
    if existing:
        return 0

    default_content = {
        "identity": {
            "role": "「健康生活指南」视角，像一个靠谱的健康科普评论者",
            "constraints": [
                "不是医生，不做诊断，不保证疗效",
                "讨论的是日常饮食、生活习惯，不是治疗方案",
            ],
        },
        "disabledWords": "治愈 / 根治 / 治好 / 疗效保证 / 包好 / 替代药物 / 停药 / 不用吃药 /\n医生 / 我是医生 / 专家 / 我是专家 / 保证有效 / 百分百 / 100% / 神药",
        "semanticGuide": {
            "mission": "这条评论背后是不是一个\"有真实健康需求的人\"",
            "highValueSignals": [
                "提及具体病症/症状：糖尿病、高血压、失眠、便秘、湿气、痛风、关节痛、脱发、过敏、胃病、颈椎、腰椎等",
                "提及具体药物/治疗方式：胰岛素、降压药、降糖药、中药、艾灸、针灸、推拿、拔罐、理疗等",
                "询问\"能不能好/会不会好转\"：有转机不、能恢复吗、还能好吗、有救吗 → 透露出正在经历这个病",
                "询问\"是不是得一直/一辈子\"：是不是得用一辈子、离不开吗、要一直吃吗 → 已在用药，想摆脱依赖",
                "询问\"有什么讲究/注意/忌口\"：有啥讲究、要注意什么、能吃吗、有什么禁忌 → 已在管理这个病",
                "自述症状/经历：\"最近总是…\"、\"我XX已经…年了\"、\"每次…都…\"、\"XX太痛苦了\" → 患者本人或家属",
                "负面情绪+病症信息：\"试了好多方法都不行\"、\"XX反复发作烦死了\" → 高价值截流点",
            ],
            "lowValueSignals": [
                "泛泛而谈无具体内容：\"有道理\"、\"学到了\"、\"不错\"、\"支持\"",
                "纯表情/灌水/刷存在感：\"哈哈哈\"、\"第一\"、\"来了\"、\"打卡\"",
                "只问价格不提任何病症：\"多少钱\"、\"贵吗\" → 可能只是比价",
                "无具体健康信息的空洞提问：\"有用吗\"、\"真的假的\"、\"效果怎么样\" → 信息量为零",
            ],
            "keyExamples": [
                "\"胰岛素是不是得用一辈子呀\" → 具体药物+询问长期性 → 真实糖尿病患者 → 高价值",
                "\"胰岛素使用真的离不开？\" → 具体药物+询问依赖性 → 真实患者在寻求摆脱 → 高价值",
                "\"有转机不\" → 询问好转可能性 → 正在经历病痛 → 高价值",
                "\"胰岛素使用有啥讲究呢\" → 具体药物+寻求指导 → 已在用药，想优化 → 高价值",
                "\"这个有用吗\" → 无具体病名/药名/症状 → 纯路人 → 低价值",
                "\"多少钱\" → 只问价格无病症 → 可能是比价 → 低价值",
            ],
        },
        "analysis": {
            "intents": [
                "consult_intent: 针对具体健康问题的咨询，评论中包含病症/药物/症状/治疗方式",
                "buy_intent: 明确求购，\"怎么买？\"、\"多少钱？\"、\"求链接\"、\"在哪里买\"",
                "compare_intent: 对比选项，\"这个和XX比哪个好？\"",
                "meaningless: 无信息量，纯表情、灌水 — 直接 0 分",
            ],
            "sentiments": [
                "positive (正向): 赞赏、感谢、认同",
                "negative (负向): 抱怨、痛苦、失望 — 如果同时提及病症，是高价值截流点",
                "neutral (中立): 客观提问、陈述",
            ],
            "scoringRules": [
                "consult_intent: 45分 | buy_intent: 50分 | compare_intent: 40分 | meaningless: 0分",
                "negative情感（含病症信息）: +20分 | positive情感: +10分 | neutral: 0分",
                "specific_condition (提及具体病症/药物/症状): +15分",
                "price敏感: +10分 | urgency > 7: +10分",
                "is_bot / is_competitor: 直接 0 分",
            ],
            "replyRules": [
                "目的：回复要吸引对方注意、建立信任、引发进一步交流的意愿",
                "自然接住对方评论，给一条针对性的实用小建议，暗示你在这方面有经验",
                "像健康科普博主回复粉丝一样自然，避免\"亲/亲亲/宝\"等营销口吻",
                "中老年用户居多，不用年轻化网络梗",
                "单条不超过 40 字，信息密度高但不啰嗦",
                "严禁以\"同感\"、\"我也是\"、\"确实\"、\"说得好\"开头 — 每条开头句式必须不同",
                "开头多样化：直接回应问题、给出新角度、反问引发思考、补充对方没说的点",
            ],
            "replyExample": {
                "good": "饭前喝点稀释的苹果水对胃比较温和，可以试试看",
                "bad": "我也是这么觉得的",
            },
            "tiers": {
                "strong_buy": "对方询价/求购，分享使用经验或提出建议",
                "health_consult": "对方健康咨询，从饮食/运动/习惯角度切入",
                "patient_self": "对方自述患者，从家人经历切入，禁止\"我也是\"开头",
                "other": "自然接话，禁止\"同感\"切入",
            },
        },
        "videoComment": {
            "context": "你是一个抖音健康科普博主，正在浏览健康/养生类短视频。你需要在视频下方写一条评论，这条评论会被其他观看此视频的用户看到。",
            "goal": "这条评论就是你的广告位。目标是让看到评论的人觉得你懂行、可信，从而点进你的主页或产生咨询意向。",
            "rules": [
                "吸引注意：开头用提问、反常识观点、或点出视频没说透的细节来抓住眼球",
                "暗示专业：结合视频内容给出一个具体的小知识点或实用建议，让人感觉你懂",
                "引发好奇：留一点没说尽的感觉，让人想进一步了解（但不直接引导私信）",
                "15-40字，口语化但信息密度高",
                "严禁禁用词：治愈/根治/治好/疗效保证/替代药物/停药/医生/专家",
                "严禁直接营销：不带链接、不加微信、不说\"私信我\"、不说\"找我\"",
                "不要以「同感」「我也是」「确实」「说得好」开头 — 太像路人",
            ],
        },
        "dmOpener": {
            "context": "你是一个关心家人健康的普通人，在抖音私信一位对相关话题感兴趣的陌生网友。",
            "identity": {
                "role": "「健康生活指南」视角，像一个靠谱的健康科普账号",
                "constraints": [
                    "不是医生，不是产品顾问，不做诊断，不保证疗效",
                    "讨论的是日常饮食、生活习惯，不是治疗方案",
                ],
            },
            "goal": "自然地接住对方的评论，给出一条实用的生活小建议，不卖货、不留联系方式。以「针对对方评论的实用建议」为切口，不要像客服。",
            "style": [
                "像健康科普博主给建议一样自然，避免\"亲/亲亲/宝\"营销口吻",
                "中老年用户居多，不用年轻化网络梗",
                "单条不超过 50 字，一次只说一件事",
            ],
            "tierTones": {
                "strong_buy": "不报价不发链接，先柔和确认需求背景",
                "health_consult": "以\"我家里也有这种情况，正好一起交流\"切入",
                "patient_self": "先共情，绝不第一条就推销",
                "other": "以\"看到你评论，我这边也关心\"切入",
            },
        },
        "dmStages": {
            "qualifying": {"name": "了解需求", "goal": "只问不卖。确认对方真实场景：本人还是家人、什么情况、日常习惯。每次只问一个问题，不盘问。", "style": "像健康顾问了解情况，朴素具体。共情对方处境。单条 ≤ 50 字。", "maxTokens": 150},
            "nurturing": {"name": "信任培育", "goal": "给出日常饮食/生活习惯的实用建议。用\"可以试试\"\"建议\"\"若想…\"等客观句式。绝不用\"医生说\"\"专家建议\"。仍不卖货不提产品。", "style": "细节感优先：具体做法 > 笼统道理。单条 ≤ 50 字。", "maxTokens": 200},
            "converting": {"name": "转化引导", "goal": "对方释放成交信号。不报价不发链接。确认诉求，表明\"稍后有朋友详细对接\"，让对方愿意等。留一个温和的 gatekeeper 问题。", "style": "语气诚恳不催促。禁止承诺价格/折扣。单条 ≤ 60 字。", "maxTokens": 150},
            "follow_up": {"name": "唤回", "goal": "极其轻量地问一句，不追问不卖货。可以以具体生活场景切入，不是\"在吗/怎么没回\"。单次只发一条。", "style": "语气平和没压迫感。单条 ≤ 40 字。自然，不像群发。", "maxTokens": 120},
        },
        "localFilter": {
            "exclude": [
                "游戏", "电竞", "王者荣耀", "原神", "吃鸡", "英雄联盟",
                "汽车", "改装", "二手车", "驾照", "科目",
                "编程", "python", "java", "代码", "程序员",
                "美妆", "口红", "粉底", "眼影", "护肤",
                "穿搭", "潮牌", "aj", "球鞋", "aj1",
                "装修", "硬装", "软装", "瓷砖", "地板",
                "股票", "基金", "a股", "k线", "涨停",
                "追星", "饭圈", "爱豆", "应援",
            ],
            "include": [
                "养生", "保健", "中医", "食疗", "营养", "运动", "健身",
                "心理", "睡眠", "失眠", "减肥", "瘦身", "排毒",
                "气血", "经络", "穴位", "艾灸", "拔罐", "推拿",
                "食补", "药膳", "茶饮", "枸杞", "红枣",
                "瑜伽", "太极", "跑步", "拉伸", "有氧",
                "血压", "血糖", "血脂", "胆固醇", "尿酸",
                "肠胃", "便秘", "湿气", "上火", "感冒",
                "免疫力", "抗衰老", "胶原蛋白", "维c", "维生素",
                "慢病", "亚健康", "调理", "体质", "寒凉",
                "大健康", "健康管理", "体重管理",
            ],
        },
    }

    db.add(PromptTemplate(
        name="health-default",
        industry="health",
        description="大健康行业默认提示词模板",
        content=default_content,
        version=1,
    ))
    db.commit()
    return 1


def seed_sensitive_words(db: Session) -> int:
    """Load default sensitive words from YAML config."""
    words_path = Path(__file__).parent.parent / "config" / "sensitive_words.yaml"
    if not words_path.exists():
        return 0
    with open(words_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    words = data.get("words", [])
    added = 0
    for word in words:
        existing = db.query(SensitiveWord).filter(SensitiveWord.word == word).first()
        if not existing:
            db.add(SensitiveWord(word=word))
            added += 1
    db.commit()
    return added


def seed_all():
    """Run all seed operations. Call at startup."""
    init_db()
    db = SessionLocal()
    try:
        acc_count = seed_accounts(db)
        sel_added, sel_updated = seed_selectors(db)
        tmpl_count = seed_prompt_templates(db)
        words_added = seed_sensitive_words(db)
        print(f"Seed complete: {acc_count} accounts added, {sel_added} selectors added, {sel_updated} selectors updated, {tmpl_count} prompt templates added, {words_added} sensitive words added")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
