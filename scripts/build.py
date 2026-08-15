#!/usr/bin/env python3
"""
CHRIS OS 讀書筆記產生器

真相源：notes/src/<slug>.md（front-matter ＋ 散文正文，可選 ## 摘要 / Summary、## 重點 / Keypoint）
產出：
  notes/<slug>.html   語意化 HTML ＋ JSON-LD ＋ OG
  notes/<slug>.md     markdown 雙生檔（agent／tinyfish 直接取用）
  notes/index.json    列表頁與機器可讀索引
  sitemap.xml         首頁 ＋ 每則筆記的 html 與 md
  llms.txt            站點概覽（llmstxt.org）
  llms-full.txt       全部筆記完整 markdown 串接
  robots.txt          AI bot 規則 ＋ Content Signals ＋ Sitemap

只用標準函式庫，任何 python3 都跑得起來。
用法：python3 scripts/build.py
"""

import html
import json
import os
import re
import subprocess
import sys

# ============================================================
# 設定
# ============================================================
# canonical 正本網址。Cloudflare 鏡像（os.housearch.net）上線後改成鏡像網址，
# 再重跑一次 build.py 即可全站更新。在鏡像就緒前指向 github.io，避免 canonical 404。
CANONICAL_BASE = "https://chrisincite.github.io"
MIRROR_BASE = "https://os.housearch.net"

# 短連結用鏡像網域：os.housearch.net/n/1 ＝ 28 字元，比 github.io 的
# /n/1.html（38 字元）短，而且是自己的網域。
# 前提是鏡像會自動更新——workflow 的最後一步會觸發 Cloudflare 部署
# （靠 CF_API_TOKEN secret），2026-08-15 實測通過。那步壞掉就要切回 CANONICAL_BASE，
# 否則新筆記的短連結會在貼出去時還是 404。
SHORT_BASE = MIRROR_BASE
SHORT_SUFFIX = ".html" if "github.io" in SHORT_BASE else ""

SITE_NAME = "CHRIS OS"
SITE_TAGLINE = "1 person ＋ AI ＝ 1 studio"
AUTHOR_NAME = "Chris Hsu"
AUTHOR_URL = "https://chrisincite.github.io"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "notes", "src")
NOTES_DIR = os.path.join(ROOT, "notes")

# 區塊標題 → 穩定錨點 id（agent 可依錨點深連結與抽取）
# 錨點名稱是對外契約，即使顯示標題改了也不要動；舊標題保留相容。
SECTION_IDS = {
    "我的想法": "my-take",
    "摘要 / Summary": "summary",
    "重點 / Keypoint": "quotes",
    # 舊標題（相容）
    "摘要/Summary": "summary",
    "重點/Keypoint": "quotes",
    "這篇在說什麼": "summary",
    "原文金句": "quotes",
}


# ============================================================
# front-matter 解析（YAML 子集，免相依）
# 支援：key: value ／ key: [a, b] ／ key: 後跟兩格縮排的子鍵
# ============================================================
def parse_front_matter(text):
    if not text.startswith("---"):
        raise ValueError("缺少 front-matter（檔案必須以 --- 開頭）")
    end = text.index("\n---", 3)
    raw = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")

    data, current_key = {}, None
    for line in raw.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line.startswith("  ")
        key, _, value = line.strip().partition(":")
        key, value = key.strip(), value.strip()

        if indented and current_key:
            data.setdefault(current_key, {})
            if isinstance(data[current_key], dict):
                data[current_key][key] = _scalar(value)
            continue

        if value == "":
            data[key] = {}
            current_key = key
        else:
            data[key] = _scalar(value)
            current_key = None
    return data, body


def _scalar(v):
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("\"'") for x in inner.split(",")]
    return v.strip().strip("\"'")


# ============================================================
# 極簡 markdown 渲染（段落／有序清單／無序清單／引言／行內）
# ============================================================
def inline(text):
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        r'<a href="\2" rel="noopener">\1</a>',
        out,
    )
    return out


