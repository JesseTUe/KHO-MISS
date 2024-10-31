'''
Explain here what it does.
J.J. Delbressine (TU/e & UNIS)
'''

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import rotate
from PIL import Image
import os
import re
from datetime import datetime, timedelta
from parameters import parameters  # Import parameters from parameters.py

# Extract parameters from the parameters dictionary
coeffs_sensitivity_miss1 = parameters['coeffs_sensitivity']['MISS1']
coeffs_sensitivity_miss2 = parameters['coeffs_sensitivity']['MISS2']
miss1_wavelength_coeffs = parameters['miss1_wavelength_coeffs']
miss2_wavelength_coeffs = parameters['miss2_wavelength_coeffs']
averaged_PNG_folder = parameters['averaged_PNG_folder']
processed_spectrogram_dir = parameters['processed_spectrogram_dir']
binX = parameters['binX'] # Check if the binning for that day is consistent with binning in the parameters file now!!!!!
binY = parameters['binY']


# Function to calculate wavelengths from the pixel, a.k.a. wavelength pixel relation.
def calculate_wavelength(pixel_columns, coeffs):
    wavelengths = coeffs[0] + coeffs[1] * pixel_columns + coeffs[2] * (pixel_columns ** 2)
    print(f"Calculated wavelengths: {wavelengths[:50]}...")  # Debugging: Show first 50 wavelengths
    return wavelengths

# Function to calculate calibration factor K_lambda, needed for radiometric calibration.
def calculate_k_lambda(wavelengths, coeffs):
    k_lambda = np.polyval(coeffs, wavelengths)
    print(f"Calculated k_lambda values (first 10): {k_lambda[:10]}")
    if np.any(k_lambda < 0):
        print("Warning: Negative k_lambda values detected.")  # Warning for negative k_lambda values
    return k_lambda


# Function to process and plot spectrograms
def process_and_plot_with_flip_and_rotate(image_array, spectrograph_type, save_path, timestamp_str):
    print(f"Original image shape: {image_array.shape}")
    flipped_image = np.flipud(image_array) # Flip the spectrogram
    background = np.median(flipped_image, axis=0) # Calculating background by taking the median along the columns.
    background_subtracted_image = np.clip(flipped_image - background[np.newaxis, :], 0, None) # Substract the background and clip values to ensure only positive pixel values present.
    rotated_image = rotate(background_subtracted_image, angle=90, reshape=True) # Rotating the image 90 degrees.

    # Choose the spectrograph type and apply relevant coefficients
    if spectrograph_type == "MISS1":
        wavelengths = calculate_wavelength(np.arange(rotated_image.shape[1]) * binY, miss1_wavelength_coeffs)
        k_lambda = calculate_k_lambda(wavelengths, coeffs_sensitivity_miss1)
        fov_start, fov_end = parameters['miss1_horizon_limits']
    elif spectrograph_type == "MISS2":
        wavelengths = calculate_wavelength(np.arange(rotated_image.shape[1]) * binY, miss2_wavelength_coeffs)
        k_lambda = calculate_k_lambda(wavelengths, coeffs_sensitivity_miss2)
        fov_start, fov_end = parameters['miss2_horizon_limits']
    else:
        raise ValueError("Unknown spectrograph type. Please choose 'MISS1' or 'MISS2'.")

    # Calibrate the image by multiplying with K_lambda and convert it to kR/Å
    #calibrated_image = rotated_image * k_lambda[np.newaxis, :] / 1000  # Convert to kR/Å
    #elevation_scale = np.linspace(-90, 90, fov_end - fov_start) # Elavation scale from -90 to 90 degrees.
    #spatial_avg = np.mean(calibrated_image[fov_start:fov_end, :], axis=1) # Calculate spatial average across the rows

    #Adjusting the binned FOV portion from the rotated image for spatial analysis
    fov_start_binned, fov_end_binned = fov_start // binX, fov_end // binX
    wavelength_range = wavelengths[::binY]

    #Extracting the binned FOV portion from the rotated image for spatial analysis
    binned_image = rotated_image[::binX, :: binY]
    binned_image_fov = binned_image[fov_start_binned:fov_end_binned, :] # limiting FOV within binned image.

    elevation_scale = np.linspace(fov_start, fov_end, binned_image_fov.shape[0]) # Matching the length to spatial_avg, elevation scale from -90 to 90 degrees

    # Plot the results
    fig = plt.figure(figsize=(12, 8))
    fig.suptitle(f"Processed {spectrograph_type} Spectrogram - {timestamp_str} UTC", fontsize=18)
    gs = plt.GridSpec(3, 2, width_ratios=[5, 1], height_ratios=[1, 4, 1])

    ax_main = fig.add_subplot(gs[1, 0])

    '''  #THIS CAN BE USED WHEN SPECTROGRAMS BADLY VISIBLE (TOO LITTLE LIGHT)
    # Square root transformation such that the darker values are better visible. Rescaling applied since without the spectrogram still looks quite dark.
    sqrt_calibrated_image = np.sqrt(np.clip(calibrated_image, 0, None)) # Clip in order to avoid negative values in sqrt function.
    sqrt_calibrated_image -= sqrt_calibrated_image.min() # Shifting minimum to 0.
    sqrt_calibrated_image /= sqrt_calibrated_image.max() # Scaling maximum to 1 
    '''

    #ax_main.imshow(rotated_image, cmap='gray', aspect='auto', extent=[wavelengths.min(), wavelengths.max(), 0, rotated_image.shape[0]])
    ax_main.imshow(np.sqrt(np.clip(rotated_image, 0, None)), cmap='gray', aspect='auto', extent=[wavelengths.min(), wavelengths.max(), 0, rotated_image.shape[0]])
    #ax_main.imshow(calibrated_image, cmap='gray', aspect='auto', extent=[wavelengths.min(), wavelengths.max(), 0, calibrated_image.shape[0]]) # This was the normal plotting function.
    
    tick_positions = np.linspace(fov_start_binned, fov_end_binned, num=7)
    tick_labels = ["South", "-60", "-30", "Zenith", "30", "60", "North"]
    ax_main.set_yticks(tick_positions)
    ax_main.set_yticklabels(tick_labels, fontsize = 14)
    ax_main.set_xlabel("Wavelength [Å]", fontsize=16)
    ax_main.tick_params(axis='x', labelsize = 14) # CHECK IF THIS IS CORRECT
    ax_main.set_ylabel("Elevation [Degrees]", fontsize=16)
    ax_main.grid(False)

    ax_spectral = fig.add_subplot(gs[0, 0])
    spectral_avg = np.mean(binned_image * k_lambda[np.newaxis, :len(wavelength_range)], axis = 0)/1000 # converting to kR/Å
    ax_spectral.plot(wavelength_range[:len(spectral_avg)], spectral_avg)
    ax_spectral.set_ylabel("Spectral Radiance [kR/Å]", fontsize=13)
    ax_spectral.set_title("Spectral Analysis", fontsize=16)
    ax_spectral.tick_params(axis='both', which= 'major', labelsize = 14)
    ax_spectral.grid()

    ax_spatial = fig.add_subplot(gs[1, 1])
    spatial_avg = np.mean(rotated_image[fov_start_binned:fov_end_binned,:] * k_lambda[np.newaxis, :], axis=1) / 1000 # calculating spatial average across the rows in kR/Å.
    elevation_scale = np.linspace(-90, 90, spatial_avg.shape[0]) # Representing the elevation range
    ax_spatial.plot(spatial_avg, elevation_scale)
    ax_spatial.set_xlabel("Spatial Radiance [kR/θ]", fontsize=13)
    ax_spatial.set_title("Spatial Analysis", fontsize=16)
    ax_spatial.set_yticks(np.linspace(-90, 90, num=9))
    ax_spatial.set_yticklabels(["South", "-60", "-45", "-30", "Zenith", "30", "45", "60", "North"])
    ax_spectral.tick_params(axis='both', which= 'major', labelsize = 14)
    ax_spatial.grid()

    plt.tight_layout()

    # Save the figure, including all subplots
    plt.savefig(save_path, format='png', bbox_inches='tight')
    plt.close(fig)


