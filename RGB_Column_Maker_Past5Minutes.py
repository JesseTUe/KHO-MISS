"""
This script will look for averaged spectrograms from the past five minutes (PNG 16-bit) by MISS1 or MISS2 and produces
(300, 1, 3) RGB PNG files (8-bit unsigned integer) based on the spectral calibration data auroral emission lines at specific wavelengths.
All RGB columns are then saved timely for live or ulterior keogram creation. 60 * 24 = 1440 RGB columns per daily keogram.

- **Red channel**: 6300 Å (Oxygen emission line)
- **Green channel**: 5577 Å (Oxygen emission line)
- **Blue channel**: 4278 Å (Nitrogen emission line)

Nicolas Martinez (UNIS/LTU) 2024

Jesse Delbressine (UNIS & TU/e)
"""

import os
import numpy as np
from scipy import signal
from PIL import Image
from datetime import datetime, timezone, timedelta
import time
from parameters import parameters  # Import parameters from parameters.py

# Extract paths and constants from parameters.py
spectro_path = parameters['spectro_path']
output_folder_base = parameters['RGB_folder']
miss1_wavelength_coeffs = parameters['miss1_wavelength_coeffs']  # Coefficients as is
miss2_wavelength_coeffs = parameters['miss2_wavelength_coeffs']  # Coefficients as is
coeffs_sensitivity_miss1 = parameters['coeffs_sensitivity']['MISS1']
coeffs_sensitivity_miss2 = parameters['coeffs_sensitivity']['MISS2']
miss1_horizon_limits = parameters['miss1_horizon_limits']
miss2_horizon_limits = parameters['miss2_horizon_limits']

processed_images = set()
current_day = datetime.now(timezone.utc).day

# Function to calculate pixel position from wavelength using the spectral fit coefficients and binning factor
def calculate_pixel_position(wavelength, coeffs, max_pixel_value, binY):
    print(f" Calculating the pixel position for wavelength {wavelength}... ")
    #Using wavelength pixel relation
    discriminant = coeffs[1]**2 - 4 * coeffs[2] * (coeffs[0] - wavelength) # Quadratic formula
    
    if discriminant < 0:
        print(f"No real solution for wavelength {wavelength}, discriminant < 0.")
        return None
    
    sqrt_discriminant = np.sqrt(discriminant)
    pixel_position = (-coeffs[1] + sqrt_discriminant) / (2 * coeffs[2])

    # Pixel position adjusted for the binning factor
    binned_pixel_position = pixel_position / binY

    # Check if the calculated binned pixel position is within the valid range
    if 0 <= binned_pixel_position <= max_pixel_value:
        return binned_pixel_position
    else:
        print(f"Calculated pixel position {binned_pixel_position} is out of valid range for wavelength {wavelength}")
        return None

# Ensure directory exists before trying to open or save
def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# Verify image integrity
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

# Read the PNG image and extract metadata
def read_png_with_metadata(filename, binX, binY):
    with Image.open(filename) as img:
        raw_data = np.array(img)
        metadata = img.info  # Extract metadata
        corrected_data = zoom(raw_data, (binY, binX), order = 1)
    return corrected_data, metadata

# Extract binning factor from metadata (use binY)
def extract_binning_from_metadata(metadata):
    try:
        binning_info = metadata.get("Binning", "1x1")
        binX, binY = map(int, binning_info.split('x'))
        return binX, binY
    except Exception as e:
        print(f"Error extracting binning factor from metadata: {e}")
        return None

# Function to calculate calibration factor K_lambda, needed for radiometric calibration.
def calculate_k_lambda(wavelengths, coeffs):
    return np.polyval(coeffs, wavelengths)