def render_blocks(body):
    """把一個區塊的 markdown 內文轉成 HTML。"""
    lines = body.split("\n")
    out, buf, mode = [], [], None

    def flush():
        nonlocal buf, mode
        if not buf:
            mode = None
            return
        if mode == "ol":
            items = "".join("<li>%s</li>" % inline(x) for x in buf)
            out.append("<ol>%s</ol>" % items)
        elif mode == "ul":
            items = "".join("<li>%s</li>" % inline(x) for x in buf)
            out.append("<ul>%s</ul>" % items)
        elif mode == "quote":
            out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(buf).strip()))
        else:
            out.append("<p>%s</p>" % inline(" ".join(buf).strip()))
        buf, mode = [], None

    # pending_blank 記住「剛剛有空行」，用來區分：
    #   清單條目之間的空行 → 同一個清單繼續（loose list）
    #   引言之間的空行     → 切成兩個獨立 blockquote
    #   段落之間的空行     → 切成兩段
    pending_blank = False
    for line in lines:
        s = line.strip()
        if not s:
            pending_blank = True
            continue

        if re.match(r"^\d+[.)]\s+", s):
            if mode != "ol":
                flush()
                mode = "ol"
            buf.append(re.sub(r"^\d+[.)]\s+", "", s))
        elif s.startswith("- ") or s.startswith("* "):
            if mode != "ul":
                flush()
                mode = "ul"
            buf.append(s[2:])
        elif s.startswith(">"):
            if mode != "quote" or pending_blank:
                flush()
                mode = "quote"
            buf.append(s.lstrip(">").strip())
        else:
            if mode in ("ol", "ul") and not pending_blank:
                buf[-1] += " " + s          # 清單條目的折行接續
            elif mode == "p" and not pending_blank:
                buf.append(s)               # 段落內的折行
            else:
                flush()
                mode = "p"
                buf.append(s)
        pending_blank = False
    flush()
    return "\n".join(out)


def split_sections(body):
    """依 '## 標題' 切段，回傳 [(標題, 內文), ...]

    沒有任何 '##' 時（手機上直接寫散文的常態），整篇當作「我的想法」一段。
    第一個 '##' 之前的文字也一併歸進「我的想法」——這樣他可以直接開寫，
    需要引用時才在後面補一個 '## 重點 / Keypoint'。
    """
    parts = re.split(r"^##\s+(.+)$", body, flags=re.M)
    sections = []

    preamble = parts[0].strip()
    if preamble:
        sections.append(("我的想法", preamble))

    for i in range(1, len(parts), 2):
        sections.append((parts[i].strip(), parts[i + 1].strip()))
    return sections


# ============================================================
# 產生單則筆記
# ============================================================
def first_sentence(body, limit=70):
    """從正文抓第一句當列表卡片的摘要（手機上只打 title 時的 fallback）。"""
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", ">", "-", "*", "!")) or re.match(r"^\d+[.)]", s):
            continue
        s = re.sub(r"[*`\[\]]|\(https?://[^)]+\)", "", s)
        for stop in ("。", "！", "？"):
            if stop in s:
                s = s.split(stop)[0] + stop
                break
        return s[:limit]
    return ""


def git_added_at(path):
    """這個檔案第一次被提交的時間（ISO 8601，含時區）。

    這才是「Chris 寫下這則筆記的時間」。不要拿 slug 前綴的日期當發佈時間——
    那是原文**被抓取**的日期，跟他何時讀完、何時決定寫筆記無關，
    會讓列表順序跟他的實際書寫順序對不上。

    需要完整的 git 歷史：workflow 的 checkout 必須設 fetch-depth: 0，
    否則淺層 clone 拿不到最初那個 commit，就會悄悄退回 slug 日期。
    """
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", path],
            cwd=ROOT, capture_output=True, text=True, timeout=20)
        lines = [x for x in out.stdout.strip().split("\n") if x.strip()]
        return lines[-1] if lines else ""
    except Exception:
        return ""


def is_note_file(name):
    """notes/src/ 裡不是筆記的檔案：說明文件、底線或點開頭的暫存檔。"""
    return (name.endswith(".md")
            and name != "README.md"
            and not name.startswith(("_", ".")))


