from pathlib import Path

base = Path(r"C:/Users/PC/Desktop/red/Garden-Spirit/frontend/prototype_home_living_astro_v6.html")
out = Path(r"C:/Users/PC/Desktop/red/Garden-Spirit/frontend/prototype_home_living_astro_v6_1.html")
s = base.read_text(encoding="utf-8")

s = s.replace("星灵花园 · Living Astro Companion V6</title>", "星灵花园 · Living Astro Companion V6.1</title>")
s = s.replace("星灵花园 · V6 Demo", "星灵花园 · V6.1 Demo")
s = s.replace(
    "V6 调整点:\n\t   - 星灵更接近 Tolan 的低复杂度生命体：有表情、身体、触角、手臂、动作反馈\n\t   - 星灵可切换：靠近倾听 / 回收到星巢 / 日常呼吸\n\t   - 首页按时间相位换色：清晨 / 中午 / 黄昏 / 夜晚\n\t   - 保留后端能力映射：今日推荐星灵、今日来信、继续昨天、记忆豆荚、今日碎片、红点、trust_level",
    "V6.1 收敛点:\n\t   - 不推翻 V6：保留单个活体星灵、时间光线、私人星信\n\t   - 首页回归单列主轴：Hero / 主 CTA / 今日来信 / 轻仪表盘\n\t   - 用 Evidence Rows 替代表格；用 Bottom Sheet 承载解释层\n\t   - Minimalism 为底座，Glass/Neumorphism 只做少量质感",
)

v61_css = """
/* V6.1 convergence: single-column axis + restrained dashboard + bottom sheet */
.home.v61 .home-content{padding:88px 22px 122px;display:flex;flex-direction:column;gap:12px}.home.v61 .date-row{margin-bottom:2px}.home.v61 .time-switch{margin:0}.home.v61 .hero{grid-template-columns:1fr 132px;gap:13px;align-items:end;margin-top:3px}.home.v61 .hero h1{font-size:30px}.home.v61 .stage{height:164px;border-radius:34px}.home.v61 .interaction-bar{display:none}.home-primary{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:0}.home-primary button{border-radius:20px;padding:12px 14px;font-size:12px;border:1px solid var(--line);backdrop-filter:blur(14px)}.home-primary .main-cta{border:0;background:#17251f;color:#fff5dc;box-shadow:0 14px 34px rgba(24,37,31,.2)}.home-primary .quiet-cta{background:var(--glass);color:var(--text)}.home.v61 .wake-strip{margin:0;border-radius:21px;padding:10px 12px;background:color-mix(in srgb,var(--star),transparent 88%)}.home.v61 .letter{border-radius:28px;padding:18px 18px 17px;box-shadow:0 18px 46px rgba(36,39,31,.13)}.home.v61 .letter h2{font-size:22px;margin:10px 0}.home.v61 .letter p{font-size:13px;line-height:1.9}.dashboard-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.home.v61 .home-grid{display:grid;grid-template-columns:1fr;gap:10px;margin-top:0}.home.v61 .mini-card{min-height:auto;border-radius:23px;background:color-mix(in srgb,var(--glass),transparent 12%);padding:14px}.home.v61 .mini-card.wide{grid-column:auto}.evidence-card{border-radius:24px;border:1px solid var(--line);background:color-mix(in srgb,var(--panel),transparent 18%);backdrop-filter:blur(18px);padding:14px;box-shadow:0 14px 34px rgba(35,40,34,.08)}.evidence-row{display:grid;grid-template-columns:58px 1fr;gap:10px;align-items:center;padding:9px 0;border-top:1px solid var(--line);font-size:11px;color:var(--soft)}.evidence-row:first-of-type{border-top:0;margin-top:8px}.evidence-row span{letter-spacing:.12em;text-transform:uppercase;font-size:9px;color:color-mix(in srgb,var(--text),transparent 52%)}.evidence-row b{font-family:var(--serif);font-size:13px;color:var(--text);font-weight:650}.evidence-note{margin:8px 0 0;font-size:10px;line-height:1.65;color:var(--soft)}.home.v61 .fab{position:absolute;z-index:45;right:24px;bottom:92px;width:54px;height:54px;border:1px solid color-mix(in srgb,var(--star),transparent 52%);border-radius:21px;background:linear-gradient(145deg,color-mix(in srgb,var(--star),#fff 26%),color-mix(in srgb,var(--star),#17251f 8%));color:#17251f;box-shadow:0 18px 46px color-mix(in srgb,var(--star),transparent 68%);font-size:22px;display:grid;place-items:center}.home.v61 .explain{left:12px;right:12px;bottom:82px;border-radius:30px;padding:10px 15px 15px;border:1px solid rgba(255,255,255,.12);background:rgba(17,27,24,.92);box-shadow:0 24px 72px rgba(0,0,0,.3);line-height:1.65}.sheet-handle{width:38px;height:4px;border-radius:999px;background:rgba(255,255,255,.22);margin:0 auto 12px}.sheet-eyebrow{font-size:9px;letter-spacing:.2em;color:rgba(255,248,235,.42);margin-bottom:5px}.home.v61 .explain p{margin:7px 0 12px;color:rgba(255,248,235,.62)}.sheet-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.sheet-actions button{border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.07);border-radius:16px;padding:10px 9px;font-size:11px;color:rgba(255,248,235,.78)}.sheet-actions button:first-child{background:#f3dfaa;color:#17251f;border:0}.home.phase-morning.v61 .letter,.home.phase-noon.v61 .letter,.home.phase-dusk.v61 .letter{background:linear-gradient(180deg,rgba(252,249,240,.84),rgba(226,222,210,.74))}@media(max-width:360px){.home.v61 .hero{grid-template-columns:1fr}.home.v61 .stage{height:150px}.dashboard-pair{grid-template-columns:1fr}.home-primary{grid-template-columns:1fr}.home-primary .quiet-cta{display:none}}
"""
needle = "/* Other screens keep V5 structure */"
s = s.replace(needle, v61_css + "\n" + needle)

