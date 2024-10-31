'''
This program asks for a date and it will then average the captured spectrograms of that day minute wise and will store them in the given directory. The averaged images are saved with the relevant metadata.
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


#Function to extract the device name (MISS1 or MISS2) from the metadata. If no metadata present, "MISS2" is returned by default.
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

#Function to average the captured spectrograms minute-wise.
def average_images(PNG_base_folder, raw_PNG_folder, selected_date, processed_minutes):
    print(f"Starting to process images for {selected_date}")

    images_by_minute = defaultdict(list)
    filename_regex = re.compile(r'^MISS2-(\d{8})-(\d{6})\.png$') # Regex pattern to match filenames with the correct structure.
    selected_date_obj = datetime.datetime.strptime(selected_date, "%Y%m%d").date()

    # Checking the raw_png_folder to find captured spectrograms.
    for root, dirs, files in os.walk(raw_PNG_folder):
        print(f"Checking directory: {root}")  # DEBUG STATEMENT: printing the checked directory.
        for filename in files:
            #print(f"Found file: {filename}")  # DEBUG STATEMENT: printing each file found. 
            filepath = os.path.join(root, filename)
            match = filename_regex.match(filename)
            if match:
                date_part, time_part = match.groups()
                image_date = datetime.datetime.strptime(date_part, "%Y%m%d").date()

                print(f"Matched Date: {date_part}, Time: {time_part}, File Date: {image_date}, Selected Date: {selected_date_obj}")  # DEBUGGING

                # Only process files matching the selected date
                if image_date == selected_date_obj:
                    minute_key = date_part + '-' + time_part[:4]
                    #print(f"Adding file to minute key: {minute_key}")  # DEBUG STATEMENT
                    images_by_minute[minute_key].append(filepath)

    print(f"Found {len(images_by_minute)} minute groups")  # DEBUG STATEMENT: printing the number of minute groups.

    #Looping through each group of spectrograms. Grouped by the minute.
    for minute_key, filepaths in images_by_minute.items():
        if len(filepaths) > 0:  # Only process if there are images.
            print(f"Processing minute: {minute_key}, with {len(filepaths)} images")  # DEBUGGING
            if minute_key not in processed_minutes:
                year, month, day, hour, minute = map(int, [minute_key[:4], minute_key[4:6], minute_key[6:8], minute_key[9:11], minute_key[11:]])
                target_utc = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)

                sum_img_array = None
                count = 0
                device_name = "MISS2"  # Default device name
                metadata = None

                # Process the image(s)
                for filepath in filepaths:
                    try:
                        #print(f"Opening image: {filepath}")  # DEBUG STATEMENT
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

                # Now check if count is greater than 0, if yes compute the average and make a 16bit image.
                if count > 0:
                    print(f"Count of images for averaging: {count}")  # DEBUG STATEMENT
                    averaged_image = (sum_img_array / count).astype(np.uint16)

                    averaged_PNG_folder = os.path.join(PNG_base_folder)#, "averaged_PNG")
                    os.makedirs(averaged_PNG_folder, exist_ok=True)

                    save_folder = os.path.join(averaged_PNG_folder, f"{year:04d}", f"{month:02d}", f"{day:02d}") # Creating subdirectories for the year, month and day if not existing.
                    os.makedirs(save_folder, exist_ok=True)

                    averaged_image_path = os.path.join(save_folder, f"{device_name}-{year:04d}{month:02d}{day:02d}-{hour:02d}{minute:02d}00.png") #Defining the filename.
                    #print(f"Saving averaged image to: {averaged_image_path}")  # DEBUG STATEMENT

                    averaged_img = Image.fromarray(averaged_image, mode='I;16')

                    pnginfo = PngImagePlugin.PngInfo() #Obtaining metadata 
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

# Get the date input from the user
selected_date = input("Enter the date (YYYYMMDD) for which to average the images: ")

# Use the parameters dictionary to get paths
raw_PNG_folder = parameters['raw_PNG_folder'] #'raw_PNG_folder' for normal spectrograms and 'rescaled_PNG_folder' for rescaled spectrograms.
PNG_base_folder = parameters['averaged_PNG_folder'] #'averaged_PNG_folder' for normal spectrograms and 'rescaled_averaged_PNG_folder' for rescaled spectrograms.

# List to keep track of processed minutes
processed_minutes = []

# Call the average_images function, starting the averaging
average_images(PNG_base_folder, raw_PNG_folder, selected_date, processed_minutes)