def build_note(path, short_url=""):
    with open(path, encoding="utf-8") as f:
        meta, body = parse_front_matter(f.read())

    # 手機上只會打 source ＋ title，其餘全部自動補
    slug = meta.get("slug") or os.path.splitext(os.path.basename(path))[0]
    meta["slug"] = slug
    added_at = git_added_at(path)
    if not meta.get("date"):
        if added_at:
            meta["date"] = added_at[:10]
        else:
            m = re.match(r"^(\d{4})(\d{2})(\d{2})", slug)
            meta["date"] = "-".join(m.groups()) if m else ""
    if not meta.get("title"):
        raise ValueError("front-matter 缺 title——標題是你的結論，不能自動生成")
    if not meta.get("hook"):
        meta["hook"] = first_sentence(body)

    src = dict(meta.get("source", {}) or {})
    # 也接受攤平的 source_* 欄位。手機上 GitHub 的 Preview 會把 front-matter
    # 渲染成表格，巢狀 mapping 會變成「表格裡再包一層表格」而爆版，
    # 所以預填一律用攤平寫法；巢狀寫法保留相容。
    for k in ("title", "author", "site", "url", "published", "archive"):
        v = meta.get("source_" + k)
        if v and not src.get(k):
            src[k] = v

    tags = meta.get("tags", []) or []
    sections = split_sections(body)

    note_url = "%s/notes/%s.html" % (CANONICAL_BASE, slug)
    md_url = "%s/notes/%s.md" % (CANONICAL_BASE, slug)
    cover = meta.get("cover", "")
    cover_url = "%s/notes/%s" % (CANONICAL_BASE, cover) if cover else ""

    # ---------- JSON-LD ----------
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": meta["title"],
        "abstract": meta.get("hook", ""),
        "datePublished": meta["date"],
        "dateModified": meta["date"],
        "inLanguage": "zh-Hant",
        "url": note_url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": note_url},
        "author": {"@type": "Person", "name": AUTHOR_NAME, "url": AUTHOR_URL},
        "publisher": {"@type": "Person", "name": AUTHOR_NAME, "url": AUTHOR_URL},
        "keywords": tags,
        "genre": "讀書筆記",
        "encoding": {
            "@type": "MediaObject",
            "encodingFormat": "text/markdown",
            "contentUrl": md_url,
        },
    }
    if cover_url:
        ld["image"] = cover_url
    if src.get("url"):
        ld["isBasedOn"] = src["url"]
        citation = {"@type": "Article", "url": src["url"]}
        if src.get("title"):
            citation["headline"] = src["title"]
        if src.get("author"):
            citation["author"] = {"@type": "Person", "name": src["author"]}
        if src.get("published"):
            citation["datePublished"] = src["published"]
        ld["citation"] = citation

    # ---------- 區塊 HTML ----------
    body_html = []
    for idx, (heading, content) in enumerate(sections, start=1):
        sid = SECTION_IDS.get(heading, "sec-%d" % idx)
        body_html.append(
            '<section id="{sid}" aria-labelledby="h-{sid}">\n'
            '  <h2 id="h-{sid}" data-num="{num}">{heading}</h2>\n'
            "  {content}\n"
            "</section>".format(
                sid=sid,
                num="%02d" % idx,
                heading=html.escape(heading),
                content=render_blocks(content),
            )
        )

    # ---------- 來源列 ----------
    # 原文標題通常已經寫在筆記標題裡（「Chris 筆記｜原標題」），
    # 所以 source_title 一般不填；沒有的話退而用站名當連結文字，不要留空連結。
    source_bits = []
    label = src.get("title") or src.get("site") or src.get("url", "")
    used_site_as_label = not src.get("title") and bool(src.get("site"))
    if label:
        if src.get("url"):
            source_bits.append(
                '原文：<cite><a href="%s" rel="external noopener">%s</a></cite>'
                % (html.escape(src["url"], quote=True), html.escape(label))
            )
        else:
            source_bits.append("原文：<cite>%s</cite>" % html.escape(label))
    if src.get("author"):
        source_bits.append(html.escape(src["author"]))
    if src.get("site") and not used_site_as_label:
        source_bits.append(html.escape(src["site"]))
    if src.get("published"):
        source_bits.append(
            '<time datetime="%s">%s</time>'
            % (html.escape(src["published"], quote=True), html.escape(src["published"]))
        )
    source_line = " · ".join(source_bits)

    cover_html = ""
    if cover:
        cover_html = (
            '<figure class="note-cover">\n'
            '  <img src="%s" alt="%s" loading="lazy">\n'
            "  <figcaption>%s</figcaption>\n"
            "</figure>"
            % (
                html.escape(cover, quote=True),
                html.escape(src.get("title", meta["title"])),
                html.escape(meta.get("cover_credit", "圖片取自原文")),
            )
        )
        # 插在他自己的評論（第一段，通常是「我的想法」）後面，不放在最上面——
        # 圖片是佐證不是門面，讀者要先看到他寫了什麼。沒有任何段落時退回最前面。
        insert_at = 1 if body_html else 0
        body_html.insert(insert_at, cover_html)

    tags_html = ""
    if tags:
        tags_html = '<div class="note-tags">%s</div>' % "".join(
            '<span class="note-tag">%s</span>' % html.escape(t) for t in tags
        )

    foot_links = []
    if src.get("url"):
        foot_links.append(
            '<a class="primary" href="%s" rel="external noopener">讀原文 ↗</a>'
            % html.escape(src["url"], quote=True)
        )
    foot_links.append('<a href="./%s.md">Markdown 版</a>' % slug)
    foot_links.append('<a href="../index.html#notes">← 回筆記列表</a>')

    short_html = ""
    if short_url:
        short_html = (
            '<p class="note-short">分享用短連結：'
            '<a href="%s"><code>%s</code></a></p>'
            % (html.escape(short_url, quote=True), html.escape(short_url))
        )

    page = NOTE_TEMPLATE.format(
        title=html.escape(meta["title"]),
        title_attr=html.escape(meta["title"], quote=True),
        hook=html.escape(meta.get("hook", ""), quote=True),
        date=html.escape(meta["date"], quote=True),
        canonical=note_url,
        md_rel="./%s.md" % slug,
        og_image=cover_url,
        og_image_tag=(
            '<meta property="og:image" content="%s">\n'
            '<meta name="twitter:card" content="summary_large_image">' % cover_url
        )
        if cover_url
        else '<meta name="twitter:card" content="summary">',
        jsonld=json.dumps(ld, ensure_ascii=False, indent=2),
        source_line=source_line,
        sections="\n".join(body_html),
        tags=tags_html,
        foot="\n    ".join(foot_links),
        short=short_html,
        site_name=SITE_NAME,
    )

    with open(os.path.join(NOTES_DIR, slug + ".html"), "w", encoding="utf-8") as f:
        f.write(page)

    # ---------- markdown 雙生檔 ----------
    md = ["# %s\n" % meta["title"]]
    head = ["> 讀書筆記 · %s · %s" % (meta["date"], AUTHOR_NAME)]
    if src.get("title"):
        who = src.get("author", "")
        site = src.get("site", "")
        pub = src.get("published", "")
        head.append(
            "> 原文：%s%s%s"
            % (
                src["title"],
                " — %s" % who if who else "",
                "（%s%s）" % (site, "，" + pub if pub else "") if site or pub else "",
            )
        )
    if src.get("url"):
        head.append("> 原文連結：%s" % src["url"])
    head.append("> 本頁 HTML：%s" % note_url)
    if short_url:
        head.append("> 短連結：%s" % short_url)
    if tags:
        head.append("> 標籤：%s" % "、".join(tags))
    md.append("\n".join(head) + "\n")
    if cover and sections and sections[0][0] == "我的想法":
        # 圖片放在他自己的評論後面，跟 HTML 版一致——不是門面，是佐證。
        md.append(sections[0][1] + "\n")
        md.append("![%s](%s)\n" % (src.get("title", meta["title"]), cover))
        for heading, content in sections[1:]:
            md.append("## %s\n\n%s\n" % (heading, content))
    else:
        # 沒有前言可插（少見：直接以 ## 開頭）就退回放最前面
        if cover:
            md.append("![%s](%s)\n" % (src.get("title", meta["title"]), cover))
        md.append(body.strip() + "\n")
    md_text = "\n".join(md)

    with open(os.path.join(NOTES_DIR, slug + ".md"), "w", encoding="utf-8") as f:
        f.write(md_text)

    return {
        "short": short_url,
        "slug": slug,
        # 排序用的完整時間戳：同一天送出兩篇時，只有日期分不出先後
        "published_at": added_at or meta["date"],
        "date": meta["date"],
        "title": meta["title"],
        "hook": meta.get("hook", ""),
        "tags": tags,
        "cover": cover,
        "url": "notes/%s.html" % slug,
        "markdown": "notes/%s.md" % slug,
        "source": src,
    }, md_text


