'''
MAIN SPECTROGRAM PROCESSING PROGRAM: Launches and makes sure all involved scripts are active (minute-averaged spectrogram 
with spectral and spatial analysis and keogram based on latest available data from MISS 1 or 2 updated live). 

1. Initialise a list to track subprocesses.
2. Define a function to terminate all subprocesses safely (ctrl + C).
3. Launche multiple subprocesses (keogram maker, RGB column maker, average PNG maker, kho_website_feed, spectrogram processor, and Feeder).
4. Enter a loop to keep processes running, checking every 60 seconds.
5. On interrupt, stop all subprocesses and exits.

Author: Nicolas Martinez (UNIS/LTU)

Updated by Jesse Delbressin (UNIS & TU/e)
'''

import signal
import subprocess
import os
import time

processes = []  # List to keep track of all subprocesses
running = True  # Manage the while loop

#This function will stop all subprocesses.
def stop_processes(processes, timeout=5):
    for process in processes:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()

# This function will handle an interrupt signal to safely stop the program.
def signal_handler(sig, frame):
    global running
    running = False
    print("Interrupt received, stopping processes...")
    stop_processes(processes)
    exit(0)

#This function will start a subprocess
def start_subprocess(script_name):
    base_dir = os.path.expanduser("~/.venvMISS2/MISS2/MISS_SOFTWARE-PACKAGE") # This directory needs to be adjusted accordingly.
    script_path = os.path.join(base_dir, script_name)
    print(f"Starting process: {script_name}")
    #process = subprocess.Popen(["python3", script_path]) # python3 used on Linux, for Windows "python" command is used.
    process = subprocess.Popen(["python", script_path])
    return process

#This function will verify that all subprocesses are running.
def verify_processes(processes):
    all_running = True
    for process in processes:
        if process.poll() is not None:
            print(f"Process {process.pid} has stopped.")
            all_running = False
    return all_running

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    #In order to let the subprocesses start right away and not wait the 300s before it starts.
    processes.append(start_subprocess("Average_png_maker_Past5Minutes.py"))
    time.sleep(10)
    processes.append(start_subprocess("Spectrogram_Processor_Past5Minutes.py"))
    time.sleep(10)
    processes.append(start_subprocess("RGB_Column_Maker_Past5Minutes.py"))
    time.sleep(10)
    processes.append(start_subprocess("Keogram_Maker_Past5Minutes.py"))
    time.sleep(10)

    
    last_execution_time = time.time()

    try:
        while running:
            current_time = time.time()
            if current_time - last_execution_time >= 300: #300s wait for the next iteration.
                last_execution_time = current_time

                # Stop and clear existing processes
                stop_processes(processes)
                processes = []

                # Start new processes
                processes.append(start_subprocess("Average_png_maker_Past5Minutes.py"))
                time.sleep(10)
                processes.append(start_subprocess("Spectrogram_Processor_Past5Minutes.py"))
                time.sleep(10)
                processes.append(start_subprocess("RGB_Column_Maker_Past5Minutes.py"))
                time.sleep(10)
                processes.append(start_subprocess("Keogram_Maker_Past5Minutes.py"))
                #processes.append(start_subprocess("KHO_WEBSITE_DATA-FEED.py"))
                #processes.append(start_subprocess("Routine_eraser.py"))

                if verify_processes(processes): # Confirming that all subprocesses have started.
                    print("All subprocesses started successfully.")
                else:
                    print("One or more subprocesses failed to start.")

            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        stop_processes(processes)
