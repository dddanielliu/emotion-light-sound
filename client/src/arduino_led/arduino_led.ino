#include <FastLED.h>
#include <WString.h> // For String class, though often included by default

// --- 燈條定義 ---
#define NUM_LEDS 432     // PIN 6 漸變燈條的 LED 數量
#define DATA_PIN 6      // PIN 6 (漸變燈條)

// --- CRGB 陣列定義 ---
CRGB leds[NUM_LEDS];

// Define emotion colors as constants
const CRGB COLOR_ANGRY = CRGB(255, 0, 0);       // Red
const CRGB COLOR_FEAR = CRGB(128, 0, 128);      // Purple
const CRGB COLOR_NEUTRAL = CRGB(255, 255, 255); // White
const CRGB COLOR_SAD = CRGB(0, 0, 255);         // Blue
const CRGB COLOR_DISGUST = CRGB(0, 255, 0);     // Green
const CRGB COLOR_HAPPY = CRGB(255, 255, 0);     // Yellow
const CRGB COLOR_SURPRISE = CRGB(255, 165, 0);  // Orange

// Global variables for color transition
CRGB currentColor = COLOR_NEUTRAL; // Start with neutral
CRGB targetColor = COLOR_NEUTRAL;
CRGB startColor = COLOR_NEUTRAL;
unsigned long transitionStartTime = 0;
const unsigned long transitionDuration = 1500; // 1.5 seconds (1500 milliseconds)

void setup() {
  // --- 註冊所有 LED 燈條 ---
  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(255); // Set maximum brightness

  Serial.begin(115200); // Initialize serial communication at 115200 baud
  Serial.setTimeout(2000); // Set a timeout of 2000ms for serial reading functions
  while (!Serial) { 
    ; // Wait for serial port to connect. Needed for native USB port only
  }

  // Initialize all LEDs to the neutral color
  fill_solid(leds, NUM_LEDS, currentColor);
  FastLED.show();
}

void loop() {
  // Handle incoming serial data
  if (Serial.available()) {
    String emotion = Serial.readStringUntil('\n');
    emotion.trim(); // Remove any leading/trailing whitespace

    // Convert emotion to lowercase for case-insensitive matching
    emotion.toLowerCase();

    // Determine targetColor based on emotion string using if-else if
    CRGB newTargetColor;
    bool emotionRecognized = true;

    if (emotion == "angry") {
      newTargetColor = COLOR_ANGRY; // Red
    } else if (emotion == "fear") {
      newTargetColor = COLOR_FEAR; // Purple
    } else if (emotion == "neutral") {
      newTargetColor = COLOR_NEUTRAL; // White
    } else if (emotion == "sad") {
      newTargetColor = COLOR_SAD; // Blue
    } else if (emotion == "disgust") {
      newTargetColor = COLOR_DISGUST; // Green
    } else if (emotion == "happy") {
      newTargetColor = COLOR_HAPPY; // Yellow
    } else if (emotion == "surprise") {
      newTargetColor = COLOR_SURPRISE; // Orange
    } else {
      Serial.print("Unknown emotion received: ");
      Serial.println(emotion);
      // try to use partual data to guess the emotion
      if (emotion[0] == 'a') {
        newTargetColor = COLOR_ANGRY; // Red
        Serial.println("guessed from partial: angry");
      }
      else if (emotion[0] == 'f') {
        newTargetColor = COLOR_FEAR; // Purple
        Serial.println("guessed from partial: fear");
      }
      else if (emotion[0] == 'n') {
        newTargetColor = COLOR_NEUTRAL; // White
        Serial.println("guessed from partial: neutral");
      }
      else if (emotion[0] == 's') {
        if (emotion.length() > 1 && emotion[1] == 'a') {
          newTargetColor = COLOR_SAD; // Blue
          Serial.println("guessed from partial: sad");
        }
        else if (emotion.length() > 1 && emotion[1] == 'u') {
          newTargetColor = COLOR_SURPRISE;
          Serial.println("guessed from partial: surprise");
        }
      }
      else if (emotion[0] == 'd') {
        newTargetColor = COLOR_DISGUST; // Green
        Serial.println("guessed from partial: disgust");
      }
      else if (emotion[0] == 'h') {
        newTargetColor = COLOR_HAPPY; // Yellow
        Serial.println("guessed from partial: happy");
      }
      else {
        emotionRecognized = false;
      }
    }

    if (emotionRecognized) {
      // A new valid emotion is received, start a new transition
      startColor = currentColor; // Current color becomes the start of the new transition
      targetColor = newTargetColor;
      transitionStartTime = millis(); // Reset the transition timer
      Serial.print("Received: "); // Echo back the received emotion
      Serial.println(emotion);
    }
  }

  // Handle color transition
  unsigned long currentTime = millis();
  unsigned long elapsedTime = currentTime - transitionStartTime;

  if (elapsedTime < transitionDuration) {
    // Transition is active
    // Calculate progress as a float from 0.0 to 1.0
    float progress = (float)elapsedTime / transitionDuration;
    // FastLED's blend function takes fract8 (0-255) for amount
    currentColor = blend(startColor, targetColor, (uint8_t)(progress * 255));
  } else {
    // Transition is complete or not active, ensure we are at the target color
    currentColor = targetColor;
  }

  // Update all LEDs with the current color
  fill_solid(leds, NUM_LEDS, currentColor);

  // Show the updated colors on the LED strip
  FastLED.show();

  // Small delay to prevent busy-waiting and allow serial buffer to fill
  // and other background tasks to run. Adjust as needed.
  delay(10);
}
