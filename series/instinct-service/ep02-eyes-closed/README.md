# 本能服務｜Instinct Service — EP.02《閉眼服務｜Service with Eyes Closed》

▶ **成片下載：[Release instinct-service-ep02-v1.0.0](https://github.com/alextlife24/alex-t-animation-studio/releases/tag/instinct-service-ep02-v1.0.0)**（`ep02_eyes_closed.mp4`，43.9 MB）

90 秒直式（1080×1920、30 fps、2700 幀）低多邊形 3D 黑色幽默短片，H.264 + AAC，英文 AI 配音，燒錄繁體中文字幕。延續第一集的角色、聲線、材質、燈光、字幕樣式與鏡頭語言。

## 故事

同一座夜晚的森林高級餐廳吧台，吧台旁多了一個淡水展示缸。黑熊先生問：「那些蝦，新鮮嗎？」並要求派崔克親自確認。收銀螢幕傳來經理的指示：「確認新鮮度。保持眼神接觸。」派崔克站上踏台，閉上眼睛把頭浸入水中，用嘴喙在水下慢慢左右掃動。黑熊先生只看到他閉著眼睛：「你在睡覺嗎？還是在我投訴的時候？」派崔克在水下用嘴喙找到藏在石頭旁的蝦，再用手網撈起確認牠還活著。聽到「電訊號」三個字，黑熊先生拿出只剩 1% 電量的手機：「幫這個充電。」派崔克解釋：「先生，我能感應電，不能發電。」最後，螢幕跳出經理的新指示：「新增職務：充電站」。

全片只有兩位出場與配音角色；經理只以收銀螢幕上的文字出現。完整分鏡與對白見 [`episodes/ep02_eyes_closed/script.md`](episodes/ep02_eyes_closed/script.md)。

## 生物冷知識與來源

- 鴨嘴獸在水下覓食時會閉上眼睛、耳朵與鼻孔，靠嘴喙上的電感受器與機械感受器找到獵物。
- 片中的電感應只是一種感知能力：派崔克不會發電、充電或放電，手機從頭到尾停在 1%。
- 示範發生在水下，嘴喙確實浸在水中，不是隔著玻璃或在空氣中感應。黑熊先生說的「睡覺」是他自己的誤解。
- 水下沒有台詞。微弱電訊號只用短暫、低強度的 2D 示意疊圖呈現，給觀眾看，不是場景裡的閃電。
- 片中只確認活蝦的位置與存活，不把電感應說成檢測新鮮度的儀器，也不加入其他冷知識。
- 來源：Australian Museum — Platypus. <https://australian.museum/learn/animals/mammals/platypus/>

## 與第一集的延續

- 程式、角色模型、場景與聲線設定全部沿用第一集（[`ep01-no-milk`](../ep01-no-milk/)），沒有重建；第一集的空牛奶杯放在吧台角落。
- 本集新增的道具只寫在 `episodes/ep02_eyes_closed/props.json`：淡水展示缸（0.56×0.42×0.44 m，缸口 1.20 m）、碎石、石頭、水草、四隻沒有表情的淡水蝦、31.5 cm 的穩固踏台、乾淨手網與掛鉤、小毛巾與毛巾架、黑熊先生的手機。
- 角色新增兩個預設為 0 的表演通道，所以第一集不受影響：`reach`（頭部略為前伸，前伸時才露出頸部）和 `squeeze`（下眼瞼閉合，用於水下閉眼）。派崔克的肚子比頭更突出，只彎腰無法讓臉入水，所以需要這個前伸。

## 資料夾內容

```
make.py                    一鍵流程：配音 → 時間軸 → 圖像 → Blender 烘焙 → 渲染 → 混音 → MP4 → 驗收
series/                    系列共用設定（與第一集相同）
episodes/ep02_eyes_closed/
  script.json / script.md  劇本（段落、台詞、字幕、螢幕文字、資訊卡、電訊號疊圖時段）
  props.json               本集道具、握點、初始掛載與新增鏡頭預設
  shots.json               鏡頭表
  acting.json              表演、手部目標、道具事件、蝦的游動路徑、水面漣漪
  sound.json               音效、環境音（含水族箱過濾聲、水泡）、水下悶音段落、靜音段落
  subtitles.zh-Hant.srt/.ass  繁體中文字幕
  assets/voice/            成片使用的 16 句配音 WAV 與 manifest（可直接重用）
src/                       程式碼（新增 signal_overlay.py：電訊號示意疊圖）
requirements.txt           Python 依賴（固定版本）
requirements-verify.txt    驗收用語音辨識依賴
.env.example               工具路徑設定範例（本專案不需要任何 API 金鑰）
```

## 製作工具與環境

| 工具 | 版本（實際使用） | 用途 |
|---|---|---|
| Blender | 5.2.1 LTS，OpenGL 後端 | 3D 動畫、EEVEE 渲染 |
| FFmpeg | 9.0.1（需含 libx264、libass、rubberband） | 合成、字幕燒錄、編碼 |
| Python | 3.11 | 配音、時間軸、混音、驗收 |
| Kokoro v1.0 | kokoro-onnx 0.6.1（Apache-2.0，本機執行） | 英文 AI 配音 |
| faster-whisper | 1.2.1（small 模型） | 驗收時重聽成片 |

測試環境為 Windows 11（Snapdragon X、Adreno GPU）。字幕字型使用系統的微軟正黑體；字型檔不收錄在儲存庫中。

## 安裝

安裝方式與第一集相同：

```bash
pip install -r requirements.txt
```

下載 Kokoro 模型到本資料夾的 `.models/`（約 350 MB，不納入 Git）：

```bash
curl -L -o .models/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o .models/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

複製 `.env.example` 為 `.env`，填入 Blender 與（驗收用）Python 的路徑。

## 生成配音

```bash
python src/tts.py ep02_eyes_closed
python src/timeline.py ep02_eyes_closed
```

想完全重現成片的配音，可以略過 `tts.py`，把 `episodes/ep02_eyes_closed/assets/voice/` 的內容複製到 `build/ep02_eyes_closed/voice/`。

## 預覽與接觸檢查

```bash
python src/graphics.py ep02_eyes_closed
blender -b --factory-startup -P src/blender/main.py -- ep02_eyes_closed stills 30.0,42.5,89.6 --pct 40
blender -b --factory-startup -P src/blender/main.py -- ep02_eyes_closed probe --step 0.1
```

`probe` 逐時檢查角色與道具是否穿過缸壁、陷入碎石，並回報派崔克眼睛在水面下的深度。

低解析整片預覽（先烘焙，再以 1/3 解析度每兩幀渲染一張）：

```bash
python make.py ep02_eyes_closed --from graphics   # 或只跑到 bake
blender -b build/ep02_eyes_closed/scene.blend -P src/blender/main.py -- ep02_eyes_closed render 0 2699 --out frames_preview --pct 34 --step 2 --samples 8
python src/compose.py ep02_eyes_closed --preview --frames frames_preview
```

## 輸出 MP4

```bash
python make.py ep02_eyes_closed
```

成片輸出為 `output/ep02_eyes_closed.mp4`。可用 `--from <步驟>` 從中途接續（`tts|timeline|graphics|bake|render|mix|compose|verify`）。渲染可中斷後續跑：已存在的影格會略過。測試機上約每幀 8–9 秒，整集約 6–7 小時。

## 驗收結果（成片）

`verify.py` 23/23 項通過：

- H.264 High、1080×1920、固定 30 fps、正好 2700 幀；影像、音訊與容器皆為 90.000 秒；AAC 48 kHz 立體聲；完整解碼無錯誤。
- −16.2 LUFS，真峰值 −1.30 dBTP。兩段刻意的沉默比對白低約 20 dB。
- Whisper 在預定時間聽到全部 16 句完整台詞；每句黑熊先生的音高（107–116 Hz）都低於派崔克（123–178 Hz），聲線沒有互換；沒有截斷或重疊；只有兩位說話角色。
- 字幕文字與劇本一致、只用繁體字、最多兩行，最寬一行 868 px，在 900 px 安全範圍內。

另以 `probe` 每 0.1 秒檢查：沒有物件穿過缸壁或陷入碎石；頭在水下時，派崔克的眼睛位於水面下 6–8 cm。

## 已知限制

- 派崔克入水時上身前傾約 78°，頭部前伸 18 cm 並露出一小段頸部。這是為了讓圓肚子的角色能把臉放進水裡。
- 站上踏台時，第一集被吧台擋住的細腿會露出來（模型相同）。
- 手機特寫中，黑熊先生的一根手指遮住部分電池圖示；時間與「1%」仍清楚可讀。
- 嘴型依配音音量開合，不是逐音素對嘴；音樂、環境音與音效全部由程式合成。
- 驗收的「場外語音」檢查只計算對白音軌確實有聲音的字詞，因為 Whisper 會在近乎無聲的片尾虛構出「You」。
- 字幕字型依賴 Windows 的微軟正黑體；在其他系統上需改 `series/series.json` 的字型設定。
