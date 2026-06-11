import time
import max30100
from collections import deque
import firebase_admin
from firebase_admin import credentials, db

# 1. Initialize Firebase connection
cred = credentials.Certificate('serviceAccountKey.json') 

# Pass 'cred' into the initializer instead of 'None'
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bpm-monitor-f7b6a-default-rtdb.europe-west1.firebasedatabase.app/'
})

# Get a reference to the root of your database
db_ref = db.reference('/vitals')

# We will store the last 100 readings to analyze a "window" of time
BUFFER_SIZE = 100
ir_buffer = deque(maxlen=BUFFER_SIZE)
red_buffer = deque(maxlen=BUFFER_SIZE)

def calculate_vitals(ir_data, red_data):
    # 1. Calculate the DC (baseline) component
    ir_dc = sum(ir_data) / len(ir_data)
    red_dc = sum(red_data) / len(red_data)

    # 2. Calculate the AC (pulsatile) component
    ir_ac = max(ir_data) - min(ir_data)
    red_ac = max(red_data) - min(red_data)

    if ir_dc == 0 or ir_ac == 0:
        return 0, 0

    # 3. Calculate SpO2
    ratio = (red_ac / red_dc) / (ir_ac / ir_dc)
    spo2 = 110 - (25 * ratio)
    spo2 = max(0, min(100, spo2))

    # 4. Calculate a SMARTER Heart Rate (BPM)
    beat_indices = []
    
    # At 100Hz, 30 samples = 300ms. 
    # This acts as a "refractory period", capping the max readable BPM at 200.
    # It forces the code to ignore high-frequency noise spikes.
    min_distance = 30 
    samples_since_last = min_distance

    # Find the exact points where the pulse happens
    for i in range(1, len(ir_data)):
        samples_since_last += 1
        
        # Check if the signal crosses the average line going UP
        if ir_data[i-1] < ir_dc and ir_data[i] >= ir_dc:
            # Only register a beat if enough time has passed since the last one
            if samples_since_last >= min_distance:
                beat_indices.append(i)
                samples_since_last = 0

    # If we found at least 2 valid beats in this window, measure the time between them
    if len(beat_indices) >= 2:
        intervals = []
        for i in range(1, len(beat_indices)):
            intervals.append(beat_indices[i] - beat_indices[i-1])
            
        avg_interval = sum(intervals) / len(intervals)

        # The sensor runs at 100Hz, so 1 sample = 0.01 seconds.
        # BPM = 60 seconds / (average interval in seconds)
        bpm = 60 / (avg_interval * 0.01)
        bpm = bpm / 2.2
    else:
        # If no full heartbeat was detected in this 1-second window, output 0
        bpm = 0

    return bpm, spo2

def main():
    print("Initializing MAX30100 for Vitals...")
    mx30 = max30100.MAX30100()
    mx30.enable_spo2()
    
    print("Place your finger on the sensor.")
    print("Collecting data... (Waiting for buffer to fill)")
    print("-" * 40)
    
    try:
        while True:
            mx30.read_sensor()
            
            # Add new readings to the right side of our buffer
            ir_buffer.append(mx30.ir)
            red_buffer.append(mx30.red)
            
            # Only calculate vitals once we have a full window of 100 samples
            if len(ir_buffer) == BUFFER_SIZE:
                bpm, spo2 = calculate_vitals(list(ir_buffer), list(red_buffer))
                
                # Print the results
                # We format it to 1 decimal place for cleaner reading
                print(f"BPM: {bpm:.1f} | SpO2: {spo2:.1f}%")
                anaphylaxis_alert = False
                if bpm > 120 and spo2 < 92 and bpm > 0:
                    anaphylaxis_alert = True
                    print("⚠️ WARNING: Thresholds indicate Anaphylactic Shock condition!")
                # -----------------------------------------------

                try:
                    db_ref.set({
                        'bpm': round(bpm, 1),
                        'spo2': round(spo2, 1),
                        'anaphylaxis_alert': anaphylaxis_alert, # Send the alert flag to the cloud
                        'timestamp': time.time()
                    })
                except Exception as cloud_err:
                    print(f"Cloud upload skipped: {cloud_err}")
                # Clear half the buffer so we wait a moment before the next calculation,
                # creating a smooth "rolling window" effect.
                for _ in range(BUFFER_SIZE // 2):
                    ir_buffer.popleft()
                    red_buffer.popleft()
            
            # The MAX30100 samples at 100Hz, so we sleep for 10ms (0.01s)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping sensor...")
        mx30.set_mode(max30100.MODE_SPO2_OFF)

if __name__ == '__main__':
    main()
