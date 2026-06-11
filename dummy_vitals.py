import time
import firebase_admin
from firebase_admin import credentials, db
import random

# Initialize Firebase connection using your credentials file
cred = credentials.Certificate('serviceAccountKey.json') 
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bpm-monitor-f7b6a-default-rtdb.europe-west1.firebasedatabase.app/'
})

db_ref = db.reference('/vitals')

print("==================================================")
print("   MAX30100 VITALS SIMULATOR FOR SCHOOL PRESENTATION")
print("==================================================")
print("Streaming live to Firebase... Press Ctrl+C to stop.\n")

state = "NORMAL"
counter = 0

try:
    while True:
        counter += 1
        
        # Switch states every 15 seconds so you can show off both conditions to your teacher
        if counter % 15 == 0:
            if state == "NORMAL":
                state = "SHOCK"
                print("\n EMERGENCY ACTIVATED: Simulating Anaphylactic Shock! ")
            else:
                state = "NORMAL"
                print("\n SYSTEM STABILIZED: Reverting to Normal Vitals... ")

        # Generate realistic dummy data based on the selected state
        if state == "NORMAL":
            bpm = random.uniform(72.0, 78.0)    # Normal resting heart rate
            spo2 = random.uniform(97.0, 99.5)   # Healthy oxygen levels
            alert = False
        else:
            bpm = random.uniform(128.0, 142.0)  # Tachycardia (>120 BPM)
            spo2 = random.uniform(86.0, 90.5)   # Hypoxia (<92% SpO2)
            alert = True

        print(f"[{state}] Sending -> BPM: {bpm:.1f} | SpO2: {spo2:.1f}% | Alert Triggered: {alert}")

        # Push to the cloud database
        db_ref.set({
            'bpm': round(bpm, 1),
            'spo2': round(spo2, 1),
            'anaphylaxis_alert': alert,
            'timestamp': time.time()
        })

        # Pushes data at a clean, readable 1-second interval
        time.sleep(1)

except KeyboardInterrupt:
    print("\nSimulator stopped safely.")
