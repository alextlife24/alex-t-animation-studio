# 本能服務｜Instinct Service — EP.01《沒有牛奶，但有亮點｜No Milk. Quite a Glow.》

▶ **成片下載：[Release instinct-service-ep01-v1.0.0](https://github.com/alextlife24/alex-t-animation-studio/releases/tag/instinct-service-ep01-v1.0.0)**（`ep01_no_milk.mp4`，42.8 MB）

90 秒直式（1080×1920、30 fps、2700 幀）低多邊形 3D 黑色幽默短片，H.264 + AAC，英文 AI 配音，燒錄繁體中文字幕。

## 故事

夜晚的森林高級西餐廳吧台。黑熊先生點了一杯「新鮮」牛奶，但冰箱裡的奶瓶是空的。收銀螢幕傳來經理的指示：「立刻現場解決。」黑熊先生理所當然地提醒調酒師派崔克：「你是哺乳動物。」派崔克只能回答：「我是公的，先生。」沉默之後，派崔克調暗燈光、拿起紫外線驗鈔燈照向自己，毛皮在光束下亮起青綠色螢光。黑熊先生完全忘了牛奶，只問：「這個要加價嗎？」

全片只有兩位出場與配音角色；經理只以收銀螢幕上的文字出現。完整分鏡與對白見 [`episodes/ep01_no_milk/script.md`](episodes/ep01_no_milk/script.md)。

## 生物冷知識與來源

- 只有雌性鴨嘴獸會分泌乳汁。派崔克是公的，片中沒有任何泌乳畫面，也沒有說這個物種不產奶。
- 鴨嘴獸毛皮在紫外線下會呈現藍綠色螢光。片中螢光只出現在紫外線照到的毛皮上，關燈後隨即消失；嘴喙、眼睛和領結不發光。片中不宣稱這種螢光在自然界的用途。
- 來源：
  - Anich, P. S. et al. (2021). Biofluorescence in the platypus (*Ornithorhynchus anatinus*). *Mammalia* 85(2). <https://doi.org/10.1515/mammalia-2020-0027>
  - Australian Museum — Platypus. <https://australian.museum/learn/animals/mammals/platypus/>

## 資料夾內容

```
make.py                    一鍵流程：配音 → 時間軸 → 圖像 → Blender 烘焙 → 渲染 → 混音 → MP4 → 驗收
series/                    系列共用設定（後續集數沿用）
  series.json              規格、字型、字幕版面、響度、色彩管理
  characters.json          角色外觀與英文配音設定（Kokoro 聲線、語速、音高、表演方向）
  set_forest_bar.json      吧台場景、道具位置、鏡頭預設
episodes/ep01_no_milk/
  script.json / script.md  劇本（段落、台詞、字幕、螢幕文字、資訊卡）
  shots.json               鏡頭表
  acting.json              表演、手部目標、道具、燈光、紫外線
  sound.json               音效、環境音、音樂與靜音段落
  subtitles.zh-Hant.srt/.ass  繁體中文字幕
  assets/voice/            成片使用的 19 句配音 WAV 與 manifest（可直接重用）
src/                       程式碼（tts、timeline、graphics、sound、compose、verify、blender/）
requirements.txt           Python 依賴（固定版本）
requirements-verify.txt    驗收用語音辨識依賴
.env.example               工具路徑設定範例（本專案不需要任何 API 金鑰）
```

## 製作工具與環境

| 工具 | 版本（實際使用） | 用途 |
|---|---|---|
| Blender | 5.2.1 LTS，OpenGL 後端 | 3D 建模、動畫、EEVEE 渲染 |
| FFmpeg | 9.0.1（需含 libx264、libass、rubberband） | 合成、字幕燒錄、編碼 |
| Python | 3.11 | 配音、時間軸、混音、驗收 |
| Kokoro v1.0 | kokoro-onnx 0.6.1（Apache-2.0，本機執行） | 英文 AI 配音 |
| faster-whisper | 1.2.1（small 模型） | 驗收時重聽成片 |

測試環境為 Windows 11（Snapdragon X、Adreno GPU）。在這張 GPU 上 Vulkan 後端會產生陰影雜訊，所以使用 OpenGL。字幕字型使用系統的微軟正黑體（`msjh.ttc` / `msjhbd.ttc`）；字型檔不收錄在儲存庫中。

## 安裝

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
python src/tts.py ep01_no_milk
python src/timeline.py ep01_no_milk
```

`tts.py` 會把每句台詞生成到 `build/ep01_no_milk/voice/`，並印出實際長度；台詞或聲線沒變的句子會沿用快取。`timeline.py` 會檢查台詞是否重疊或超出段落，並產生嘴型曲線與字幕檔。

想完全重現成片的配音，可以略過 `tts.py`，把 `episodes/ep01_no_milk/assets/voice/` 的內容複製到 `build/ep01_no_milk/voice/`。

## 預覽

渲染指定秒數的靜態畫面（40% 解析度，數秒一張）：

```bash
python src/graphics.py ep01_no_milk
blender -b --factory-startup -P src/blender/main.py -- ep01_no_milk stills 9.6,74.0,89.6 --pct 40
```

畫面輸出到 `build/ep01_no_milk/stills/`。參數 `cams` 可改為每個鏡頭預設各出一張。

渲染尚未完成時，也能用現有影格組出整片預覽（缺少的影格以最近的影格代替）：

```bash
python src/compose.py ep01_no_milk --preview
```

## 輸出 MP4

```bash
python make.py ep01_no_milk
```

依序執行配音、時間軸、圖像、烘焙、渲染、混音、合成與驗收，成片輸出為 `output/ep01_no_milk.mp4`。可用 `--from <步驟>` 從中途接續（`tts|timeline|graphics|bake|render|mix|compose|verify`）。渲染可中斷後續跑：已存在的影格會略過；要重渲染某段，刪除那段影格即可。

在測試機上渲染約每幀 8 秒，整集約 6 小時。`verify.py` 會檢查規格、響度、台詞完整性（Whisper）、聲線、字幕，並輸出 `build/ep01_no_milk/verify/` 下的接觸表。

## 已知限制

- 製作時沒有參考影片，視覺依文字描述建立。
- 角色由剛體低多邊形零件組成，沒有毛髮模擬或軟體變形。
- 嘴型依配音音量開合，不是逐音素對嘴。
- AI 配音自然，但表演細膩度不及真人配音員。
- 音樂、環境音與音效全部由程式合成。
- 渲染耗時長；在部分 GPU 上 Vulkan 後端會產生陰影雜訊。
- 字幕字型依賴 Windows 的微軟正黑體；在其他系統上需改 `series/series.json` 的字型設定。