# ============================================================
# 站台層檔案
# ============================================================
BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def base36(n):
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = BASE36[r] + out
        if not n:
            return out


def load_shortlinks():
    """slug → 短碼。一旦指派就永不變動——短連結會被貼到 Facebook，
    改掉等於讓已經發出去的貼文全部失效。"""
    path = os.path.join(NOTES_DIR, "shortlinks.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_shortlinks(mapping):
    path = os.path.join(NOTES_DIR, "shortlinks.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def assign_short(mapping, slug):
    if slug in mapping:
        return mapping[slug]
    used = set(mapping.values())
    n = 1
    while base36(n) in used:
        n += 1
    mapping[slug] = base36(n)
    return mapping[slug]


# 轉址頁要自己帶 OG 標籤：meta-refresh 不是 HTTP 轉址，Facebook 的爬蟲
# 不保證會跟過去抓最終頁，沒有 OG 就沒有預覽卡片——而短連結存在的目的
# 就是拿去貼 FB，沒預覽等於白做。
REDIRECT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<title>{title}</title>
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{hook}">
<meta property="og:url" content="{target}">
<meta property="og:locale" content="zh_TW">
{og_image}
</head>
<body>
<p>正在前往：<a href="{target}">{title}</a></p>
<script>location.replace("{target}");</script>
</body>
</html>
"""


def write_redirects(notes, mapping):
    d = os.path.join(ROOT, "n")
    os.makedirs(d, exist_ok=True)
    for n in notes:
        code = mapping[n["slug"]]
        target = "%s/%s" % (CANONICAL_BASE, n["url"])
        cover = n.get("cover", "")
        og_image = (
            '<meta property="og:image" content="%s/notes/%s">\n'
            '<meta name="twitter:card" content="summary_large_image">'
            % (CANONICAL_BASE, cover)
        ) if cover else '<meta name="twitter:card" content="summary">'
        with open(os.path.join(d, "%s.html" % code), "w", encoding="utf-8") as f:
            f.write(REDIRECT_TEMPLATE.format(
                target=target,
                title=html.escape(n["title"], quote=True),
                hook=html.escape(n.get("hook", ""), quote=True),
                og_image=og_image))


def latest_date(notes):
    """最新一則筆記的日期。用它當「更新時間」而不是 now()——
    產出必須是 deterministic，否則 GitHub Actions 每次建置都會產生
    只有時間戳不同的 commit，觸發自己、變成無限迴圈。"""
    return max((n["date"] for n in notes), default="")


def write_index_json(notes):
    payload = {
        "site": SITE_NAME,
        "description": "Chris 的讀書筆記——讀完之後自己想了什麼。",
        "canonical_base": CANONICAL_BASE,
        "updated": latest_date(notes),
        "count": len(notes),
        "notes": notes,
    }
    with open(os.path.join(NOTES_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_sitemap(notes):
    urls = [(CANONICAL_BASE + "/", None, "1.0")]
    for n in notes:
        urls.append(("%s/%s" % (CANONICAL_BASE, n["url"]), n["date"], "0.8"))
        urls.append(("%s/%s" % (CANONICAL_BASE, n["markdown"]), n["date"], "0.5"))
    urls.append((CANONICAL_BASE + "/llms.txt", None, "0.5"))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, prio in urls:
        lines.append("  <url>")
        lines.append("    <loc>%s</loc>" % html.escape(loc, quote=True))
        if lastmod:
            lines.append("    <lastmod>%s</lastmod>" % lastmod)
        lines.append("    <priority>%s</priority>" % prio)
        lines.append("  </url>")
    lines.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


AI_BOTS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-Web", "anthropic-ai", "Claude-SearchBot",
    "Google-Extended", "Applebot-Extended", "Amazonbot",
    "PerplexityBot", "Bytespider", "CCBot", "meta-externalagent",
]


def write_robots():
    lines = [
        "# %s — %s" % (SITE_NAME, SITE_TAGLINE),
        "# 這個站歡迎 AI agent 檢索與取用內容。",
        "",
        "User-agent: *",
        "Allow: /",
        "Content-Signal: ai-train=yes, search=yes, ai-input=yes",
        "",
    ]
    for bot in AI_BOTS:
        lines += [
            "User-agent: %s" % bot,
            "Allow: /",
            "Content-Signal: ai-train=yes, search=yes, ai-input=yes",
            "",
        ]
    lines += [
        "Sitemap: %s/sitemap.xml" % CANONICAL_BASE,
        "",
    ]
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_llms(notes):
    lines = [
        "# %s" % SITE_NAME,
        "",
        "> Chris（%s）的個人站：室內設計與日本建築背景，把日常工作改寫成「一個人＋AI」的流程。"
        "本站包含讀書筆記、專案介紹與工具清單，全部繁體中文。" % SITE_TAGLINE,
        "",
        "站點正本：%s" % CANONICAL_BASE,
        "每則筆記都同時提供 HTML 與 markdown 兩種格式，markdown 版把 .html 換成 .md 即可取得。",
        "",
        "## 讀書筆記",
        "",
        "格式固定為三段：**我的想法**（Chris 本人的評註，錨點 #my-take）、"
        "**這篇在說什麼**（重點整理，錨點 #summary）、**原文金句**（引用，錨點 #quotes）。",
        "",
    ]
    for n in notes:
        s = n.get("source", {}) or {}
        lines.append(
            "- [%s](%s/%s)：%s%s"
            % (
                n["title"],
                CANONICAL_BASE,
                n["markdown"],
                n.get("hook", ""),
                "（原文：%s）" % s.get("title", "") if s.get("title") else "",
            )
        )
    lines += [
        "",
        "## 其他",
        "",
        "- [筆記索引 JSON](%s/notes/index.json)：機器可讀的完整清單" % CANONICAL_BASE,
        "- [全文串接](%s/llms-full.txt)：所有筆記的完整 markdown，一次取用" % CANONICAL_BASE,
        "- [網站首頁](%s/)：專案、工具棚與關於頁（單頁式 OS 介面）" % CANONICAL_BASE,
        "",
    ]
    with open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_llms_full(notes, texts):
    parts = [
        "# %s — 全文" % SITE_NAME,
        "",
        "Chris 的讀書筆記全文串接，供 LLM 一次取用。共 %d 則。" % len(notes),
        "最後更新：%s" % latest_date(notes),
        "正本網址：%s" % CANONICAL_BASE,
        "",
        "---",
        "",
    ]
    for text in texts:
        parts.append(text.strip())
        parts.append("")
        parts.append("---")
        parts.append("")
    with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


NOTE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — 讀書筆記 · {site_name}</title>
<meta name="description" content="{hook}">
<meta name="author" content="Chris Hsu">
<link rel="canonical" href="{canonical}">
<link rel="alternate" type="text/markdown" href="{md_rel}" title="Markdown 版本">
<meta property="og:type" content="article">
<meta property="og:title" content="{title_attr}">
<meta property="og:description" content="{hook}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="zh_TW">
<meta property="article:published_time" content="{date}">
{og_image_tag}
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📖</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&family=Noto+Sans+TC:wght@400;500;700&family=Noto+Serif+TC:wght@700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="./assets/note.css">
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>

<nav class="note-topbar">
  <a class="tb-brand" href="../index.html">CHRIS OS</a>
  <a href="../index.html#notes">讀書筆記</a>
  <span class="tb-spacer"></span>
  <a href="{md_rel}">.md</a>
</nav>

<article class="note">
  <header class="note-head">
    <p class="note-kicker">讀書筆記 · <time datetime="{date}">{date}</time></p>
    <h1>{title}</h1>
    <p class="note-source">{source_line}</p>
  </header>

{sections}

  {tags}

  <footer class="note-foot">
    {foot}
  </footer>
  {short}
</article>

</body>
</html>
"""


def main():
    if not os.path.isdir(SRC_DIR):
        print("尚無 %s，沒有筆記可處理" % SRC_DIR)
        return 0

    files = sorted(f for f in os.listdir(SRC_DIR) if is_note_file(f))
    shortlinks = load_shortlinks()
    notes, texts = [], []
    for name in files:
        slug = os.path.splitext(name)[0]
        code = assign_short(shortlinks, slug)
        short_url = "%s/n/%s%s" % (SHORT_BASE, code, SHORT_SUFFIX)
        try:
            meta, text = build_note(os.path.join(SRC_DIR, name), short_url)
        except Exception as e:
            print("✗ %s：%s" % (name, e), file=sys.stderr)
            return 1
        notes.append(meta)
        texts.append(text)
        print("✓ %s" % meta["slug"])

    # 先配對再排序，避免 notes 就地排序後與 texts 錯位
    paired = sorted(
        zip(notes, texts),
        key=lambda p: (p[0].get("published_at") or p[0]["date"], p[0]["slug"]),
        reverse=True,
    )
    notes = [n for n, _ in paired]
    texts = [t for _, t in paired]

    write_redirects(notes, shortlinks)
    save_shortlinks(shortlinks)
    write_index_json(notes)
    write_sitemap(notes)
    write_robots()
    write_llms(notes)
    write_llms_full(notes, texts)

    print("\n共 %d 則筆記" % len(notes))
    print("已更新：notes/index.json、notes/shortlinks.json、n/*.html、"
          "sitemap.xml、robots.txt、llms.txt、llms-full.txt")
    print("canonical：%s" % CANONICAL_BASE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
