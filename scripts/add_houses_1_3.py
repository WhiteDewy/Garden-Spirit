"""将用户提供的1-3宫飞星数据转换为 dispositor_rules.yaml 格式并合并。
用户原始数据格式: {house: {entries: {target: {summary, positive, negative}}}}
目标格式: house_flights: {from_house: {to_house: {title, jin, ke}}}
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 用户提供的1-3宫数据（从 TARGET_HOUSE_FLIGHT_SECTIONS 提取）
_raw = {
    1: {
        "entries": {
            1: {"summary": "追求自我实现，彰显个人意志，天生先行者", "positive": "意气风发，身心健康长寿，办事利落干脆，执行力极强，自带主角气场。", "negative": "体质偏弱，健康不佳，识人眼光差容易被人坑害，诸事不顺，做事总遇阻碍。"},
            2: {"summary": "重视资源积累，美食家", "positive": "热爱赚钱，通常会拥有不俗的赚钱能力，也热爱消费美食，用钱有方", "negative": "财富掌控能力差，多浪费金钱，黑暗料理"},
            3: {"summary": "一生奔波，竹杖芒鞋轻胜马", "positive": "热爱学习，懂得变通，学业好，童年快乐无忧，出行运势好；受到兄弟姐妹街坊邻居的喜欢，获得好处", "negative": "爱学习但学不好，给兄弟姐妹街坊邻居添麻烦，出行需要注意交通事故"},
            4: {"summary": "好宅家，注重家庭氛围和权威感", "positive": "田宅运好，家里话事人，易得祖产，有园艺、家装、收藏与收纳方面的天赋，替父亲分担责任获得好处", "negative": "无法打理好祖产和房屋土地，有原生家庭阴影，需要面对家庭和父亲相关的问题，晚年不佳"},
            5: {"summary": "老顽童，享受人间烟火气", "positive": "受人喜欢、倍儿有面子，桃花多、恋爱浪漫，投机运好、中奖，子女成器、孝顺", "negative": "经常乐极生悲，烂桃花多、纵欲过度，赌博投机破财，易给桃花、子女带来麻烦"},
            6: {"summary": "一生操劳不得闲", "positive": "敬业爱岗，工作能力强，办事细心，在职场如鱼得水，专注打磨职业技能，有一技之长", "negative": "工作地位低，因忙碌导致健康隐患多，工作运势不佳，容易碰到工作问题，给人当牛做马"},
            7: {"summary": "在意他人看法，活在别人眼中", "positive": "擅长交际与合作，得到伴侣和贵人帮助，善于处理竞争和对抗性关系，受人重视", "negative": "受困于他人评价，不会斡旋关系，容易被敌视，易受法律纠纷"},
            8: {"summary": "心思谋略多，掌控欲强", "positive": "隐藏的好胜心，决断力强，做事风格凌厉，利投资、合伙做生意，偏财好", "negative": "骗人牟利，心理阴暗，不相信他人，遭飞来横祸"},
            9: {"summary": "旅行家，追求心智成长", "positive": "乐观豁达，身带驿马，异地发展机会好，演讲天赋，领悟力好，有智慧，道德感强", "negative": "异地发展不佳，远行不顺、学业不顺"},
            10: {"summary": "功名利禄伴一生", "positive": "社会地位高，事业顺利，受尊重，事业心比较重", "negative": "事业挫折多，名声地位受损，与上位者关系不融洽"},
            11: {"summary": "为理想奋斗，精神追求高", "positive": "实现理想，人缘好，受朋友欢迎，容易结识贵人，做自媒体流量不错", "negative": "爱博出位，黑红也要红，特立独行，人际关系不好，损友多，会被朋友牵连"},
            12: {"summary": "活在精神世界里，想象力丰富", "positive": "身心灵领域有造诣，有福报好运，喜欢独处", "negative": "受小人所害，易患精神疾病，莫名遭祸，容易遇异灵事件"},
        }
    },
    2: {
        "entries": {
            1: {"summary": "财星入命，为自己买单", "positive": "有毅力有耐心，感知觉敏锐，财运好、资源多，总有机会找上门", "negative": "为财所困，对自己吝啬或乱花钱，固执己见"},
            2: {"summary": "财富嗅觉好，胃口好，财运亨通", "positive": "赚钱、理财天赋好，资源充足", "negative": "入不敷出，资源紧缺，容易蒙受损失，食欲不佳"},
            3: {"summary": "尊重知识价值，舍得花钱学习", "positive": "学习知识以此来创造财富；在交通出行和亲友关系上，花小钱办大事", "negative": "学习方面投入多收获少；交通出行和维系亲友关系上花冤枉钱"},
            4: {"summary": "财富用于家人，在住宿上舍得花钱", "positive": "愿意为家人花钱，可以获得好处，购买地产、家装，收藏可以获利", "negative": "因父亲、或购买房产、乱搞收藏破财"},
            5: {"summary": "喜好投机、花钱买开心", "positive": "投机容易获利，博彩运不错，为娱乐活动、桃花和子女花钱会很开心", "negative": "赌博、投机输钱，因桃花和子女破财"},
            6: {"summary": "相信技能价值，为服务买单", "positive": "花钱学技术，靠技术服务带来财富，同事、下属和被服务者带来财富机会，养宠物得财", "negative": "工作倒贴钱，为同事和下属破费，治病开销多"},
            7: {"summary": "赚钱要合伙，有钱愿意分享", "positive": "合伙财运好，得伴侣财，通过法律、契约获利", "negative": "因伴侣、合伙人、法律问题破财，容易被他人夺财"},
            8: {"summary": "喜赚偏财，好投资，得他人财", "positive": "做生意、投资获利，得遗产、得伴侣财，因祸得财", "negative": "投资亏损，容易负债，给人花冤枉钱"},
            9: {"summary": "乐意为旅行和进修消费", "positive": "异地得财，有海外财机，有利于经营传媒、教育行业", "negative": "在外容易破财，进修容易破费"},
            10: {"summary": "喜经营、想创业，花钱买身份", "positive": "经营事业得财，容易得上位者帮助，容易给人留下有钱人的印象", "negative": "创业容易破财，因母亲和上司破财；容易因散财名声被人记住"},
            11: {"summary": "舍得为人脉花钱", "positive": "为社交花钱，也容易通过朋友获得赚钱机会，通过掌管团体资金或资源获利，获得政府资金帮助", "negative": "因社交和团队破费，借钱给朋友收不回来，不利掌管团队资金和资源"},
            12: {"summary": "钱不重要，做慈善", "positive": "莫名得到财富、捐赠，因身心灵疗愈得财，因医疗、政策和公益项目、艺术灵感得财", "negative": "因被盗、被骗蒙受损失，因住院破费，花钱没记性所以莫名没钱"},
        }
    },
    3: {
        "entries": {
            1: {"summary": "手足缘分深，爱动脑子口才好", "positive": "机敏善变通，人生变动多、多有利；手足亲友往来多，愿意帮忙", "negative": "骑墙派，疲于接受人生无常转变；为手足亲友所累"},
            2: {"summary": "动脑子赚钱，不稳定", "positive": "靠口才和写作赚钱，出差赚钱；因手足亲友的帮助赚钱，因交通工具获财", "negative": "出行开销多，因口舌破财；兄弟亲友争财，或因手足蒙受财富损失"},
            3: {"summary": "机灵鬼", "positive": "爱出门溜达，居所周边环境好，学业好，应变能力优秀；兄弟姐妹发展好", "negative": "小时贪玩、不务正业，为人狡猾擅撒谎，居所周边环境复杂，不受待邻里待见；兄弟姐妹健康不佳，能力较差"},
            4: {"summary": "恋旧、恋家", "positive": "手足亲友与父亲关系好，兄弟姊妹在家中有话语权，容易得到手足关照，对家有温情的回忆", "negative": "手足给家中添乱，父亲因此烦恼；与手足争祖产"},
            5: {"summary": "会说漂亮话，喜欢出门玩乐", "positive": "说话讨人欢心，爱和孩子沟通玩乐，手足亲友和自己孩子关系好，和兄弟姐妹玩在一起", "negative": "和恋人、子女的沟通问题很多；手足出行不利、且烂桃花多、爱赌博"},
            6: {"summary": "动脑子的工作", "positive": "有利从事需要口才、交流、文书写作或出行相关技能的工作；手足工作比较辛苦，但能力很强", "negative": "常因工作导致精力耗尽、感到疲惫，工作中易产生口角纷争；手足身体不佳、劳碌、社会地位不高"},
            7: {"summary": "青梅竹马白月光", "positive": "伴侣为手足亲友介绍认识，或青梅竹马，在学习和出行中遇见另一半，夫妻交流轻松；手足婚姻好", "negative": "因口舌生是非，夫妻沟通不佳；和手足关系差，因为手足影响夫妻关系"},
            8: {"summary": "思维深邃，洞察人心", "positive": "想问题一针见血，清晰的洞察力带来机会，擅长媒体、口才、写作、出行相关的生意项目；手足擅长做生意，有偏财运", "negative": "自己容易遭遇严重的交通事故；手足亲友有重疾或负债，可能早逝"},
            9: {"summary": "聪明和智慧", "positive": "对哲学、宗教、异域文化有好奇心，知识积累丰富、有文化；手足定居远方、海外，带来见闻与机会", "negative": "学业不顺，三观不正，立场多变；手足与自己三观不合，文化程度一般，在外发展不顺"},
            10: {"summary": "3之8，一颗七窍玲珑心", "positive": "为人八面玲珑，口才、写作、交通物流相关有助事业发展，适合经营媒体、物流、交通行业；手足有成就，能助力自己事业", "negative": "易遭流言蜚语，因口舌是非带来事业名誉受损；手足早逝或不如意"},
            11: {"summary": "忠于理想、渴望同频沟通", "positive": "在意精神交流，因抒发意见得到欢迎和认同，适合搞自媒体，喜欢和朋友聊天，出行访友有收获；手足人缘好，与手足有思想共鸣", "negative": "容易被人误解，遭到朋友非议，容易网上被黑；手足人缘不好，易交损友"},
            12: {"summary": "高灵高敏", "positive": "学习身心灵及医学有天赋，爱幻想，灵感丰富；手足亲友与身心灵或医疗行业相关，因此得到帮助", "negative": "暗中受到非议，容易有精神方面的问题；手足亲缘浅薄，对自己不利"},
        }
    },
}

import yaml
from pathlib import Path

yaml_path = Path("domain/astrology/knowledge/dispositor_rules.yaml")
with open(yaml_path, encoding="utf-8") as f:
    data = yaml.safe_load(f)

house_flights = data.get("house_flights", {})

# 添加 1-3宫
for from_house in [1, 2, 3]:
    house_flights[from_house] = {}
    for to_house in range(1, 13):
        entry = _raw[from_house]["entries"][to_house]
        house_flights[from_house][str(to_house)] = {
            "title": entry["summary"],
            "jin": entry["positive"],
            "ke": entry["negative"],
        }

data["house_flights"] = house_flights

# 写回
with open(yaml_path, "w", encoding="utf-8") as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=200)

print("Done. Houses 1-3 added to dispositor_rules.yaml")

# 验证
with open(yaml_path, encoding="utf-8") as f:
    verify = yaml.safe_load(f)
count = sum(len(v) for v in verify["house_flights"].values())
print(f"Total entries: {count} (expect 144 = 12 houses x 12 targets)")
houses = sorted(verify["house_flights"].keys())
print(f"Houses covered: {houses}")
