/*
 * Detox Arduino Serial Example 
 */

#include <Arduino.h>

void setup() {
  Serial.begin(9600);  // start serial for output
  Serial.println("Hello, World!");
}

void loop() {
  static int i = 0;
  Serial.print("Loop ***: ");
  Serial.println(i++);
}
