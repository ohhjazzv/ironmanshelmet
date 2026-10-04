This is the ironman's helmet firmware we are making with phython and c++

Perception looks at the camera picture and writes down what it sees ("cup, laptop, person")
State holds everything that's true right now: what's visible, head angle, battery, mode
Assistant hears a question, reads state, asks an AI model, and speaks the answer
HUD reads state 20 times a second and draws the overlay
