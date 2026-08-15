# 讀書筆記——怎麼在手機上寫一則

在這個 `notes/src/` 資料夾按 **Add file → Create new file**，檔名打 `<日期>-<英文slug>.md`
（例如 `20260815-japan-ai-adoption-slow.md`，跟 twitter_article 那邊同名最好認），
內容照下面這樣寫，commit 完就結束了——剩下全部自動。

```markdown
---
source: 20260815-japan-ai-adoption-slow
title: 日本不是不會用 AI，是不敢犯錯
---

讀完的第一個念頭是，這篇講的其實不是技術問題。

接下來想寫多長就寫多長，一段一段寫下去就好。不用分點、不用小標，
就當成在寫一則 FB 貼文。
```

**只有兩行是必填的：**

| 欄位 | 意思 |
|---|---|
| `source` | twitter_article 裡那篇的資料夾名。用來自動抓原文作者、網址、發表日、封面圖。 |
| `title` | 你的一句話結論。**不是原文標題**——列表上顯示的是這句，所以寫你的觀點。 |

其餘（日期、卡片摘要、原文 metadata、封面）都會自動補上。
不知道 `source` 要填什麼，就去 [twitter_article](https://github.com/chrisincite/twitter_article)
看那篇文章的資料夾名。

## 想多控制一點的話

這些都是選填，寫了就會蓋過自動判斷：

```markdown
---
source: 20260815-japan-ai-adoption-slow
title: 日本不是不會用 AI，是不敢犯錯
hook: 列表卡片上顯示的一句話（不寫就自動取正文第一句）
tags: [AI 導入, 日本, 組織文化]
---

正文……

## 重點/Keypoint

> 想引用原文的話，加這一段。不想引用就整段不要寫。
```

自動補完之後，這個檔案會被改寫成完整版（作者、網址那些會被填進來）。
**之後你再編輯它，補完程式不會再覆蓋你改的東西**——所以作者名抓錯了，直接在 GitHub 上改掉就好。

## commit 之後會發生什麼

1. GitHub Actions 去 twitter_article 撈原文 metadata 和封面圖
2. 產出 `notes/<slug>.html`（給人看）和 `notes/<slug>.md`（給 AI agent 看）
3. 更新 `sitemap.xml`、`llms.txt`、`llms-full.txt`、`notes/index.json`
4. 推回 main → GitHub Pages 更新，同時觸發 Cloudflare 鏡像部署

大概一兩分鐘後，兩個網址都會看得到：

- https://chrisincite.github.io/#notes
- https://os.housearch.net/#notes

跑失敗的話去 repo 的 **Actions** 分頁看紅色那筆的 log。

## 寫作原則

正文就是你的話。**不要分點條列**——一段一段的散文比較有人味，
這也是這個筆記區存在的理由：文章原文在 twitter_article 裡已經有了，
這裡要留下的是「讀完之後你想了什麼」。
