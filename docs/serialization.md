# 计算层出口（Serialization）规范

> 状态：v1 技术规范（2026-08-04）
> 定位：agent 后续接入星灵 app——**所有计算层面都要有出口**，计算结果必须可序列化导出。

---

## 1. 原则

**每个计算输出模型都有 `to_dict()`，返回 JSON 友好 dict**（无枚举对象、无 datetime 对象、无复杂嵌套类）：

- `enum` → `.value`（字符串）
- `datetime` → `.isoformat()`（字符串）
- `tuple` → `list`
- 嵌套模型 → 递归 `to_dict()`
- 保证 `json.dumps(d, ensure_ascii=False)` 直接可序列化

## 2. 已覆盖的出口

| 层 | 模型 | to_dict |
|----|------|---------|
| 解释引擎 | `SignificationItem` | house/word/polarity/strength/resonance/evidence/gated |
| 解释引擎 | `HouseSynapsis` | hub_planet/houses/manifestation/description |
| 解释引擎 | `ConnectionFact` | subject/target/conn_type/strength/detail |
| 解释引擎 | `AfflictionReading` | other/aspect_type/received/target_kind/label/text |
| 解释引擎 | `NatalReading` | synapsis/domains（跨8域） |
| 推运·法达 | `FirdariaPeriod` | major/sub lord + 区间 |
| 推运·法达 | `TimeLordCharacter` | nature/tone/domains/behavior/effort/afflictions/evidence |
| 推运·法达 | `FirdariaReading` | period/major/sub/characters |
| 推运·月返 | `LunarReturn` | moment/生效区间/上升/月亮落宫/宫位群星 |
| 证据卡 | `EvidenceCard` | card_id/source_type/skeleton/resonance/action/evidence/polarity/from_house/to_house/lord |
| LLM 转述 | `build_prompt` | system（人格+方法论+铁律）+ user（结论+证据卡+本命） |

## 3. 标准

- 模型 dataclass 内直接定义 `to_dict(self) -> dict`
- 复合模型调用子模型的 `to_dict()`
- 新增计算模型时必须实现 `to_dict()`（code review 检查点）
- 出口字段命名与领域一致（moon_house / sub_lord / target_kind…）

## 4. 消费方式（星灵 app）

app 调用计算层 → 得到 dict → `json.dumps` → 前端渲染。
例：
```json
{
  "type": "lunar_return",
  "moment": "2026-07-11T00:25:53+00:00",
  "moon_house": 10,
  "houses": {"10": ["moon", "mars", "uranus"], ...}
}
```
