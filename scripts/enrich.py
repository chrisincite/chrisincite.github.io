#!/usr/bin/env python3
"""
把手機上只寫了兩行 front-matter 的筆記原稿補完。

手機上只需要寫：

    ---
    source: 20260815-japan-ai-adoption-slow
    title: 日本不是不會用 AI，是不敢犯錯
    ---

    （散文正文）

這支會去 private repo chrisincite/twitter_article 撈該篇的作者／原文網址／
發表日期／封面圖，把 front-matter 就地改寫成完整版並下載封面，
之後 build.py 就能正常建置。

- **冪等**：已經補完過（source 是 mapping 且有 url）的檔案會直接跳過。
- 在 GitHub Actions 裡跑時，需要環境變數 SOURCE_REPO_TOKEN
  （能讀 twitter_article 的 fine-grained PAT）。本機跑會自動改用 gh CLI。

用法：python3 scripts/enrich.py [檔案...]      （不給檔案就掃 notes/src/*.md）
"""

import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

SOURCE_REPO = "chrisincite/twitter_article"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "notes", "src")
IMG_DIR = os.path.join(ROOT, "notes", "img")


# ------------------------------------------------------------
# 讀 private repo：CI 用 PAT 走 API，本機用 gh CLI
# ------------------------------------------------------------
def read_source_file(path):
    token = os.environ.get("SOURCE_REPO_TOKEN")
    url = "https://api.github.com/repos/%s/contents/%s" % (SOURCE_REPO, path)

    if token:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer %s" % token,
                "Accept": "application/vnd.github+json",
                "User-Agent": "chris-os-note-builder",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError("讀不到 %s（HTTP %s）" % (path, e.code))
        return base64.b64decode(payload["content"])

    out = subprocess.run(
        ["gh", "api", "repos/%s/contents/%s" % (SOURCE_REPO, path), "--jq", ".content"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError("讀不到 %s：%s" % (path, out.stderr.strip()))
    return base64.b64decode(out.stdout)


# ------------------------------------------------------------
# 解析 twitter-article-zh 的表頭
# 已知三種格式（別再收窄這裡的容忍度）：
#   > 原文：[@handle（Name）](url)　發表於 Wed Aug 12 12:39:45 +0000 2026
#   > 原文：[www.bbc.com](url)　發表於 2026-08-12T23:00:47.427Z
#   > 原文：[note.com](url)　作者　note（ノート）　發表於 2026-08-15T00:59:24.000+09:00
# ------------------------------------------------------------
def normalize_date(raw):
    raw = (raw or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return "-".join(m.groups())
    m = re.search(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+[\d:]+\s+[+\-]\d{4}\s+(\d{4})", raw)
    if m:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        try:
            return "%s-%02d-%02d" % (m.group(3), months.index(m.group(1)) + 1, int(m.group(2)))
        except ValueError:
            return ""
    return ""


def parse_header(text):
    meta = {"title": "", "url": "", "author": "", "site": "", "published": "", "cover_rel": ""}

    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        meta["title"] = m.group(1).strip()

    m = re.search(r"^>\s*原文：(.+)$", text, re.M)
    if m:
        line = m.group(1)
        lm = re.search(r"\[([^\]]+)\]\(([^)\s]+)\)", line)
        link_text = lm.group(1).strip() if lm else ""
        if lm:
            meta["url"] = lm.group(2).strip()
        # 發表於 之後到行尾（或下一個全形空格分隔欄位）
        dm = re.search(r"發表於[\s　]*([^\s　]+(?:\s+[^\s　]+)*)", line)
        meta["published"] = normalize_date(dm.group(1) if dm else "")
        # 同一行裡的「作者　X」或「作者：X」
        am = re.search(r"作者[：:\s　]+([^\s　]+)", line)
        if am:
            meta["author"] = am.group(1).strip()

        if "x.com" in meta["url"] or "twitter.com" in meta["url"]:
            meta["site"] = "X"
            meta["author"] = meta["author"] or link_text
        else:
            dm2 = re.match(r"https?://([^/]+)", meta["url"])
            meta["site"] = (dm2.group(1) if dm2 else link_text).replace("www.", "")
            meta["author"] = meta["author"] or link_text

    # 獨立成行的「> 記者：」「> 作者：」優先（一般網頁常見）
    m = re.search(r"^>\s*(?:記者|作者)[：:]\s*(.+)$", text, re.M)
    if m:
        meta["author"] = m.group(1).strip()

    m = re.search(r"!\[[^\]]*\]\((images/[^)]+)\)", text)
    if m:
        meta["cover_rel"] = m.group(1)

    return meta


# ------------------------------------------------------------
# front-matter 就地改寫
# ------------------------------------------------------------
def split_front_matter(text):
    if not text.startswith("---"):
        raise ValueError("缺少 front-matter")
    end = text.index("\n---", 3)
    return text[3:end].strip("\n"), text[end + 4:].lstrip("\n")


def yaml_quote(v):
    v = str(v)
    return '"%s"' % v.replace('"', '\\"') if re.search(r'[:#\[\]{}"\']|^\s|\s$', v) else v


def enrich(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    raw_fm, body = split_front_matter(text)

    # 已補完過就跳過（冪等）
    if re.search(r"^source:\s*$", raw_fm, re.M) and "url:" in raw_fm:
        print("• %s（已補完，跳過）" % os.path.basename(path))
        return False

    m = re.search(r"^source:\s*(\S+)\s*$", raw_fm, re.M)
    if not m:
        print("• %s（沒有 source: <slug>，跳過）" % os.path.basename(path))
        return False
    archive_slug = m.group(1).strip().strip("\"'").strip("/")

    fields = {}
    for line in raw_fm.split("\n"):
        fm = re.match(r"^([a-z_]+):\s*(.*)$", line.strip())
        if fm and fm.group(1) != "source":
            fields[fm.group(1)] = fm.group(2).strip()

    if not fields.get("title"):
        raise ValueError("%s 缺 title" % path)

    archive = archive_slug if "/" in archive_slug else "%s/%s" % (archive_slug[:8], archive_slug)
    article = read_source_file("%s/article-zh.md" % archive).decode("utf-8")
    src = parse_header(article)

    slug = os.path.splitext(os.path.basename(path))[0]

    # 封面
    cover = ""
    if src["cover_rel"]:
        ext = os.path.splitext(src["cover_rel"])[1] or ".jpg"
        os.makedirs(IMG_DIR, exist_ok=True)
        dest = "%s-cover%s" % (slug, ext)
        try:
            with open(os.path.join(IMG_DIR, dest), "wb") as f:
                f.write(read_source_file("%s/%s" % (archive, src["cover_rel"])))
            cover = "img/%s" % dest
        except Exception as e:
            print("  ⚠ 封面下載失敗：%s" % e, file=sys.stderr)

    date = fields.get("date") or (
        "-".join(re.match(r"^(\d{4})(\d{2})(\d{2})", slug).groups())
        if re.match(r"^\d{8}", slug) else ""
    )

    lines = ["---", "slug: %s" % slug, "date: %s" % date,
             "title: %s" % yaml_quote(fields["title"])]
    if fields.get("hook"):
        lines.append("hook: %s" % yaml_quote(fields["hook"]))
    if fields.get("tags"):
        lines.append("tags: %s" % fields["tags"])
    if cover:
        lines.append("cover: %s" % cover)
        lines.append("cover_credit: 圖片取自原文")
    lines.append("source:")
    for k in ("title", "author", "site", "url", "published"):
        if src.get(k):
            lines.append("  %s: %s" % (k, yaml_quote(src[k])))
    lines.append("  archive: %s" % archive)
    lines += ["---", "", body.rstrip(), ""]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("✓ %s ← %s" % (os.path.basename(path), archive))
    return True


def main():
    targets = sys.argv[1:]
    if not targets:
        if not os.path.isdir(SRC_DIR):
            print("找不到 %s" % SRC_DIR, file=sys.stderr)
            return 1
        targets = [os.path.join(SRC_DIR, f)
                   for f in sorted(os.listdir(SRC_DIR)) if f.endswith(".md")]

    changed = 0
    for t in targets:
        try:
            if enrich(t):
                changed += 1
        except Exception as e:
            print("✗ %s：%s" % (t, e), file=sys.stderr)
            return 1
    print("補完 %d 篇" % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
