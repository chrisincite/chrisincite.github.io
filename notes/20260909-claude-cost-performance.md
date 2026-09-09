# Chris 筆記｜用 Claude Platform 降低成本、提升效能

> 讀書筆記 · 2026-09-09 · Chris Hsu
> 原文連結：https://x.com/ClaudeDevs/status/2097369738968195513
> 本頁 HTML：https://chrisincite.github.io/notes/20260909-claude-cost-performance.html
> 短連結：https://os.housearch.net/n/h

Anthropic 突然在昨晚發布了這篇文章，教你如何降低使用 Claude 的成本，這事聽起來就是有點詭異。很明顯，超越 Astra 的模型即將被放出來了，Anthropic 知道這種貴得嚇死人的前沿模型會讓大家又愛又恨，所以先教會你把自己的設定調整好，這樣就能做好迎接暴風的準備。

不只是手把手告訴你怎麼做，Anthropic 還在 Claude Code 中新增了 skill，你不用自己動手，真的是夠體貼了⋯

1）輸入 /claude-api prompt-audit ，這個新增的skill專門幫你找出過時、囉嗦、互相打架的指令，然後看它整理的報告，報告會告訴你，哪一行有問題、為什麼過時、建議怎麼改，你可以直接接受它的建議。

2）再輸入 /claude-api cost-optimize ，讓它試算成本並最佳化。

3）用你經常跑的專案，執行 /claude-api hillclimb ，它會試不同模型組合，比如換更便宜的模型，或者把 effort 從高調到低，或者精煉微調提示詞。

4）更新後你可以進入 Claude Console 官方後台，去看 cache hit rate ，這裡會顯示用量和緩存情況，進階的 cache diagnostics API ，你如果有興趣，就自己再深挖吧⋯⋯

## 摘要 / Summary

這篇文章來自 ClaudeDevs，說明如何在不犧牲應用效能的前提下降低使用 Claude Platform 的成本，主要透過三個修正點：拉高 prompt cache 命中率、在升級到前沿模型時移除 prompt 裡針對舊模型弱點寫的反模式指令、以及把 effort 校準到符合任務所需。文章拆解了 prompt cache 的運作機制——綁定特定模型、前綴需 byte-exact 完全一致、有限的存活時間（TTL）——並列出實務技巧，例如讓易變值遠離前綴、延後載入不常用工具、預熱快取、隨對話成長移動快取斷點等。

第二部分談 instructions 反模式：像是「double-check」「be maximally thorough」這類驗證儀式與加強語氣的字眼、強制性的草稿鷹架、過時的 few-shot 範例、互相矛盾的規則，這些過去用來修補舊模型弱點的指令，在前沿模型上反而會拖累表現、浪費 token。文章用一個客服基準測試示範，把 Opus 4.8 遷移到 Opus 5 後，執行 /claude-api prompt-audit 移除這些反模式，平均降低了 14.6% 的成本，並提升了 5.3% 的準確率。

第三部分談 effort 校準：設得太高會導致過度思考、拉高成本卻不一定換到分數；設得太低則會在證據還不充分時就停下來，答案看似完成卻建立在不完整的資訊上。文章建議測試「更強模型＋更低 effort」的組合，往往比「較弱模型＋更高 effort」更便宜也更準，並介紹 /claude-api hillclimb 這個指令，能自動在模型與 effort 等級之間搜尋最佳的成本效能組合。文末以 LegalBench、tau2-bench retail、OfficeQA Pro、SWE-bench Verified 四個公開基準測試示範 /claude-api cost-optimize 帶來的成本降幅，從 52% 到 73% 不等。

## 重點 / Keypoint

> 效能與成本經常被視為一種取捨：想花得少，就得接受較差的結果。但實務上我們發現，許多使用 Claude Platform 的應用可以透過三個修正點，在不犧牲效能的前提下降低成本：把 prompt cache 命中率拉到最高、在升級到前沿 Claude 模型時移除 prompt 裡的反模式（anti-pattern）、以及把 effort 校準到符合任務所需。

> 執行 /claude-api prompt-audit 移除了這些反模式，平均降低了 14.6% 的成本，並提升了 5.3% 的準確率。

> 測試「更強的模型＋更低的 effort」組合。用低 effort 跑一個更強的模型，可能會比用高 effort 硬撐一個較弱的模型還要便宜。
