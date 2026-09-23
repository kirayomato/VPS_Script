#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_old_dir.py - 清理目标目录下创建时间早于指定天数的文件。

视频保护：
  后缀为视频时，用 ffprobe 探测分辨率和码率；
  若为竖屏(高>宽) 且 码率 < 3000 kbps，则跳过不删除。

用法示例:
  python3 clean_old_dir.py -d /data/logs -n 30
  python3 clean_old_dir.py -d /data/logs -n 30 -e log,tmp
  python3 clean_old_dir.py -d /data/logs -n 30 -x
  python3 clean_old_dir.py -d /data/logs -n 30 -x -y
  python3 clean_old_dir.py -d /data/logs -n 30 -x -e .bak,.gz
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime

# ---------- 常量 ----------

DANGEROUS_PATHS = {
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/home",
    "/lib",
    "/lib64",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/srv",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
}

# 识别为视频的扩展名
VIDEO_EXTS = {
    "mp4",
    "mkv",
    "avi",
    "mov",
    "flv",
    "wmv",
    "webm",
    "m4v",
    "ts",
    "mpg",
    "mpeg",
    "3gp",
    "3g2",
    "m2ts",
    "vob",
    "rmvb",
    "rm",
    "asf",
    "ogv",
    "mts",
    "f4v",
}

# 竖屏低码率保护阈值（单位 bps）
BITRATE_THRESHOLD_BPS = 3000 * 1000  # 3000 kbps

# ffprobe 超时（秒）
FFPROBE_TIMEOUT = 30


# ---------- 通用工具 ----------


def human_size(n):
    """仿 numfmt --to=iec，输出人类可读大小。"""
    n = int(n)
    if n < 1024:
        return f"{n}B"
    units = ["K", "M", "G", "T", "P", "E", "Z", "Y"]
    v = float(n)
    for u in units:
        v /= 1024.0
        if abs(v) < 1024.0:
            return f"{v:.1f}{u}"
    return f"{v:.1f}Y"


def human_bitrate(bps):
    if bps is None:
        return "未知"
    return f"{bps / 1000:.0f} kbps"


def nonneg_int(s):
    try:
        v = int(s)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"必须是大于等于 0 的整数，收到：{s}")
    if v < 0:
        raise argparse.ArgumentTypeError(f"必须是大于等于 0 的整数，收到：{s}")
    return v


def normalize_exts(raw_list):
    """把 ['log,tmp', '.bak'] 归一化成 ['log', 'tmp', 'bak']。"""
    result, seen = [], set()
    for item in raw_list:
        for part in item.split(","):
            part = part.strip().lstrip(".").lower()
            if part and part not in seen:
                seen.add(part)
                result.append(part)
    return result


def is_excluded(name, exts):
    """按后缀匹配扩展名，不区分大小写。"""
    if not exts:
        return False
    lname = name.lower()
    return any(lname.endswith("." + e) for e in exts)


def get_ext(name):
    """取最后一个点之后的扩展名(小写)，无扩展名返回空串。"""
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[1].lower()


def is_video_file(name):
    return get_ext(name) in VIDEO_EXTS


# ---------- ffprobe ----------


def ffprobe_video(path):
    """用 ffprobe 探测视频信息。

    返回 (width, height, bit_rate_bps) 或 None（探测失败）。
    width/height/bit_rate 任一可能为 None。
    """
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,bit_rate:format=bit_rate",
                "-of",
                "json",
                "--",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=FFPROBE_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    if proc.returncode != 0:
        return None

    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, TypeError):
        return None

    streams = data.get("streams") or []
    if not streams:
        return None

    s = streams[0]
    w = s.get("width")
    h = s.get("height")
    br = s.get("bit_rate")
    if br is None:
        # 回退到容器整体码率
        br = (data.get("format") or {}).get("bit_rate")

    try:
        br = int(br) if br is not None else None
    except (TypeError, ValueError):
        br = None

    return w, h, br


def is_portrait_low_bitrate(width, height, bitrate):
    """竖屏(高>宽) 且 码率低于阈值 -> True。"""
    if not width or not height:
        return False
    if height <= width:
        return False
    if bitrate is None:
        return False
    return bitrate < BITRATE_THRESHOLD_BPS


# ---------- 文件系统遍历（仿 find -xdev） ----------


