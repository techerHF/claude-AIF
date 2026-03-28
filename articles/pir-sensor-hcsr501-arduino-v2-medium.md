非會員可以透過這個連結免費閱讀：[Medium 朋友連結]

---

# PIR 感測器入門：用 HC-SR501 和 Arduino 做出你第一個動作偵測裝置

![PIR 動作感測器安裝在牆面的實體照](https://upload.wikimedia.org/wikipedia/commons/0/0e/Schneider_Electric_PIR_motion_detector.JPG "PIR 動作感測器")
*圖片來源：Wikimedia Commons / CC BY-SA 3.0*

---

## 你要做的是什麼

你要做的是這樣一個東西：

有人走進它的感測範圍，LED 亮。那個人離開，LED 滅。

這不只是一顆會亮的 LED。這是一個能感知到人的裝置。走廊燈、保全警報器、野生動物相機，背後用的都是同樣的邏輯。你現在要從最基礎的版本開始做起。

整個過程大概 30 分鐘。你需要的元件一顆 NT$20 就能買到。

---

## 動手前，先知道你選的是什麼感測器，為什麼

你要做的這件事，用幾種不同的感測器都能做到。但每種感測器偵測的東西不一樣，適合的情況也不一樣。

| 方案 | 感知的是什麼 | 最適合的情況 | 功耗 | 成本 |
|------|------------|-------------|------|------|
| **PIR** | 人體熱輻射移動 | 偵測有沒有人在動，低功耗裝置 | 極低 | 低 |
| 超聲波 | 聲波反射距離 | 測距、障礙物偵測 | 低 | 低 |
| 微波雷達 | 多普勒效應 | 穿牆偵測、細微動作感測 | 中 | 中 |
| 相機 + AI | 影像 | 人臉辨識、複雜場景 | 高 | 高 |

你今天的需求是「有沒有人在動」，不需要知道距離多遠、也不需要穿牆，用 PIR 是最直接的選擇。

PIR 最大的優點是被動偵測，它不發出任何東西，只是接收。這讓它的待機功耗幾乎可以忽略，電池供電的裝置可以撐好幾年。

---

## 你需要什麼

![HC-SR501 PIR 感測器模組，白色圓頂為菲涅爾透鏡](https://upload.wikimedia.org/wikipedia/commons/6/6f/PIR_Motion_Sensor-Sensinova_%28SN-PR11%29.png "HC-SR501 PIR 感測器模組")
*圖片來源：Wikimedia Commons / CC BY-SA 4.0*

- HC-SR501 PIR 感測器模組 × 1（[Amazon 連結]）
- Arduino Uno × 1（[Amazon 連結]）
- 麵包板 × 1（[Amazon 連結]）
- 杜邦線（公對公、公對母各幾條）（[Amazon 連結]）

HC-SR501 蝦皮也買得到（[蝦皮連結]），搜尋「HC-SR501」就有，一顆大概 NT$20-50。

---

## PIR 是怎麼感知到你的

這件事說起來比想像中直接。

PIR 的全名是 Passive Infrared，被動紅外線。被動是說它不主動發出任何東西，只是接收。接收的是你身體的熱，也就是紅外線輻射。

人體溫度大約 36 到 37°C，這個溫度會持續向外輻射波長約 9 到 10 微米的紅外線。你眼睛看不到，但 PIR 感測元件對這個波長很敏感。這就是為什麼走廊全暗，它還是能偵測到你。

---

## 感測器裡面在做什麼

![PIR 感測器電路板內部，可以看到感測元件與訊號處理電路](https://upload.wikimedia.org/wikipedia/commons/7/7d/Toom_motion_detector_-_board_-_Pollin_PIR_D203S-2662.jpg "PIR 感測器電路板內部")
*圖片來源：Wikimedia Commons / CC BY-SA 4.0*

HC-SR501 的感測元件裡有兩個並排的熱電堆（Pyroelectric Element）。

想像兩個人並排坐著，各自感受周圍的溫度。平常沒有熱源移動的時候，兩個人感受到的溫度差不多，沒有訊號。

你走過去的時候，你的熱先掃到左邊那個人，再掃到右邊那個人。這個先後差異讓感測器輸出 HIGH，也就是「偵測到了」。

你停下來不動，兩個人都感受到你的熱了，差異消失，訊號回到 LOW。

所以 PIR 感測的不是「有熱在那裡」，是「熱在移動」這件事。

這就解釋了一個很常見的問題：走廊站著不動，幾秒後燈滅了。不是感測器壞了，是你靜止後它真的感覺不到你了。

感測元件前面那顆白色圓頂是菲涅爾透鏡（Fresnel Lens）。它把來自各個方向的紅外線聚焦到感測元件上，讓偵測角度達到 120 度，感測距離最遠 7 公尺。

---

## 接線方式

![走廊裝有 PIR 感測器的牆壁開關，展示實際應用場景](https://upload.wikimedia.org/wikipedia/commons/c/cd/Light_switch_with_passive_infrared_sensor.jpg "PIR 感測器實際安裝在牆壁開關上")
*圖片來源：Wikimedia Commons / CC BY-SA 4.0*

HC-SR501 只有三個腳位，接線很簡單：

| HC-SR501 腳位 | Arduino 腳位 |
|--------------|-------------|
| VCC | 5V |
| GND | GND |
| OUT | D2 |

模組上有兩個旋鈕：
- 左邊旋鈕：靈敏度，控制偵測距離（3 到 7 公尺可調）
- 右邊旋鈕：延遲時間，控制觸發後訊號維持多久

兩個旋鈕先轉到中間位置就好，之後再根據實際需要微調。

接線模擬器（互動式）：https://wokwi.com/projects/459724505742791681

> 打開連結可以直接在瀏覽器裡執行電路模擬，不需要實體元件。

---

## 程式碼

```cpp
const int PIR_PIN = 2;   // OUT 腳位接在 D2
const int LED_PIN = 13;  // 使用 Arduino 內建 LED 測試

void setup() {
  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);

  // HC-SR501 上電後需要約 30 秒校正環境背景紅外線
  // 這段時間 LED 可能會亂閃，是正常的，等它穩定
  Serial.println("等待感測器暖機...");
  delay(30000);
  Serial.println("就緒，開始偵測");
}

void loop() {
  int state = digitalRead(PIR_PIN);

  if (state == HIGH) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("偵測到動作");
  } else {
    digitalWrite(LED_PIN, LOW);
  }

  delay(100);
}
```

上傳程式後，打開 Serial Monitor（Tools > Serial Monitor，鮑率設 9600）。

等 30 秒之後，你會看到「就緒，開始偵測」出現在 Serial Monitor 裡。在感測器前面揮手，Serial Monitor 應該出現「偵測到動作」，LED 同時亮起。手移開等幾秒，LED 滅，訊息停止。

---

## 可能遇到的問題

**Q：上電後 LED 一直亂閃，程式是不是有問題？**
A：沒問題。HC-SR501 上電後需要 30 到 60 秒校正環境的背景紅外線值，這段時間它會反覆誤觸發。`delay(30000)` 讓程式等這段時間過去再開始偵測。如果 30 秒後還是一直閃，把延遲時間旋鈕往左轉到最小值再試。

**Q：揮手沒反應，感測器是不是壞的？**
A：先檢查兩件事：一、接線有沒有接錯（VCC 接 5V、GND 接 GND、OUT 接 D2）。二、靈敏度旋鈕是不是轉到最小值了，往右轉增加靈敏度。如果接線和旋鈕都沒問題，打開 Serial Monitor 確認是否顯示「就緒，開始偵測」，如果還在顯示暖機訊息，繼續等。

**Q：LED 亮了很快就滅了，怎麼調整維持時間？**
A：把延遲時間旋鈕（右邊那個）往右轉，讓觸發後的訊號維持更久。

---

## 你做出來的這個東西還能往哪裡走

你現在手上有一個能感知到人的裝置。LED 亮滅是最直接的反應，但觸發的不一定要是 LED。

用同樣的邏輯，換掉觸發的東西，可以做到這些：
- 有人靠近就拍照，儲存到 SD card（野生動物相機的基本邏輯）
- 5 分鐘沒有動作就觸發蜂鳴器（進入警戒模式）
- 偵測到人就記錄時間戳記，追蹤一天裡有人的時段

每一個方向都不複雜，但每一步都需要知道在那個點上怎麼設計觸發邏輯和程式結構。

![相機陷阱捕捉到大峽谷黑熊，這類裝置用的是和你今天一樣的 PIR 觸發邏輯](https://upload.wikimedia.org/wikipedia/commons/1/19/Grand_Canyon_National_Park_Black_Bear_%22Camera_Trapped%22_0067_%287456310532%29.jpg "相機陷阱拍到的大峽谷黑熊")
*圖片來源：Grand Canyon National Park / CC BY 2.0*

這張照片是用相機陷阱（Camera Trap）拍的。它用的就是和你今天做的東西一樣的邏輯：PIR 感測到熱源移動，相機觸發拍照。把你的 LED 換成相機模組，加上儲存邏輯，就是同樣的東西。

完整的執行步驟、code 邏輯拆解，還有三個可以直接做的進階方向，在這個 project pack 裡：[Whop 單品連結]

如果你想要持續追蹤感測器選型思路、互動概念和 project pack 的更新，可以加入 Interactive Sensor Vault：[Whop 會員連結]
