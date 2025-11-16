#include <FastLED.h>

// --- 燈條定義 ---
#define NUM_LEDS 432     // PIN 6 漸變燈條的 LED 數量
#define DATA_PIN 6      // PIN 6 (漸變燈條)

#define GRADIENT_SPEED 200 

// --- CRGB 陣列定義 ---
CRGB leds[NUM_LEDS];       // PIN 6 (漸變燈條)

unsigned char R = 255;
unsigned char G = 0;
unsigned char B = 0;

// PIN 6 漸變邏輯
bool reverseGradient = true; 
static int phase = 0; 
static int pos = 0;   
static int reversePhase = 0; 


void setup() {
  // --- 註冊所有 LED 燈條 ---
  // PIN 6: 漸變燈條 (使用原始 leds 陣列)
  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS); 
  
  FastLED.setBrightness(255); 
}

void loop() {
  
  // 設置當前顏色 (用於 PIN 6)
  CRGB currentColor;

  // --- PIN 6 漸變邏輯 (與您原始程式碼相同) ---
  if (reverseGradient) {
    // === 實作 Red -> Blue -> Green -> Yellow -> Red 順序 ===
    
    pos += 1; 
    if (pos > 255) {
      pos = 0;
      reversePhase = (reversePhase + 1) % 4;
    }

    R = 0; G = 0; B = 0; 

    if (reversePhase == 0) { // Red -> Blue (R 減 B 增)
      R = 255 - pos;
      B = pos;
    } 
    else if (reversePhase == 1) { // Blue -> Green (B 減 G 增)
      B = 255 - pos;
      G = pos;
    }
    else if (reversePhase == 2) { // Green -> Yellow (G 保持 R 增)
      G = 255;
      R = pos;
    }
    else if (reversePhase == 3) { // Yellow -> Red (R 保持 G 減)
      R = 255;
      G = 255 - pos;
    }
    
    currentColor = CRGB(R, G, B);

  } else {
    // === 實作標準 Red -> Yellow -> Green 順序 ===
    
    pos += 1; 
    if (pos > 255) {
      pos = 0;
      phase = (phase + 1) % 6;
    }
    
    R = 0; G = 0; B = 0; 
    
    if (phase == 0) { R=255; G=pos; }        // R->Y
    else if (phase == 1) { G=255; R=255-pos; } // Y->G
    else if (phase == 2) { G=255; B=pos; }    // G->C
    else if (phase == 3) { B=255; G=255-pos; } // C->B
    else if (phase == 4) { B=255; R=pos; }    // B->M
    else if (phase == 5) { R=255; B=255-pos; } // M->R
    
    currentColor = CRGB(R, G, B);
  }

  // --- 顯示 PIN 6 漸變顏色 ---
  fill_solid(leds, NUM_LEDS, currentColor);
  
  // 呼叫 show() 會更新所有已註冊的燈條
  FastLED.show();
  delay(GRADIENT_SPEED); 
}
