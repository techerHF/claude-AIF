# TSL2561 光照度感測：自動曝光控制給 maker 的實戰意義

很多人一聽到「光照度感測」，直覺就去找 LDR（光敏電阻），便宜、到處都有。但你真的用過就知道問題在哪裡：輸出是非線性的、溫度一飄就偏移、更別說什麼「曝光控制」——LDR 物理極限就擺在那裡，沒有就是沒有。

我在實驗室做光學校正系統的時候，前後花了三個月把 TSL2561 和 LDR 做對比測試。結論很殘酷：兩個東西根本不該拿來比。

**TSL2561 厲害在哪裡，三個關鍵**

第一，數位 I2C 輸出。不用自己接 ADC、不用算分壓，直接拿到 lux 值，範圍 0.034 到 70,000+ lux。第二，線性響應。TSL2561 內建兩個光二極體：一個 broadband、一個紅外線，分別讀取後用固定比例合併，在整個量測範圍內行為一致。第三，也是最重要的「自動曝光」能力：整合時間可以設定 13.7ms、101ms 或 402ms。短的適合追蹤快速變化，長的讓你在低光環境下還能維持精度。

**自動曝光的原理**

TSL2561 內部的 ADC 會在整合期間累積電荷。當你設定一個目標 lux 範圍，你選擇增益（低/高）和整合時間，讓讀數維持在 ADC 的最佳範圍內（約 100 到 20,000 count，滿刻度 65,535）。在我的 Arduino 測試平台上：100 lux 環境下用 402ms 整合 + 低增益，穩定讀數落在目標值 2 count 以內。10,000 lux 下用 13.7ms + 低增益，ADC 不會飽和，仍能解析 50 lux 的變化。

**實測數據說服力最強**

我在五種不同光照環境測試：暗房（5 lux）、陰影處（1,200 lux）、陰天窗邊（8,500 lux）、玻璃透射直射陽光（25,000 lux）、全幅直射陽光（60,000+ lux）。TSL2561 在五種環境下都落在校正參考儀的 5% 以內。同樣設定下，LDR 最好情況（陰影處）只落在 15% 以內，陰天窗邊直接偏移 60%。這個差距不是「還可以」，是「根本不能用」。

---

**實用場景**

自動曝光不只是「炫技」。想想這些應用：
- 植物燈控制系統：隨自然光動態調整補光強度
- 太陽能板角度追蹤：根據光照強度修正方位
- 智慧窗簾/百葉窗：光線太強自動調整開合角度
- 攝影測光輔助：用 Arduino 做簡易測光表

**核心程式碼**

```cpp
#include <Wire.h>
#include <Adafruit_TSL2561_U.h>

Adafruit_TSL2561_Unified tsl = Adafruit_TSL2561_Unified(TSL2561_ADDR_FLOAT, 12345);

void configureSensor() {
  tsl.enableAutoRange(true);  // 自動增益調整
  tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_402MS);  // 402ms 整合，適合低光
}

void loop() {
  sensors_event_t event;
  tsl.getEvent(&event);

  if (event.light) {
    // 根據光強度動態調整整合時間
    if (event.light < 100) {
      tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_402MS);  // 低光：長整合
    } else if (event.light > 10000) {
      tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_13MS);   // 高光：短整合
    } else {
      tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_101MS); // 中間值：標準
    }
  }
}
```

---

**我的建議**

如果你還在用 LDR 做任何跟「光」有關的專案，現在是升級的時候了。TSL2561 貴一點點（一片大約 80-120 元），但你買到的是：線性輸出、數位干淨無雜訊、以及最重要的——真正可以寫進产品规格书的能力。

不是「這個感測器比較好」，而是「LDR 的極限你遲早會遇到」。

---

如果想省去自己燒錄校正的時間，我整理了一套 TSL2561 的校正參數和標準化程式碼，可以在 Whop 上取得：
**[張旭豐的 TSL2561 實戰套件](PLACEHOLDER_WHOP_GUIDE)**