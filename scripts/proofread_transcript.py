#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto-meeting-minutes · 二次校对模块（纯标准库，无外部依赖）

职责：把 Vosk 等离线 ASR 的"原始转写稿"做一轮自动校对，
把"无标点 / 大量重复字 / 杂乱碎片"整理成可入纪要的、带基本标点与段落结构的文本。

说明：
- 本模块是"确定性规则校对"，不依赖任何大模型 / 外网 / Key。
- 它能在没有大模型的环境下，把小模型输出整理到"可读、结构化"水平；
  若转写本身准确率太低（专有名词错认），仍需人工最终核对——模块会明确标注置信度。
- 大模型 vosk-model-cn-0.22 自带标点，本模块对其仅做轻量归一化。

对外接口：
  proofread(raw_text, with_punct=False) -> dict
    返回 {
      "clean": 清洗后的纯文本(去重复字/去噪),
      "paragraphs": [分段后的句子列表],
      "sections": { "部门汇报":[...], "领导强调":[...], "其他":[...] },
      "speakers": [检测到的可能发言人称呼],
      "confidence": "high" | "medium" | "low",
      "note": 给人工核对的提示
    }
"""
import re

# ---------- 1. 清洗 ASR 噪声 ----------
_FILLER = ["呃", "嗯", "啊啊", "那个", "就是说", "的话", "对吧", "是不是", "然后呢"]
# 重复字修复：连续 3 个及以上相同汉字 -> 保留 1 个（ASR 卡顿产物）
_DUP_CJK = re.compile(r"([\u4e00-\u9fff])\1{2,}")
# 多余的空格
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_LEADING_SPACE = re.compile(r"(?<=\n)[ \t]+")
# 零散拉丁/数字噪声（长度 1-2 且夹在中文中间的无意义字符）
_STRAY_LATIN = re.compile(r"(?<=[\u4e00-\u9fff])[a-zA-Z]{1,2}(?=[\u4e00-\u9fff])")

# ---------- 2. 句子切分线索 ----------
# 强边界词：出现即视作一句结束/新句开始
_STRONG_CUE = ["然后", "所以", "但是", "不过", "另外", "此外", "首先", "其次", "再次",
               "最后", "第一", "第二", "第三", "第四", "接下来", "下面", "关于", "针对",
               "会议", "今天", "本周", "这个", "那个", "我们", "大家", "我这边", "这边"]
# 发言人称呼模式（用于分段）
_SPEAKER = re.compile(r"(?:([刘王张李陈赵周吴郑冯杨黄何高孙马朱胡郭何][总工经理董事长书记部长院长局长])|"
                      r"([A-Za-z\u4e00-\u9fff]{1,4}[:：]))")

# 领导强调类关键词
_LEADER_KW = ["强调", "要求", "部署", "指示", "指出", "希望", "务必", "一定要", "抓紧", "落实", "统筹"]
# 部门汇报类关键词
_DEPT_KW = ["汇报", "总结", "计划", "进度", "上周", "本周", "完成", "推进", "开展", "情况"]


def clean_asr(text: str) -> str:
    if not text:
        return ""
    t = text
    # 去重复汉字
    t = _DUP_CJK.sub(r"\1", t)
    # 去零散拉丁噪声
    t = _STRAY_LATIN.sub("", t)
    # 去多余空格
    t = _MULTI_SPACE.sub(" ", t)
    t = _LEADING_SPACE.sub("", t)
    # 去首尾空格
    t = t.strip()
    return t


def _has_punct(s: str) -> bool:
    return any(p in s for p in "。！？.!?")


def segment_sentences(clean: str):
    """把清洗后的文本切成句子列表（带基本标点）。"""
    if not clean:
        return []
    # 若原稿已带标点（大模型），按标点分句即可
    if _has_punct(clean):
        parts = re.split(r"(?<=[。！？.!?])", clean)
        return [p.strip() for p in parts if p.strip()]

    # 小模型：无标点，按长度 + 线索词切分
    buf = ""
    out = []
    i = 0
    n = len(clean)
    while i < n:
        ch = clean[i]
        buf += ch
        # 触发强边界：当前缓冲中含未处理过的强线索词且长度>12
        if len(buf) >= 14:
            hit = any(cue in buf for cue in _STRONG_CUE)
            if hit or len(buf) >= 42:
                # 在最后一个强线索词之前断开
                cut = -1
                for cue in _STRONG_CUE:
                    pos = buf.rfind(cue)
                    if pos > 6:
                        cut = pos
                        break
                if cut > 0:
                    out.append(buf[:cut].strip())
                    buf = buf[cut:]
                else:
                    out.append(buf.strip())
                    buf = ""
        i += 1
    if buf.strip():
        out.append(buf.strip())
    # 补标点 + 首字大写（中文无需大写，仅加句号）
    sentences = []
    for s in out:
        s = s.strip()
        if not s:
            continue
        if not s[-1] in "。！？.!?，,":
            s += "。"
        sentences.append(s)
    return sentences


def detect_speakers(sentences):
    sp = set()
    for s in sentences:
        for m in _SPEAKER.finditer(s):
            name = (m.group(1) or "").strip()
            if name:
                sp.add(name)
    return sorted(sp)


def structure(sentences):
    """把句子归入 部门汇报 / 领导强调 / 其他。"""
    sec = {"部门汇报": [], "领导强调": [], "其他": []}
    for s in sentences:
        if any(k in s for k in _LEADER_KW):
            sec["领导强调"].append(s)
        elif any(k in s for k in _DEPT_KW):
            sec["部门汇报"].append(s)
        else:
            sec["其他"].append(s)
    # 避免某类为空时结构塌陷
    if not sec["部门汇报"] and not sec["领导强调"]:
        sec["其他"] = sentences
    return sec


def proofread(raw_text: str, with_punct: bool = False) -> dict:
    clean = clean_asr(raw_text)
    sentences = segment_sentences(clean)
    speakers = detect_speakers(sentences)
    sec = structure(sentences)

    # 置信度：重复字密度、句子数、是否有人称线索；小模型（无标点）上限降级
    dup_density = (len(raw_text) - len(clean)) / max(1, len(raw_text))
    if with_punct and len(sentences) >= 6 and dup_density < 0.05:
        confidence = "high"
        note = "大模型转写带标点且较连贯，可直接作为纪要初稿，建议人工核对专有名词与人名。"
    elif len(sentences) >= 3:
        cap = "medium" if with_punct else "low"
        confidence = cap
        if cap == "low":
            note = "检测到为小模型（无标点）原始转写，准确率有限；已做二次校对分句，但关键数据/人名/议题需人工核对，"
            note += "建议配置大模型 vosk-model-cn-0.22（skill 首次运行可自动下载）或 OpenAI Whisper API 后重跑以提升质量。"
        else:
            note = "已做二次校对并分句，但原始转写准确率有限，关键数据/人名/议题需人工核对后定稿。"
    else:
        confidence = "low"
        note = "原始转写质量过低，仅作占位参考；建议更换大模型 Vosk / OpenAI Whisper API 后重跑。"

    return {
        "clean": clean,
        "paragraphs": sentences,
        "sections": sec,
        "speakers": speakers,
        "confidence": confidence,
        "note": note,
    }


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src and __import__("os").path.exists(src):
        txt = open(src, encoding="utf-8").read()
    else:
        txt = sys.stdin.read()
    r = proofread(txt)
    print(f"[置信度] {r['confidence']}  | 句子数={len(r['paragraphs'])} 发言人={r['speakers']}")
    print(f"[提示] {r['note']}")
    print("---- 二次校对后正文 ----")
    for s in r["paragraphs"]:
        print(s)
