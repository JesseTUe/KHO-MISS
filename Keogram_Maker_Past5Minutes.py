"""
This program uses RGB image-columns generated every 5 minutes using the spectrograms captured by MISS* to update a daily keogram.
At 00:00 UTC, a new keogram for the day is created (empty). At 00:05 UTC, the previous day's keogram receives its last update,
and the new day's keogram receives its first update.

The script ensures only available past data is used for analysis. The RGB channels are named according to the three main
emission lines of the aurora: 

- **Red channel**: 6300 Å (Oxygen emission line)
- **Green channel**: 5577 Å (Oxygen emission line)
- **Blue channel**: 4278 Å (Nitrogen emission line)

Author: Nicolas Martinez (UNIS/LTU)

Updated by Jesse Delbressine (UNIS & TU/e)

"""

import os
import numpy as np
from PIL import Image
from datetime import datetime, timezone, timedelta
import matplotlib.pyplot as plt
import time
from parameters import parameters  # Import parameters from parameters.py

# Extract parameters from parameters.py
spectrograph = parameters['device_name']
RGB_folder = parameters['RGB_folder']
keogram_dir = parameters['keogram_dir']
num_pixels_y = parameters['num_pixels_y']
num_minutes = parameters['num_minutes']


# Initialise an empty keogram with white pixels,  dimensions: height = num_pixels_y, width = num_minutes and 3 channels (RGB)
def initialise_keogram():
    return np.full((num_pixels_y, num_minutes, 3), 255, dtype=np.uint8)


# Save the updated keogram with axes and units
def save_keogram_with_axes(keogram, keogram_dir, spectrograph, date_input):
    current_date_str = datetime.now().strftime('%Y%m%d')

    # Organizing by year, month and day
    current_date_dir = os.path.join(keogram_dir, current_date_str[:4], current_date_str[4:6], current_date_str[6:8])
    os.makedirs(current_date_dir, exist_ok=True)

    # Create figure for keogram with axes and units
    fig, ax = plt.subplots(figsize=(24, 10))
    ax.imshow(keogram, aspect='auto', extent=[0, num_minutes, -90, 90]) # South is down on vertical axis and north up

    # Set correct title format for the keogram
    spectrograph_title = "I" if spectrograph == "MISS1" else "II"
    ax.set_title(f"Meridian Imaging Svalbard Spectrograph {spectrograph_title} {date_input}", fontsize=28)

    # Set axis labels and ticks
    ax.set_xlabel("Time (UT)", fontsize=20)
    ax.set_ylabel("Elevation angle [degrees]", fontsize=20)

    # Set x-axis ticks for time (every 2 hours)
    x_ticks = np.arange(0, num_minutes + 1, 120)
    x_labels = [(datetime(2024, 1, 1) + timedelta(minutes=int(t))).strftime('%H:%M') for t in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, fontsize = 24)

    # Set y-axis ticks for elevation angle
    y_ticks = np.linspace(-90, 90, 7)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(['90° S', '60° S', '30° S', 'Zenith', '30° N', '60° N', '90° N'], fontsize = 24)

    # Save the keogram with axes (without subplots) on this computer.
    keogram_filename = os.path.join(current_date_dir, f'{spectrograph}-keogram-{current_date_str}.png')
    plt.savefig(keogram_filename)

    # Save the keogram with axes and upload it to KHO website.
    #keogram_filename2 = os.path.join('Z:\\kho\\MISS2', 'latest-keogram.png') # Directory needs to be changed for MISS1.
    #plt.savefig(keogram_filename2)
    
    plt.close(fig)

# Add all available RGB columns from 00:00 UTC to now(current UTC time) to the keogram
def add_rgb_columns(keogram, date_str, now):
    today_RGB_dir = os.path.join(RGB_folder, date_str)
    if not os.path.exists(today_RGB_dir):
        print(f"No RGB directory found for date {date_str}.")
        return keogram

    #Start from 00:00 UTC
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Determining how many minutes have passed since 00:00 UTC
    minutes_passed = int((now - start_time).total_seconds() // 60)

    # Loop through all the RGB columns from 00:00UTC to current UTC
    for minute in range(minutes_passed):
        timestamp = start_time + timedelta(minutes=minute)
        filename = f"{spectrograph}-{timestamp.strftime('%Y%m%d-%H%M00')}_RGB.png"
        file_path = os.path.join(today_RGB_dir, filename)

        if os.path.exists(file_path) and verify_image_integrity(file_path):
            try:
                rgb_data = np.array(Image.open(file_path))

                # Validate the shape of the image data
                if rgb_data.shape != (num_pixels_y, 1, 3):
                    print(f"Unexpected image shape {rgb_data.shape} for {filename}. Expected ({num_pixels_y}, 1, 3). Skipping this image.")
                    continue

                # Debugging info: Check the min and max values of the loaded RGB data
                print(f"Processing {filename} - Min: {rgb_data.min()}, Max: {rgb_data.max()}")
                
                keogram[:, minute:minute+1, :] = rgb_data.astype(np.uint8)

            except Exception as e:
                print(f"Error processing {filename}: {e}")

        else:
            print(f"File {file_path} does not exist or is corrupted.")
    return keogram

# Verify if the image is intact
def verify_image_integrity(file_path):
    try:
        with Image.open(file_path) as img:
            img.verify()
        with Image.open(file_path) as img:
            img.load()
        return True
    except Exception as e:
        print(f"Corrupted PNG detected: {file_path} - {e}")
        return False

# Main function
def main():
    # Get current time in UTC and formatting it as yyyy/mm/dd
    now = datetime.now(timezone.utc)
    date_input = now.strftime('%Y/%m/%d')
    current_date_str = now.strftime('%Y%m%d')

    # Initialize the keogram
    keogram = initialise_keogram()

    # Add RGB columns from 00:00 UTC to now
    keogram = add_rgb_columns(keogram, date_input, now)

    # Save the keogram with axes
    save_keogram_with_axes(keogram, keogram_dir, spectrograph, date_input)

    print(f"Keogram for {date_input} has been created successfully.")

if __name__ == "__main__":
    main()
