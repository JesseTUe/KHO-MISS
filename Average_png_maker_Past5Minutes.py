'''
This program will average the captured spectrograms minute wise for the last 5 minutes of the current day. The averaged images are saved with the relevant metadata.
This program is based on "Average_PNG_Maker.py" made by Nicolas Martinez (UNIS/LTU).

Jesse Delbressine (TU/e & UNIS)
'''

import os
import datetime
import numpy as np
from PIL import Image, PngImagePlugin
import re
from collections import defaultdict
from parameters import parameters  # Import the parameters dictionary


# Function to extract the device name (MISS1 or MISS2) from the metadata. If no metadata present, "MISS2" is returned by default.
def get_device_name_from_metadata(filepath):
    try:
        img = Image.open(filepath)
        metadata = img.info
        note = metadata.get("Note", "")
        if note:
            match = re.search(r'(MISS\d)', note)
            if match:
                return match.group(1)
        return "MISS2"  # Default to "MISS2" if no device name is found
    except Exception as e:
        print(f"Error reading metadata from {os.path.basename(filepath)}: {e}")
        return "MISS2"  # Default to "MISS2" in case of error

#Function to average the captured spectrograms of the last 5minutes. They are averaged minute wise.
def average_images(PNG_base_folder, raw_PNG_folder, processed_minutes):
    # Use the current date and time in UTC
    current_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"Starting to process images for {current_time.strftime('%Y%m%d')} at {current_time.strftime('%H:%M:%S')}")

    # Calculate the time 5 minutes ago
    time_5_minutes_ago = current_time - datetime.timedelta(minutes=5)

    images_by_minute = defaultdict(list)
    filename_regex = re.compile(r'^MISS2-(\d{8})-(\d{6})\.png$')  # Regex for the PNG file pattern
    current_date_str = current_time.strftime("%Y%m%d")

    # Set the folder for the current day
    raw_PNG_folder_today = os.path.join(raw_PNG_folder, current_date_str[:4], current_date_str[4:6], current_date_str[6:])

    # Walk through the raw PNG folder of the current day
    for root, dirs, files in os.walk(raw_PNG_folder_today):
        print(f"Checking directory: {root}")  # DEBUG STATEMENT
        for filename in files:
            print(f"Found file: {filename}")  # DEBUG STATEMENT
            filepath = os.path.join(root, filename)
            match = filename_regex.match(filename)
            if match:
                date_part, time_part = match.groups()
                image_time = datetime.datetime.strptime(f"{date_part}-{time_part}", "%Y%m%d-%H%M%S").replace(tzinfo=datetime.timezone.utc)

                # Only process images from the last 5 minutes
                if time_5_minutes_ago <= image_time <= current_time:
                    minute_key = date_part + '-' + time_part[:4]  # Group by minute
                    print(f"Adding file to minute key: {minute_key}")  # DEBUGGING
                    images_by_minute[minute_key].append(filepath)

    print(f"Found {len(images_by_minute)} minute groups within the last 5 minutes")  # DEBUGGING

    # Process images minute-wise
    for minute_key, filepaths in images_by_minute.items():
        if len(filepaths) > 0:  # Only process if there are images
            print(f"Processing minute: {minute_key}, with {len(filepaths)} images")  # DEBUGGING
            if minute_key not in processed_minutes:
                year, month, day, hour, minute = map(int, [minute_key[:4], minute_key[4:6], minute_key[6:8], minute_key[9:11], minute_key[11:]])
                target_utc = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)

                sum_img_array = None
                count = 0
                device_name = "MISS2"  # Default device name
                metadata = None

                # Process each image
                for filepath in filepaths:
                    try:
                        print(f"Opening image: {filepath}")  # DEBUGGING
                        img = Image.open(filepath)
                        img_array = np.array(img)
                        print(f"Image shape: {img_array.shape}")  # CHECKING image array shape

                        if sum_img_array is None:
                            sum_img_array = np.zeros_like(img_array, dtype='float64')

                        sum_img_array += img_array
                        count += 1

                        # Get metadata from the first image only
                        if metadata is None:
                            metadata = img.info

                    except Exception as e:
                        print(f"Error processing image {os.path.basename(filepath)}: {e}")

                # Average the images and save if count > 0
                if count > 0:
                    print(f"Count of images for averaging: {count}")  # DEBUGGING
                    averaged_image = (sum_img_array / count).astype(np.uint16)

                    averaged_PNG_folder = os.path.join(PNG_base_folder)
                    os.makedirs(averaged_PNG_folder, exist_ok=True)

                    save_folder = os.path.join(averaged_PNG_folder, f"{year:04d}", f"{month:02d}", f"{day:02d}")
                    os.makedirs(save_folder, exist_ok=True)

                    averaged_image_path = os.path.join(save_folder, f"{device_name}-{year:04d}{month:02d}{day:02d}-{hour:02d}{minute:02d}00.png")
                    print(f"Saving averaged image to: {averaged_image_path}")  # DEBUGGING

                    averaged_img = Image.fromarray(averaged_image, mode='I;16')

                    pnginfo = PngImagePlugin.PngInfo()
                    if metadata:
                        for key, value in metadata.items():
                            if key in ["Exposure Time", "Date/Time", "Temperature", "Binning", "Note"]:
                                pnginfo.add_text(key, str(value))
                        pnginfo.add_text("Note", f"1-minute average image. {metadata.get('Note', '')}")
                    else:
                        pnginfo.add_text("Note", "1-minute average image.")

                    try:
                        averaged_img.save(averaged_image_path, pnginfo=pnginfo)
                        print(f"Saved averaged image with metadata: {averaged_image_path}")  # DEBUGGING
                    except Exception as e:
                        print(f"Error saving averaged image: {e}")

                    processed_minutes.append(minute_key)  # Keep track of processed minute keys
                else:
                    print(f"No images processed for minute: {minute_key}")  # DEBUGGING
        else:
            print(f"Skipping processing for minute: {minute_key}, with 0 images")  # DEBUGGING

# Use the parameters dictionary to get paths
raw_PNG_folder = parameters['raw_PNG_folder']
PNG_base_folder = parameters['averaged_PNG_folder']

# List to keep track of processed minutes
processed_minutes = []

# Call the average_images function for the current date and last 5 minutes
average_images(PNG_base_folder, raw_PNG_folder, processed_minutes)