s = s.replace('<section id="home" class="screen home active phase-morning">', '<section id="home" class="screen home active v61 phase-morning">')
s = s.replace('<button class="icon-btn" onclick="toggleExplain()">☾</button>', '<button class="icon-btn" onclick="toggleExplain()">?</button>')

old_home = '''    <div class="wake-strip"><div><b>月亮星灵被唤醒</b><br><span>行运月亮触发安全感 / 归属主题</span></div><span>score 92</span></div>
    <article class="letter">
      <div class="letter-k">PRIVATE TRANSIT LETTER</div>
      <h2 id="letterTitle">今天，先温柔地醒来。</h2>
      <p id="letterBody">你最近一直在练习“不立刻答应”。清晨的月亮像一只小手，把那句话轻轻托起来：你可以慢一点回应，也可以先确认自己真正愿意什么。</p>
      <div class="letter-meta"><span class="meta-pill">今日来信 unread</span><span class="meta-pill">月亮 · 四宫</span><span class="meta-pill">记忆镜头：情绪日子优先</span></div>
      <div class="actions"><button class="primary" onclick="go('chat')">和月灵聊聊　→</button><button class="secondary" onclick="go('journal')">存入日记</button></div>
    </article>
    <div class="home-grid">
      <div class="mini-card"><div class="mini-label">继续昨天</div><b>“很难拒绝别人”</b><p>上一段对话还在这里，月灵可以接着陪你整理。</p></div>
      <div class="mini-card"><div class="mini-label">今日碎片</div><b>亮起 3 颗星</b><div class="fragment-row"><span class="frag">边界 +10</span><span class="frag">休息 +5</span></div></div>
      <div class="mini-card wide"><div class="mini-label">我记得你</div><div class="recall-line"><i class="pulse-star"></i><div><b>你确认过：关系里最累的是反复解释自己。</b><p>这不是标签，只是一颗被你校准过的记忆星。</p></div></div></div>
    </div>'''
