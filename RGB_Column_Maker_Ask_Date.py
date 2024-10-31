'''
This program is based on RGB_Column_Maker_Past5Minutes.py. It will ask for a specific date as input and for this date RGB columns will be made.

Jesse Delbressine (UNIS & TU/e)
'''
#THIS PROGRAM IS STILL WORK IN PROGRESS ;)
import os
import numpy as np
from scipy import signal
from PIL import Image
from datetime import datetime, timezone
from parameters import parameters  # Import parameters from parameters.py
from scipy.ndimage import zoom  # For ensuring that RGB column has the correct shape.

# Extract paths and constants from parameters.py
spectro_path = parameters['spectro_path']
output_folder_base = parameters['RGB_folder']
miss1_wavelength_coeffs = parameters['miss1_wavelength_coeffs']
miss2_wavelength_coeffs = parameters['miss2_wavelength_coeffs']
coeffs_sensitivity_miss1 = parameters['coeffs_sensitivity']['MISS1']
coeffs_sensitivity_miss2 = parameters['coeffs_sensitivity']['MISS2']
miss1_horizon_limits = parameters['miss1_horizon_limits']
miss2_horizon_limits = parameters["miss2_horizon_limits"]


# Function to calculate pixel position from wavelength using spectral fit coefficients and binning factor
def calculate_pixel_position(wavelength, coeffs, max_pixel_value, binY):
    print(f"C0={coeffs[0]}, C1={coeffs[1]}, C2={coeffs[2]}")
    #discriminant = coeffs[1]**2 - 4 * coeffs[2] * (coeffs[0] - wavelength) # Quadratic formula.
    #discriminant = coeffs[1]**2 - 4 * coeffs[0] * (coeffs[2] - wavelength) #This is what was in Nicolas his code
    ''' 
    if discriminant < 0:
        print(f"No real solution for wavelength {wavelength}, discriminant < 0.")
        return None
    sqrt_discriminant = np.sqrt(discriminant) # Calculating pixel position and adjusting for binning factor.
    #pixel_position = (-coeffs[1] + sqrt_discriminant) / (2 * coeffs[2])
    pixel_position = (-coeffs[1] + sqrt_discriminant) / (2 * coeffs[0])
    '''
    pixel_position = (coeffs[1] + 2078 * coeffs[2] - np.sqrt(coeffs[1]**2 - 4 * coeffs[0] * coeffs[2] + 4 * coeffs[2] * wavelength)) / (2 * coeffs[2])
    binned_pixel_position = pixel_position / binY
    if 0 <= binned_pixel_position <= max_pixel_value: # Ensuring the pixel position is within the range.
        return binned_pixel_position
    else:
        print(f"Calculated pixel position {binned_pixel_position} is out of valid range.")
        return None

# Ensure directory exists before trying to open or save
def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        print(f"Creating directory: {directory}")
        os.makedirs(directory)
    else:
        print(f"Directory already exists: {directory}")

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

# Read the PNG image, apply binning correction and extract metadata
def read_png_with_metadata(filename, binX, binY):
    with Image.open(filename) as img:
        raw_data = np.array(img)
        metadata = img.info
        corrected_data = zoom(raw_data, (binY, binX), order = 1) # order = 1 applies bilinear interpolation.
    return corrected_data, metadata


# Extracting the binning factors from the metadata.
def extract_binning_from_metadata(metadata):
    try:
        binning_info = metadata.get("Binning", "1x1")
        binX, binY = map(int, binning_info.split('x'))
        return binX, binY
    except Exception as e:
        print(f"Error extracting binning factor from metadata: {e}")
        return None, None 

# Function to calculate calibration factor K_lambda, needed for radiometric calibration.
def calculate_k_lambda(wavelengths, coeffs):
    return np.polyval(coeffs, wavelengths)

