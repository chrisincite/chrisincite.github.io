---
title: "Chris 筆記｜免費好用的Talkify 語音輸入系統"
cover: "img/20260819-talkify-macos-dictation-cover.jpg"
cover_credit: "圖片取自原文"
source_author: "@tornikegomareli（Tornike Gomareli）"
source_site: "X"
source_url: "https://x.com/tornikegomareli/status/2088524464224919700"
source_published: "2026-08-15"
source_archive: "20260819/20260819-talkify-macos-dictation"
---

終於在Claude Code CLI 中實現語音輸入自由了！

雖然MacOS有內建語音輸入的功能，但是被藏在系統設定內，每次開啟關閉都極為不便，而且這款 Talkify 有許多有進步的地方。

1. 按住講，不是連按兩下 Control
fn 按住 → 講 → 放開。這是 push-to-talk，直接解掉我上一輪點名的「Ctrl 誤觸」問題——終端裡 Ctrl 組合鍵用得兇，雙擊 Control 太容易誤觸發。另有 quick-tap 進免持模式、Esc 中途取消。快捷鍵可改。

2. 雙語各綁一顆鍵
fn 講中文、右 ⌥ 講英文，兩個模型同時常駐，不用進選單切換。這解掉了「中英混講要中斷去換語言」那個痛點——雖然仍不能在同一句裡混講，但切換成本從「開設定面板」降到「換一根手指」。

它的說明還特別解釋了為什麼不做自動語言偵測：Apple Speech 一次只認一種語言，猜錯的結果不是報錯而是「流暢的胡話」。這個判斷是對的。

3. 用貼上插入文字
這對你的 Claude Code 場景反而是關鍵優點。系統聽寫是把「未確定文字」（marked text）即時注入輸入欄位，跟 TUI 的畫面重繪會打架；Talkify 是講完一次貼進去，繞過了整個 marked text 機制，終端相容性會穩很多。

4. 拖檔轉錄
把音訊／影片拖到瀏海處就轉逐字稿，背景跑不擋聽寫。這是內建聽寫完全沒有的功能。

5. 完全離線、MIT、免費
不發網路請求、不存音檔。跟內建聽寫的離線模式同等隱私，但你可以讀原始碼。

## 摘要 / Summary

Tornike Gomareli 想要 macOS 上有一個真正即時、原生體驗的語音聽寫工具，於是自己動手做了 Talkify——一款只有 8.2 MB 大小的聽寫 App，從放開按鍵到文字出現，中位延遲僅 123 毫秒。他把它拿去跟市面上幾款熱門聽寫 App（superwhisper、voiceink、wispr flow、macwhisper）比較，結果 Talkify 是其中速度最快的一個。

這款 App 的介面設計貼著 macOS 的視覺語言：常駐在螢幕瀏海（notch）位置，搭配漂亮的 shader 動畫效果，並提供各種客製化選項，讓聽寫這件事融入日常操作而不突兀。

技術上，Talkify 建立在 Apple 的 SpeechAnalyzer 之上，使用系統內建管理的語音模型做完全裝置端（on-device）轉錄，免費且開源。

## 重點 / Keypoint

「從放開按鍵到文字出現的中位延遲只要 123 毫秒。」

「在跟 superwhisper、voiceink、wispr flow 和 macwhisper 這五款 App 的測試中，它是速度最快的一個。」

「Talkify 是建立在 Apple 的 SpeechAnalyzer 之上，用系統內建管理的語音模型進行完全裝置端（on-device）轉錄，免費且開源。」