new_home = '''    <div class="home-primary"><button class="main-cta" onclick="go('chat')">和今天醒来的星灵聊聊　→</button><button class="quiet-cta" onclick="toggleExplain()">为什么是它</button></div>
    <div class="wake-strip"><div><b>月亮星灵被唤醒</b><br><span>行运月亮触发安全感 / 归属主题</span></div><span>top 1</span></div>
    <article class="letter">
      <div class="letter-k">PRIVATE TRANSIT LETTER</div>
      <h2 id="letterTitle">今天，先温柔地醒来。</h2>
      <p id="letterBody">你最近一直在练习“不立刻答应”。清晨的月亮像一只小手，把那句话轻轻托起来：你可以慢一点回应，也可以先确认自己真正愿意什么。</p>
      <div class="letter-meta"><span class="meta-pill">今日来信 unread</span><span class="meta-pill">月亮 · 四宫</span><span class="meta-pill">记忆镜头：情绪日子优先</span></div>
      <div class="actions"><button class="primary" onclick="go('chat')">继续这封信　→</button><button class="secondary" onclick="go('journal')">存入日记</button></div>
    </article>
    <div class="dashboard-pair">
      <div class="mini-card"><div class="mini-label">继续昨天</div><b>“很难拒绝别人”</b><p>上一段对话还在这里，月灵可以接着陪你整理。</p></div>
      <div class="mini-card"><div class="mini-label">今日碎片</div><b>亮起 3 颗星</b><div class="fragment-row"><span class="frag">边界 +10</span><span class="frag">休息 +5</span></div></div>
    </div>
    <div class="home-grid">
      <div class="mini-card wide"><div class="mini-label">我记得你</div><div class="recall-line"><i class="pulse-star"></i><div><b>你确认过：关系里最累的是反复解释自己。</b><p>这不是标签，只是一颗被你校准过的记忆星。</p></div></div></div>
    </div>
    <div class="evidence-card"><div class="mini-label">Evidence Rows · 解释线索</div><div class="evidence-row"><span>trigger</span><b>行运月亮触发安全感主题</b></div><div class="evidence-row"><span>memory</span><b>记忆镜头优先取情绪 / 家庭 / 近期话题</b></div><div class="evidence-row"><span>growth</span><b>今日碎片只代表聊过、被照见、做过</b></div><p class="evidence-note">首页不做 Data Table 或无限信息流，只保留可解释的三行证据。</p></div>'''
if old_home not in s:
    raise RuntimeError("home block not found")
s = s.replace(old_home, new_home)

old_explain = '''  <div class="explain" id="explain"><b>为什么今天是月亮星灵？</b>来自 recommended-spirits top1：行运月亮触发本命安全感主题；recall 镜头优先取情绪、家庭、近期话题。首页会按清晨 / 中午 / 黄昏 / 夜晚切换光线，但核心只保留一个醒来的星灵和一封私人星信。</div>
</section>'''
new_explain = '''  <button class="fab" onclick="go('chat')">✦</button>
  <div class="explain" id="explain"><div class="sheet-handle"></div><div class="sheet-eyebrow">WHY TODAY</div><b>为什么今天是月亮星灵？</b><p>来自 recommended-spirits top1：行运月亮触发本命安全感主题；recall 镜头优先取情绪、家庭、近期话题。首页会按清晨 / 中午 / 黄昏 / 夜晚切换光线，但核心只保留一个醒来的星灵和一封私人星信。</p><div class="sheet-actions"><button onclick="go('chat')">和月灵聊聊</button><button onclick="setSpirit('listening')">靠近倾听</button><button onclick="setSpirit('withdraw')">回收星巢</button></div></div>
</section>'''
if old_explain not in s:
    raise RuntimeError("explain block not found")
s = s.replace(old_explain, new_explain)

s = s.replace(
    "function setPhase(phase){const data=phaseMap[phase]||phaseMap.morning;home.className='screen home active phase-'+phase;phaseTitle.textContent=data.label;heroTitle.innerHTML=data.title;heroCopy.textContent=data.copy;letterTitle.textContent=data.letter;letterBody.textContent=data.body;document.querySelectorAll('#timeSwitch button').forEach(b=>b.classList.toggle('active',b.dataset.phase===phase))}",
    "function setPhase(phase){const data=phaseMap[phase]||phaseMap.morning;home.className='screen home active v61 phase-'+phase;phaseTitle.textContent=data.label;heroTitle.innerHTML=data.title;heroCopy.textContent=data.copy;letterTitle.textContent=data.letter;letterBody.textContent=data.body;document.querySelectorAll('#timeSwitch button').forEach(b=>b.classList.toggle('active',b.dataset.phase===phase))}",
)

out.write_text(s, encoding="utf-8")
print(f"created {out}")
