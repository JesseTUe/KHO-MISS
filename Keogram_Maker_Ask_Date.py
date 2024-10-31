'''
This program will use the rgb columns created to make a keogram. It will ask for a specific date as input and then make a keogram for this specific date if rgb columns are present for that day. 
This program is based on Keogram_Maker_Past5minutes from Nicolas Martinez (UNIS & LTU) and Jesse Delbressine (UNIS & TU/e).

Jesse Delbressine (UNIS & TU/e)
'''

import os
import numpy as np
from PIL import Image
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from parameters import parameters  # Import parameters from parameters.py

# Extract parameters from parameters.py
spectrograph = parameters['device_name']
RGB_folder = parameters['RGB_folder']
keogram_dir = parameters['keogram_dir']
num_pixels_y = parameters['num_pixels_y']
num_minutes = parameters['num_minutes']

# Initialize an empty keogram with white pixels, dimensions: height = num_pixels_y, width = num_minutes and 3 channels (RGB)
def initialise_keogram():
    return np.full((num_pixels_y, num_minutes, 3), 255, dtype=np.uint8)

# Save the updated keogram with axes and units
def save_keogram_with_axes(keogram, keogram_dir, spectrograph, date_input, current_date_str):
    #Organizing by year, month, day
    current_date_dir = os.path.join(keogram_dir,current_date_str[:4], current_date_str[4:6], current_date_str[6:8])
    os.makedirs(current_date_dir, exist_ok=True)

    # Create figure for keogram with axes and units
    fig, ax = plt.subplots(figsize=(24, 10))
    #ax.imshow(keogram, aspect='auto', extent=[0, num_minutes, 90, -90]) # Here north is down on vertical axis and south up. This is incorrect, therefore the line below.
    ax.imshow(keogram, aspect = 'auto', extent= [0, num_minutes, -90, 90]) # Now south is down on vertical axis and north up. This correct I think.

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
    ax.set_xticklabels(x_labels, fontsize = 18)

    # Set y-axis ticks for elevation angle
    y_ticks = np.linspace(-90, 90, 7)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(['90° S', '60° S', '30° S', 'Zenith', '30° N', '60° N', '90° N'], fontsize = 18)

    # Save the keogram with axes (without subplots)
    keogram_filename = os.path.join(current_date_dir, f'{spectrograph}-Keogram-{current_date_str}.png')
    plt.savefig(keogram_filename)
    plt.close(fig)

# Add RGB columns to the keogram
def add_rgb_columns(keogram, date_str):
    today_RGB_dir = os.path.join(RGB_folder, date_str)
    if not os.path.exists(today_RGB_dir):
        print(f"No RGB directory found for date {date_str}.")
        return keogram

    # Looping over each minute of the day to add corresponding rgb column
    for minute in range(num_minutes):
        timestamp = datetime.strptime(date_str, '%Y/%m/%d') + timedelta(minutes=minute)
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

                keogram[:, minute:minute+1, :] = rgb_data.astype(np.uint8) # Adding the rgb column in the keogram.

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

#Main function 
def main():
    date_input = input("Enter the date for the keogram (YYYY/MM/DD): ")
    try:
        # Check if the date format is correct
        datetime.strptime(date_input, '%Y/%m/%d')
    except ValueError:
        print("Invalid date format. Please use YYYY/MM/DD.")
        return
    
    #Making the input data into YYYYMMDD format.
    current_date_str = date_input.replace('/', '')

    # Initialize the keogram
    keogram = initialise_keogram()

    # Add RGB columns for the specified date
    keogram = add_rgb_columns(keogram, date_input)

    # Save the keogram with axes
    save_keogram_with_axes(keogram, keogram_dir, spectrograph, current_date_str, current_date_str)

    print(f"Keogram for {date_input} has been created successfully.")

if __name__ == "__main__":
    main()
