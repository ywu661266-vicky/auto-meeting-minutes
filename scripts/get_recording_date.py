#!/usr/bin/env python3
"""
从音频文件自动读取“会议/录制日期”，全程无需客户手工提供。

读取优先级：
  1. ID3v2 录制时间帧：TDRC（v2.4 录制时间）/ TDOR（原始发行日期）/
     TORY（原始发行年份）/ TYER（年份）/ TDAT（日期）。优先 TDRC。
  2. 文件系统的修改时间（mtime）作为兜底。
     —— 多数手机录音/微信转发文件，落盘时间≈录制时间；若文件被长时间
        存储后才拷贝，则该时间为拷贝时间，属近似，skill 会标注来源。

输出（main）：
  READ_DATE=<YYYY-MM-DD> SOURCE=<id3|filesystem>
  MONDAY=<YYYY-MM-DD>        # 周例会按周一对齐后的日期

也可作为模块调用：
  from get_recording_date import get_recording_date, snap_to_monday
  d, src = get_recording_date(path)        # d: datetime.date, src: str
  mon   = snap_to_monday(d)                # 周一
"""
import os
import re
import struct
import sys
from datetime import datetime, timedelta

# 日期相关帧（按优先级）
DATE_FRAMES = ["TDRC", "TDOR", "TORY", "TYER", "TDAT"]


def _extract_date(text):
    """从 ID3 文本帧内容里尽量解析出 date。"""
    text = (text or "").strip().strip("\x00")
    if not text:
        return None
    # 完整日期 2026-09-07 / 2026/09/07 / 20260907
    m = re.search(r"(20\d{2})[-/]?(\d{1,2})[-/]?(\d{1,2})", text)
    if m:
        y, mo, da = m.groups()
        try:
            return datetime(int(y), int(mo), int(da)).date()
        except ValueError:
            pass
    # 仅年份
    m = re.search(r"(20\d{2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), 1, 1).date()
        except ValueError:
            pass
    return None


def _parse_id3v2_date(path):
    """解析 ID3v2 文本帧寻找日期；找不到返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(10)
            if head[:3] != b"ID3":
                return None
            # syncsafe 整数解码
            def ss(b):
                return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]
            size = ss(head[6:10])
            f.seek(0)
            tag = f.read(size + 10)
    except Exception:
        return None

    pos = 10
    while pos + 10 <= len(tag):
        fid = tag[pos:pos + 4]
        if fid == b"\x00\x00\x00\x00":
            break
        try:
            flen = struct.unpack(">I", tag[pos + 4:pos + 8])[0]
        except Exception:
            break
        flags = tag[pos + 8:pos + 10]
        body = tag[pos + 10:pos + 10 + flen]
        fname = fid.decode("latin-1", "ignore")
        if fname in DATE_FRAMES and flen > 1:
            # 首字节为编码标识
            text = body[1:].decode("utf-8", "replace")
            d = _extract_date(text)
            if d:
                return d
        pos += 10 + flen
    return None


def get_recording_date(path):
    """返回 (date, source)。source ∈ {'id3','filesystem'}。"""
    d = _parse_id3v2_date(path)
    if d:
        return d, "id3"
    mtime = datetime.fromtimestamp(os.path.getmtime(path)).date()
    return mtime, "filesystem"


def snap_to_monday(d):
    """周例会默认周一召开，把任意日期对齐到所在周的周一。"""
    return d - timedelta(days=d.weekday())


def main():
    if len(sys.argv) < 2:
        print("用法：python get_recording_date.py <音频文件>")
        sys.exit(1)
    d, src = get_recording_date(sys.argv[1])
    mon = snap_to_monday(d)
    print(f"READ_DATE={d.isoformat()} SOURCE={src}")
    print(f"MONDAY={mon.isoformat()}")


if __name__ == "__main__":
    main()
