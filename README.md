# auto-meeting-minutes · 自动会议纪要整理 Skill

> 严格按「海南龙源新能源有限公司」真实周例会模板，把录音一键整理成可交付的会议纪要 .docx。

## 它能做什么

丢一段会议录音（.mp3 / .wav 等），自动完成：

1. **语音转写** —— 调用 OpenAI Whisper API（也可切本地 Whisper / Google SR 兜底）
2. **按真实模板总结** —— 100% 还原客户提供的第 25/26/27 次周例会纪要格式（标题、时间、地点、参会人员分层、议题、决议、待办）
3. **自动算第几次** —— 根据会议日期推算周例序号（基准：2026-08-17 = 第 25 次，公式 `序号 = 25 + (目标日期 − 2026-08-17) / 7`）
4. **规范命名** —— 输出文件名为 `海南龙源新能源有限公司{年份}年第{序号}次周例会会议纪要.docx`

## 安装

把本目录整体放到 WorkBuddy 的 skills 目录：

```
~/.workbuddy/skills/auto-meeting-minutes/
├── SKILL.md
├── README.md
└── scripts/
    ├── transcribe_audio.py          # 音频转写
    └── calculate_meeting_number.py  # 按日期算第几次
```

## 使用

在 WorkBuddy 里直接说：

> 把这段录音整理成海南龙源第 XX 次周例会纪要

Skill 会按模板输出，并可导出 .docx。

## 模板还原要点（务必严格遵循）

- 标题：`{年份}年第{序号}次周例会`
- 会议时间：`YYYY年MM月DD日（周X）上午/下午HH:MM`
- 参会人员分三层：公司领导 / 各部门负责人 / 列席人员
- 正文按「议题 → 发言要点 → 决议 → 待办（含责任人/时限）」结构
- 落款与原始模板一致（单位、日期格式）

## 依赖

- Python 3.10+
- `openai`（`pip install openai`，用于 Whisper API）
- 可选：`whisper`、`SpeechRecognition`