# Function to process all the spectrograms for the input date
def process_spectrograms_for_day(averaged_PNG_folder, processed_spectrogram_dir, input_date):
    # Parse the input date
    date_to_process = datetime.strptime(input_date, '%Y%m%d')
    start_of_day = date_to_process.replace(hour=0, minute=0, second=0, tzinfo=None)
    end_of_day = start_of_day + timedelta(days=1)

    # Walk through the average_PNG_folder 
    for root, _, files in os.walk(averaged_PNG_folder):
        for file in files:
            if file.endswith('.png'):
                match = re.search(r'(\d{8})-(\d{6})\.png', file)
                if match:
                    date_str = match.group(1)
                    time_str = match.group(2)
                    timestamp_str = f"{date_str}-{time_str}"
                    timestamp = datetime.strptime(timestamp_str, '%Y%m%d-%H%M%S')

                    # Check if the spectrogram falls within the provided date
                    if start_of_day <= timestamp < end_of_day:
                        image_path = os.path.join(root, file)
                        print(f"Processing image: {image_path}")
                        image_array = np.array(Image.open(image_path))

                        if "MISS1" in file:
                            spectrograph_type = "MISS1"
                        elif "MISS2" in file:
                            spectrograph_type = "MISS2"
                        else:
                            print("Spectrograph type not identified.")
                            continue

                        # Create folder structure and save path
                        date_folder = os.path.join(processed_spectrogram_dir, date_str[:4], date_str[4:6], date_str[6:8])
                        os.makedirs(date_folder, exist_ok=True)
                        processed_image_name = f"{spectrograph_type}-ProcessedSpectrogram-{timestamp_str}.png"
                        save_path = os.path.join(date_folder, processed_image_name)

                        # Process and save the figure
                        process_and_plot_with_flip_and_rotate(image_array, spectrograph_type, save_path, timestamp_str)
                        print(f"Processed and saved spectrogram: {save_path}")


# Main function, asking for input date.
input_date = input("Enter the date (format YYYYMMDD) for which to process spectrograms: ")
process_spectrograms_for_day(averaged_PNG_folder, processed_spectrogram_dir, input_date)


