# 超入門（/guide）怎麼新增一篇

一篇教學＝這裡一個 `.md`＋`../img/<slug>/` 一個圖片資料夾＋`../eli5/<slug>.html` 一頁圖解版。
寫好之後跑 `python3 scripts/build.py`，其餘（HTML、.md 雙生檔、index.json、短連結、sitemap、llms.txt）全部自動產生。

## 1. front-matter

```
---
title: 小學生也能懂的『XXX』超入門
date: 2026-09-11
status: ready                      # draft 不會上站；ready / published 才會
eli5: ./eli5/xxx.html              # 圖解版路徑，每篇標配
hook: 一句話說明這篇在講什麼。
tags: [XXX, 超入門, AI 協作]        # ⚠️ 只認行內式，不可寫成 YAML 區塊清單
cover: img/xxx/01-first.png        # 不填的話會自動拿文章第一張圖
---
```

**`tags` 一定要寫成 `[a, b]` 這種行內式。** 寫成
```
tags:
  - a
  - b
```
會被 front-matter 解析器當成巢狀鍵、變成 dict，而且不會報錯——前端讀到就整個分區空白。
build.py 現在會噴警告，但不要靠它。

## 2. 本文

- `#` ＝章。自動編錨點 `#ch-1`、`#ch-2`……，也自動生出「本文架構」目錄，**不要自己再寫一份目錄**
- `##` / `###` ＝章內小標
- 第一個 `#` 之前的文字＝導言，會排在目錄之前
- ` ``` ` 圍欄、markdown 表格、`---` 分隔線都支援
- 圖片寫 `![說明](img/<slug>/檔名.png)`，緊接著的 `> 這一行`會變成圖說；沒寫 `>` 的話會拿 `[]` 裡的文字當圖說

## 3. 圖片

放 `guide/img/<slug>/`，**一篇一個子資料夾**，不要丟在 `img/` 根目錄。

終端機／網頁截圖請先壓過再放進來，2x 截圖直接進 repo 會肥十倍：

```bash
magick 原圖.png -resize 1520x -strip -colors 256 PNG8:目標.png
```

實測 6.9MB 的十張終端機截圖壓成 712KB，文字仍然清晰。照片類的改用 `-quality 88` 存成 jpg。

## 4. 圖解版（eli5）

`guide/eli5/<slug>.html`，單檔靜態頁，共用 `guide/eli5/assets/eli5.css`。
照著 `github.html` 或 `claude-code.html` 改：一個概念一張 `.card`，圖用 inline SVG 自己畫，不要外部相依。

版型是固定的：`.num` 編號 → `<h2>` 大標 → `.say` 一句話 → SVG → `.punch` 結論（`<em>` 會變紅）→ `.word` 對應的英文術語。

## 5. 建置與驗收

```bash
python3 scripts/build.py
python3 -m http.server 8777        # 用 http 開，不要用 file:// ——index.json 讀不到
```

建置訊息會印 `🔰 <slug>（N 章、M 圖）`。**章數和圖數要跟你寫的對得上**——
對不上通常是 ``` 圍欄沒收尾，或是圍欄裡有行首 `#`（shell 註解）被誤判成章標題。