# Process and average emission line rows
def process_emission_line(spectro_array, emission_row, binY, pixel_range, min_rows_for_average=2):
    print(f"Processing emission line for row {emission_row} with binY {binY}")
    num_rows_to_average = max(1, int(12 / binY)) # Determining number of rows to average based on binning factor. 
    start_row = max(0, emission_row - binY // 2) # Defining start and end rows for the region of interest.
    end_row = min(spectro_array.shape[0], emission_row + num_rows_to_average // 2 + 1)
    available_rows = end_row - start_row
    if available_rows < min_rows_for_average:
        print(f"Not enough rows for averaging at row {emission_row}, ({available_rows}<{min_rows_for_average})")
        return None
    
    # Crop and process the region of interest from the spectrogram.
    spectro_array_cropped = spectro_array[:, pixel_range[0]:pixel_range[1]]
    extracted_rows = spectro_array_cropped[start_row:end_row, :]

    #Apply median filter smoothing out the rows and average the rows.
    processed_rows = signal.medfilt2d(extracted_rows.astype('float32'))
    averaged_row = np.mean(processed_rows, axis=0)

    # Rescale the averaged row to fit the desired columns size (300 pixels)
    rescaled_row = zoom(averaged_row, (300 / len(averaged_row)))
    print(f"Processed emission line for row {emission_row}")
    return rescaled_row.flatten()

# Create RGB column from emission line data 
def create_rgb_column(spectro_array, row_6300, row_5577, row_4278, binY, pixel_range, k_lambda_6300, k_lambda_5577, k_lambda_4278):
    column_RED = process_emission_line(spectro_array, row_6300, binY, pixel_range) # Process red, green and blue channels from emission lines
    column_GREEN = process_emission_line(spectro_array, row_5577, binY, pixel_range)
    column_BLUE = process_emission_line(spectro_array, row_4278, binY, pixel_range)
    
    if column_RED is None or column_GREEN is None or column_BLUE is None:
        print(f"Image will be skipped due to missing emission line data.")
        return None
    
    def scale_channel(channel_data): 
        min_val = np.min(channel_data)
        max_val = np.max(channel_data)
        range_val = max_val - min_val
        return np.clip(((channel_data - min_val) / range_val) * 255, 0, 255).astype(np.uint8) if range_val != 0 else np.zeros_like(channel_data, dtype=np.uint8)
    
    
    # Scale and reshape each channel
    column_RED = scale_channel(column_RED).reshape(300, 1)
    column_GREEN = scale_channel(column_GREEN).reshape(300, 1)
    column_BLUE = scale_channel(column_BLUE).reshape(300, 1)
    true_rgb_image = np.stack((column_RED, column_GREEN, column_BLUE), axis=-1) # Stack channels to form final rgb column.
    if true_rgb_image.shape != (300, 1, 3):
        print(f"Error: RGB image has an incorrect shape {true_rgb_image.shape}. Expected shape: (300, 1, 3)")
        return None
    print(f"Succesfull created RGB column.")
    return true_rgb_image

# Process images to create RGB columns for a specific date, MAIN function.
def create_rgb_columns_for_date(date_str):
    print(f"Processing images for date: {date_str}")
    spectro_path_dir = os.path.join(spectro_path, date_str)
    ensure_directory_exists(spectro_path_dir)
    output_folder = os.path.join(output_folder_base, date_str)
    ensure_directory_exists(output_folder)
    matching_files = [f for f in os.listdir(spectro_path_dir) if f.endswith(".png")]
    if not matching_files:
        print(f"No PNG files found for {date_str} => SKIPPING")
        return
    for filename in matching_files:
        png_file_path = os.path.join(spectro_path_dir, filename)
        if not verify_image_integrity(png_file_path):
            print(f"Skipping corrupted image: {filename}")
            continue
        try:
            spectro_data, metadata = read_png_with_metadata(png_file_path, 1, 1) # (1,1) used as placeholders. They are replaced with actual value later.
            binX, binY = extract_binning_from_metadata(metadata)
            print(f" binX = {binX} and binY = {binY}")
            if binX is None or binY is None:
                print(f"Skipping file due to failed binning factor extraction {filename}")
                continue
            spectro_data, metadata = read_png_with_metadata(png_file_path, binX, binY) # Reloading spectro_data with the actual binning values

            if "MISS1" in filename:
                pixel_range = miss1_horizon_limits
                coeffs = miss1_wavelength_coeffs 
            elif "MISS2" in filename:
                pixel_range = miss2_horizon_limits
                coeffs = miss2_wavelength_coeffs
            else:
                continue
            emission_wavelengths = [6300, 5577, 4278] # Define emission wavelengths for auroral lines. 
            max_pixel_value = spectro_data.shape[0] - 1 
            row_6300 = calculate_pixel_position(emission_wavelengths[0], coeffs, max_pixel_value, binY) # Calculate row positions for each emission line
            row_5577 = calculate_pixel_position(emission_wavelengths[1], coeffs, max_pixel_value, binY)
            row_4278 = calculate_pixel_position(emission_wavelengths[2], coeffs, max_pixel_value, binY)
            if None in (row_6300, row_5577, row_4278):
                continue

            # Round pixel positions to nearest integer. Fit lambda(pixel_row) is starting from last pixel!!!
            #row_6300 = max_pixel_value - int(round(row_6300)) 
            #row_5577 = max_pixel_value - int(round(row_5577))
            #row_4278 = max_pixel_value - int(round(row_4278))

            row_6300 = int(round(row_6300)) 
            row_5577 = int(round(row_5577))
            row_4278 = int(round(row_4278))


            # Determine k_lambda for each emission line (Radiometric calibration) 
            k_lambda_6300 = calculate_k_lambda(6300, coeffs_sensitivity_miss2)
            k_lambda_5577 = calculate_k_lambda(5577, coeffs_sensitivity_miss2)
            k_lambda_4278 = calculate_k_lambda(4278, coeffs_sensitivity_miss2)

            RGB_image = create_rgb_column(spectro_data, row_6300, row_5577, row_4278, binY, pixel_range, k_lambda_6300, k_lambda_5577, k_lambda_4278)
            if RGB_image is None:
                continue
            RGB_pil_image = Image.fromarray(RGB_image.astype('uint8'), mode='RGB')
            resized_RGB_image = RGB_pil_image.resize((1, 300), Image.LANCZOS)

            filename_without_ext, ext = os.path.splitext(filename)
            output_filename = f"{filename_without_ext}_RGB.png"
            output_path = os.path.join(output_folder, output_filename)
            resized_RGB_image.save(output_path)
            print(f"Saved RGB image: {output_filename}")
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

# Main loop to prompt user for date and process images
def main():
    print("Starting the program.")
    while True:
        try:
            date_str = input("Enter the date for RGB columns (YYYY/MM/DD): ").strip() # Asking the date for which the RGB columns need to be made.
            datetime.strptime(date_str, "%Y/%m/%d") # Checking if date format is correct.
            create_rgb_columns_for_date(date_str) #Calling the function to create the RGB columns

        except ValueError:
            print(f" Invalid date format: Please enter the date in 'YYYY/MM/DD' format") #If the date is incorrectly entered.

        except Exception as e:
            print(f"Other error occured: {e}")
        
        continue_processing = input("Do you want to process another date? (yes/no):").strip().lower() #Asking for another date to process
        if continue_processing != 'yes':
            print("Exiting program, 10 seconds to detonation.")
            break

#Calling the main script.
if __name__ == "__main__":
    main()