def walk_same_fs(root, topdown=True):
    """仿 find -xdev：不跨越文件系统边界，不跟随符号链接。"""
    try:
        root_dev = os.stat(root).st_dev
    except OSError:
        return

    for dirpath, dirnames, filenames in os.walk(
        root, topdown=topdown, followlinks=False
    ):
        keep = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            try:
                st = os.stat(full, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                continue
            if st.st_dev == root_dev:
                keep.append(d)
        dirnames[:] = keep
        yield dirpath, dirnames, filenames


def iter_regular_files(root):
    """产出 (path, stat_result)，仅普通文件，且不跨越文件系统。"""
    for dirpath, dirnames, filenames in walk_same_fs(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                st = os.stat(full, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                yield full, st


def dir_size(root):
    return sum(st.st_size for _, st in iter_regular_files(root))


def iter_empty_dirs(root):
    for dirpath, dirnames, filenames in walk_same_fs(root, topdown=False):
        if dirpath == root:
            continue
        try:
            if not os.listdir(dirpath):
                yield dirpath
        except OSError:
            pass


def remove_empty_dirs(root):
    count = 0
    for dirpath, dirnames, filenames in walk_same_fs(root, topdown=False):
        if dirpath == root:
            continue
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
                count += 1
        except OSError:
            pass
    return count


# ---------- 日志 ----------


class Logger:
    def __init__(self, log_path, real_run):
        self.real_run = real_run
        self.fh = open(log_path, "a", encoding="utf-8") if real_run else None

    def __call__(self, msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line)
        if self.fh is not None:
            self.fh.write(line + "\n")
            self.fh.flush()

    def close(self):
        if self.fh is not None:
            try:
                self.fh.close()
            finally:
                self.fh = None


# ---------- 参数解析 ----------


def parse_args():
    p = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description="清理目标目录下创建时间早于指定天数的文件。"
        "视频(竖屏且码率<3000kbps)会被保护不删。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # dry-run 预览: 控制台输出, 不写日志
  %(prog)s -d /data/logs -n 30

  # 排除 .log 和 .tmp 后预览
  %(prog)s -d /data/logs -n 30 -e log,tmp

  # 真实执行: 屏幕 + 追加写入日志
  %(prog)s -d /data/logs -n 30 -x
  %(prog)s -d /data/logs -n 30 -x -y   # 免确认

  # 真实执行并排除 .bak/.gz
  %(prog)s -d /data/logs -n 30 -x -e .bak,.gz
""",
    )
    p.add_argument(
        "-d",
        dest="target_dir",
        default="/home/ubuntu/brec/27628019-雨纪_Ameki/",
        metavar="DIR",
        help="目标目录 (必填)",
    )
    p.add_argument(
        "-n",
        dest="days",
        type=nonneg_int,
        default=30,
        metavar="N",
        help="天数, 默认 30, 删除创建时间早于此天数的文件",
    )
    p.add_argument(
        "-l",
        dest="log_file",
        default="clean_old_dir.log",
        metavar="FILE",
        help="日志文件路径, 默认 clean_old_dir.log",
    )
    p.add_argument(
        "-e",
        dest="exclude_exts",
        action="append",
        default=["xml", "json"],
        metavar="EXT",
        help="排除扩展名, 可重复或逗号分隔; 不区分大小写, 可带点",
    )
    p.add_argument(
        "-x",
        dest="real_run",
        action="store_true",
        help="真实执行删除; 不加 -x 为 dry-run 预览模式",
    )
    p.add_argument("-y", dest="yes", action="store_true", help="真实执行时跳过二次确认")
    p.add_argument(
        "--no-video-protect",
        dest="video_protect",
        action="store_false",
        default=True,
        help="关闭视频保护(默认开启: 竖屏且码率<3000kbps 不删)",
    )
    return p.parse_args()


# ---------- 主流程 ----------


def main():
    args = parse_args()

    target_dir = args.target_dir
    days = args.days
    real_run = args.real_run
    yes = args.yes
    exclude_exts = normalize_exts(args.exclude_exts)
    video_protect = args.video_protect

    # 参数校验
    if not os.path.isdir(target_dir):
        print(f"错误：目录不存在 {target_dir}", file=sys.stderr)
        sys.exit(1)

    # 解析为绝对路径（等价 pwd -P）
    target_dir = os.path.realpath(target_dir)

    # 危险路径保护
    if target_dir in DANGEROUS_PATHS:
        print(f"错误：拒绝在危险目录上执行：{target_dir}", file=sys.stderr)
        sys.exit(1)

    # 日志文件准备（仅真实模式）
    log_file = args.log_file
    if real_run:
        log_dir = os.path.dirname(os.path.abspath(log_file)) or "."
        if not os.path.isdir(log_dir):
            print(f"错误：日志目录不存在 {log_dir}", file=sys.stderr)
            sys.exit(1)
        if not os.access(log_dir, os.W_OK):
            print(f"错误：日志目录不可写 {log_dir}", file=sys.stderr)
            sys.exit(1)
        log_file_abs = os.path.join(
            os.path.realpath(log_dir), os.path.basename(log_file)
        )
        # 防止日志文件位于目标目录内被误删
        if log_file_abs == target_dir or log_file_abs.startswith(target_dir + os.sep):
            print(
                f"错误：日志文件不能位于目标目录内部：{log_file_abs}", file=sys.stderr
            )
            sys.exit(1)
        log_file = log_file_abs

    logger = Logger(log_file, real_run)
    try:
        logger("==================== 开始清理任务 ====================")
        logger(f"目标目录: {target_dir}")
        logger(
            f"过滤条件：文件创建时间早于 {days} 天（不支持创建时间时回退为修改时间）"
        )
        if exclude_exts:
            logger(f"排除扩展名: {', '.join(exclude_exts)}（不区分大小写）")
        else:
            logger("排除扩展名: 无")

        # 视频保护状态
        if video_protect:
            if shutil.which("ffprobe"):
                logger(
                    f"视频保护: 开启（竖屏且码率 < {BITRATE_THRESHOLD_BPS // 1000} kbps 不删除）"
                )
            else:
                logger("视频保护: 已请求，但未找到 ffprobe，视频将按普通文件处理！")
                logger(
                    "          请安装 ffmpeg/ffprobe 后重试，例如: apt install ffmpeg"
                )
        else:
            logger("视频保护: 已关闭（--no-video-protect）")

        if not real_run:
            logger(
                "模式：DRY-RUN 预览模式，不执行删除，【不写入日志文件】；大小为模拟预估值"
            )
        else:
            logger(f"模式：真实删除模式，修改磁盘数据，日志追加至 {log_file}")

        before_size = dir_size(target_dir)
        logger(f"清理前目录真实总大小: {human_size(before_size)}")

        now = time.time()
        cutoff = now - days * 86400

        # 查找待删除文件
        files_to_delete = []  # [(path, size)]
        protected_videos = []  # [(path, w, h, bitrate)]
        ffprobe_fail = 0

        for path, st in iter_regular_files(target_dir):
            name = os.path.basename(path)

            # 扩展名排除
            if is_excluded(name, exclude_exts):
                continue

            # 时间过滤
            bt = getattr(st, "st_birthtime", 0)
            ts = bt if (bt and bt > 0) else st.st_mtime
            if ts >= cutoff:
                continue

            # 视频保护：竖屏且低码率 -> 跳过
            if video_protect and is_video_file(name):
                info = ffprobe_video(path)
                if info is None:
                    ffprobe_fail += 1
                else:
                    w, h, br = info
                    if is_portrait_low_bitrate(w, h, br):
                        protected_videos.append((path, w, h, br))
                        continue

            files_to_delete.append((path, st.st_size))

        file_count = len(files_to_delete)
        del_size = sum(sz for _, sz in files_to_delete)

        logger(f"待删除旧文件数量：{file_count} 个")
        logger(f"待删除文件总大小：{human_size(del_size)}")

        if protected_videos:
            logger(f"受保护视频(竖屏且低码率)：{len(protected_videos)} 个")
            for p, w, h, br in protected_videos:
                logger(f" [保护] {p}  分辨率={w}x{h}  码率={human_bitrate(br)}")
        if ffprobe_fail:
            logger(f"提示：{ffprobe_fail} 个视频 ffprobe 探测失败，已按普通文件处理")

        if not real_run:
            # ---------- DRY-RUN ----------
            logger("----------【预览】待删除文件列表----------")
            for f, _ in files_to_delete:
                logger(f" {f}")

            logger("----------【预览】待删除空目录列表----------")
            for d in iter_empty_dirs(target_dir):
                logger(f"空目录：{d}")

            simulate_after = max(0, before_size - del_size)
            logger("==================== DRY-RUN 模拟统计 ====================")
            logger(f"清理前真实大小: {human_size(before_size)}")
            logger(f"预估释放空间:   {human_size(del_size)}")
            logger(f"预估清理后大小: {human_size(simulate_after)}")
            logger("注意：模拟值未扣除空目录元数据，仅供参考")
        else:
            # ---------- 真实执行 ----------
            if not yes:
                print()
                print(f"即将真实删除 {file_count} 个文件，目录：{target_dir}")
                if protected_videos:
                    print(
                        f"（其中 {len(protected_videos)} 个视频因竖屏且低码率被保护）"
                    )
                try:
                    ans = input("确认执行？输入 yes 继续：")
                except EOFError:
                    ans = ""
                if ans != "yes":
                    logger("用户取消，未执行删除。")
                    logger("======================================================")
                    logger("")
                    return

            logger("开始删除旧文件...")
            for f, _ in files_to_delete:
                try:
                    os.unlink(f)
                except OSError as e:
                    logger(f"删除失败: {f} ({e})")

            logger("开始删除空目录...")
            removed = remove_empty_dirs(target_dir)
            logger(f"已删除空目录数：{removed}")

            after_size = dir_size(target_dir)
            real_release = max(0, before_size - after_size)
            logger("==================== 真实执行统计 ====================")
            logger(f"清理前真实大小: {human_size(before_size)}")
            logger(f"清理后真实大小: {human_size(after_size)}")
            logger(f"实际释放空间:   {human_size(real_release)}")

        logger("======================================================")
        logger("")
    finally:
        logger.close()


if __name__ == "__main__":
    main()
