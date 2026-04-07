import pyttsx3

engine = pyttsx3.init()  # try driverName='sapi5' if needed
voices = engine.getProperty('voices')
print("Voices found:")
for i, v in enumerate(voices):
    print(i, v.id)

engine.setProperty('rate', 180)
engine.setProperty('volume', 1.0)
engine.setProperty('voice', voices[0].id)

engine.say("Hello. This is a py t t s x three test.")
engine.runAndWait()
print("Done.")
