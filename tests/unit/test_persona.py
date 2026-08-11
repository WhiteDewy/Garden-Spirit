"""10 星灵人格回归测试（self_map_design §1.1）——宝石人格 → 10 行星灵。

验证：
- PersonaType 恰好是 10 颗行星（太阳…冥王星），值与 Planet 值一致
- 每颗星的疗愈名 = §1.1 签名表（与 mailbox/signature.HEALING_NAMES 单一来源一致）
- 默认人格 = 月亮（产品 mascot）；未知/旧宝石人格名 → 月亮兜底
- 每颗星人格声音不同（system prompt 各异）
"""

from shared.enums import PersonaType, Planet

from application.conversation.persona import all_personas, get_persona


def test_persona_type_is_ten_classical_planets():
    """PersonaType 恰好是 10 颗古典行星，值与 Planet 对齐（供信落款 sender 复用）。"""
    planets = {Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
               Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO}
    assert len(list(PersonaType)) == 10
    assert {Planet(m.value) for m in PersonaType} == planets


def test_healing_names_match_signature_table():
    """§1.1 签名表：每颗星疗愈名 = mailbox/signature.HEALING_NAMES（单一来源不漂移）。"""
    from application.mailbox.signature import HEALING_NAMES

    for persona in PersonaType:
        assert get_persona(persona).healing_name == HEALING_NAMES[Planet(persona.value)]
    assert get_persona(PersonaType.MOON).healing_name == "想被抱抱的我"
    assert get_persona(PersonaType.SUN).healing_name == "想被看见的我"


def test_default_persona_is_moon():
    """默认人格 = 月亮（产品 mascot，与每日来信默认 sender moon / 聊天占位 🌙 对齐）。"""
    from foundation.config import AppConfig

    assert AppConfig().default_persona == PersonaType.MOON
    # 未知/旧宝石人格名（回归前值）→ 兜底月亮，不炸
    assert get_persona("rose_quartz").key == PersonaType.MOON
    assert get_persona("zircon").key == PersonaType.MOON
    assert get_persona("nonsense").key == PersonaType.MOON


def test_all_personas_have_distinct_voices():
    """每颗星人格声音不同（system prompt 各异）——人格是"谁在回应"，不是装饰。"""
    prompts = [p.system_prompt() for p in all_personas()]
    assert len(prompts) == 10
    assert len(set(prompts)) == 10
    # 人格名 = 行星中文名
    names = [p.name for p in all_personas()]
    assert "太阳" in names and "月亮" in names and "海王星" in names


def test_persona_system_prompt_mentions_healing_name():
    """人格档案能把疗愈名挂在口头（想被看见的我…）——签名落在声音里。"""
    prompt = get_persona(PersonaType.SUN).system_prompt()
    assert "太阳" in prompt and "想被看见" in prompt