# Process the emission line rows in the spectrogram and average them.
def process_emission_line(spectro_array, emission_row, binY, pixel_range, min_rows_for_average=2):
    num_rows_to_average = max(1, int(12 / binY))
    start_row = max(emission_row - num_rows_to_average // 2, 0)
    #end_row = min(emission_row + num_rows_to_average // 2, spectro_array.shape[0])
    end_row = min(spectro_array.shape[0], emission_row + num_rows_to_average // 2 + 1)


    # Check if enough rows are available for averaging
    available_rows = end_row - start_row
    if available_rows < min_rows_for_average:
        print(f"Not enough rows for averaging at row {emission_row}, ({available_rows}<{min_rows_for_average})")
        return None
    
    # Crop the array to the desired pixel range (columns)
    spectro_array_cropped = spectro_array[:, pixel_range[0]:pixel_range[1]]
    extracted_rows = spectro_array_cropped[start_row:end_row, :]
    
    #Apply a median filter
    processed_rows = signal.medfilt2d(extracted_rows.astype('float32'))
    averaged_row = np.mean(processed_rows, axis=0)

    # Rescale the averaged row to fit 300 pixels
    rescaled_row = zoom(averaged_row, (300 / len(averaged_row)))  # Maybe this causes the error?
    return rescaled_row.flatten()

# Function to create the RGB image from the extracted rows
def create_rgb_column(spectro_array, row_6300, row_5577, row_4278, binY, pixel_range, k_lamba_6300, k_lambda_5577, k_lambda_4278 ):
    # Process each emission line and extract the corresponding rows
    column_RED = process_emission_line(spectro_array, row_6300, binY, pixel_range)
    column_GREEN = process_emission_line(spectro_array, row_5577, binY, pixel_range)
    column_BLUE = process_emission_line(spectro_array, row_4278, binY, pixel_range)

    if column_RED is None or column_GREEN is None or column_BLUE is None:
        print(f"Image will be skipped due to missing emission line data.")
        return None
        
    #Applying k_lambda
    column_RED = column_RED * k_lambda_6300
    column_GREEN = column_GREEN * k_lambda_5577
    column_BLUE = column_BLUE * k_lambda_4278

    
    def scale_channel(channel_data, scale_factor): # Scale factor is now set to one, change accordingly for hopefully better colours.
        min_val = np.min(channel_data)
        max_val = np.max(channel_data)
        range_val = max_val - min_val
        print(f"Channel min value: {min_val}, max value: {max_val}, range: {range_val}")
        return np.clip(((channel_data - min_val) / range_val) * 255 *scale_factor, 0, 255).astype(np.uint8) if range_val != 0 else np.zeros_like(channel_data, dtype=np.uint8)
    
    
    # Scale and reshape each channel
    scaled_red_channel = scale_channel(column_RED, scale_factor=1).reshape(300, 1)
    scaled_green_channel = scale_channel(column_GREEN, scale_factor=1).reshape(300, 1)
    scaled_blue_channel = scale_channel(column_BLUE,scale_factor=1).reshape(300, 1)
    

    # Combine the individually scaled channels into the final RGB image
    true_rgb_image = np.stack((scaled_red_channel, scaled_green_channel, scaled_blue_channel), axis=-1)

    true_rgb_image_flipped = np.flipud(true_rgb_image) # Flipping the RGB column since I thought they were upside down.
    if true_rgb_image_flipped.shape != (300, 1, 3):
        print(f"Error: RGB image has an incorrect shape {true_rgb_image_flipped.shape}. Expected shape: (300, 1, 3)")
        return None
    print(f"Succesfull created RGB column.")
    return true_rgb_image_flipped

# Process images to create RGB columns, main function
def create_rgb_columns():
    global processed_images, current_day

    current_time_UT = datetime.now(timezone.utc)
    five_minutes_ago = current_time_UT - timedelta(minutes=5)

    # Clear processed images set if it's a new day
    if current_time_UT.day != current_day:
        processed_images.clear()
        current_day = current_time_UT.day

    # Ensuring the directories exists
    spectro_path_dir = os.path.join(spectro_path, current_time_UT.strftime("%Y/%m/%d"))
    ensure_directory_exists(spectro_path_dir)
    
    output_folder = os.path.join(output_folder_base, current_time_UT.strftime("%Y/%m/%d"))
    ensure_directory_exists(output_folder)

    matching_files = [f for f in os.listdir(spectro_path_dir) if f.endswith(".png")] # Finding all the files in the directory.

    if not matching_files:
        print("No PNG files found to process => SKIPPING")
        return

    for filename in matching_files:
        png_file_path = os.path.join(spectro_path_dir, filename)

        # Check if the file was modified within the last 5 minutes
        file_mod_time = datetime.utcfromtimestamp(os.path.getmtime(png_file_path)).replace(tzinfo=timezone.utc)
        if file_mod_time < five_minutes_ago:
            print(f"Skipping {filename}, it is older than 5 minutes.")
            continue

        if not verify_image_integrity(png_file_path):
            print(f"Skipping corrupted image: {filename}")
            continue

        try:

            # Read image and extract metadata
            spectro_data, metadata = read_png_with_metadata(png_file_path, 1, 1) # (1,1) used as placeholders. They are replaced with actual value later.
            binX, binY = extract_binning_from_metadata(metadata)
            print(f" binX = {binX} and binY = {binY}")

            if binX is None or binY is None:
                print(f"Skipping file due to failed binning factor extraction {filename}")
                continue
            spectro_data, metadata = read_png_with_metadata(png_file_path, binX, binY) #Reloading spectro_data with the actual binning values

      

        # Determine the spectrograph type (MISS1 or MISS2) from the filename
        if "MISS1" in filename:
            pixel_range = miss1_horizon_limits
            coeffs = miss1_wavelength_coeffs
            coeffs_sensitivity = coeffs_sensitivity_miss1
        elif "MISS2" in filename:
            pixel_range = miss2_horizon_limits
            coeffs = miss2_wavelength_coeffs
            coeffs_sensitivity = coeffs_sensitivity_miss2
        else:
            print(f"Unknown spectrograph type for {filename}")
            continue

        # Define emission line wavelengths in Angstroms
        emission_wavelengths = [6300, 5577, 4278]  # Adjust wavelengths as needed [Å]

        # Calculate the pixel positions (rows) for each emission line
        max_pixel_value = spectro_data.shape[0] - 1  # Maximum valid pixel index (rows)
        row_6300 = calculate_pixel_position(emission_wavelengths[0], coeffs, max_pixel_value, binY)
        row_5577 = calculate_pixel_position(emission_wavelengths[1], coeffs, max_pixel_value, binY)
        row_4278 = calculate_pixel_position(emission_wavelengths[2], coeffs, max_pixel_value, binY)

       if row_6300 is None or row_5577 is None or row_4278 is None:
                print(f"Skipping {filename} due to missing emission line data.")
                continue

        # Round pixel positions to nearest integer. Fit lambda(pixel_row) is starting from last pixel!!!
        row_6300 = max_pixel_value - int(round(row_6300))
        row_5577 = max_pixel_value - int(round(row_5577))
        row_4278 = max_pixel_value - int(round(row_4278))

        # Calculate k_lambda values for each emission line to apply calibration
        k_lambda_6300 = calculate_k_lambda(6300, coeffs_sensitivity)
        k_lambda_5577 = calculate_k_lambda(5577, coeffs_sensitivity)
        k_lambda_4278 = calculate_k_lambda(4278, coeffs_sensitivity)

        # Use calculated rows and k_lambda values to create RGB columns
        RGB_image = create_rgb_column(
            spectro_data, row_6300, row_5577, row_4278, binY, pixel_range, 
            k_lambda_6300, k_lambda_5577, k_lambda_4278)

        if RGB_image is None:
            print(f"RGB column creation failed for {filename}")
            continue
            
        RGB_pil_image = Image.fromarray(RGB_image.astype('uint8'), mode='RGB')
        resized_RGB_image = RGB_pil_image.resize((1, 300), Image.LANCZOS)

       # Save the RGB image
        rgb_filename = filename.replace(".png", "_RGB.png")
        rgb_image_output_path = os.path.join(output_folder, rgb_filename)
        resized_RGB_image.save(rgb_image_output_path)
        print(f"Saved RGB image: {rgb_image_output_path}")

    except Exception as e:
        print(f"Failed to process {filename}: {e}")


if __name__ == "__main__":
    create_rgb_columns()
