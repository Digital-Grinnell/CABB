# Function 12: Process TIFFs & Create JPG Derivatives

## Purpose
This function processes TIFF files from their original locations, copies them to the `For-Import` directory, and creates JPG derivatives. It updates a CSV file with the filenames of both the JPG (file_name_1) and TIFF (file_name_2) for each object.

## How It Works

### Input Sources
1. **TIFF Location CSV**: `all_single_tiffs_with_local_paths.csv` - contains MMS IDs and local file paths for TIFF files
2. **MMS IDs**: Either a single MMS ID or a set of MMS IDs
3. **Optional Export CSV**: Path to alma_export CSV file (from Set ID field), or a new one will be created

### Process Flow
1. Reads `all_single_tiffs_with_local_paths.csv` to build a mapping of MMS ID → Local Path
2. For each MMS ID to process:
   - Locates the TIFF file using the Local Path
   - Copies the TIFF to `For-Import/` directory
   - Creates a JPG derivative (quality=95) in the same directory
   - Updates the CSV with:
     - `file_name_1`: JPG basename
     - `file_name_2`: TIFF basename

### Error Handling
- If a TIFF file is missing, logs an error and continues
- If file copy fails (e.g., network volume disconnected), logs error and continues
- If JPG creation fails, logs error and continues
- Creates `process_tiffs_failures.csv` with details of any failures

## Usage

### Single MMS ID Mode
1. Enter a single MMS ID in the MMS ID field
2. (Optional) Enter path to alma_export CSV in the Set ID field
3. Click "Process TIFFs & Create JPG Derivatives"

### Set Mode
1. Load a set using "Fetch Set Members"
2. (Optional) Enter path to alma_export CSV in the Set ID field
3. Click "Process TIFFs & Create JPG Derivatives"

## Output

### Files Created
- **For-Import/[basename].tif**: Copy of original TIFF
- **For-Import/[basename].jpg**: JPG derivative at quality=95
- **alma_export_[timestamp].csv**: CSV with file_name_1 and file_name_2 columns populated
- **process_tiffs_failures.csv**: (if errors occur) List of failed operations

### Progress Tracking
The function shows:
- Progress bar with percentage complete
- Current/total record count
- Status messages for each operation
- Summary of successful and failed operations

## Requirements
- `all_single_tiffs_with_local_paths.csv` must exist
- TIFF files must be accessible at the paths specified in the CSV
- Pillow library must be installed for JPG conversion

## Notes
- JPG quality is set to 95 for high-quality derivatives
- Original TIFF files are not modified, only copied
- Network volume disconnections may cause failures; check `process_tiffs_failures.csv`
- Progress is saved incrementally to the CSV file

## Recent Fixes (February 2026)

### 16-bit TIFF Conversion Fix
**Problem**: JPG derivatives were being created with correct dimensions but blank/white content when source TIFFs were 16-bit grayscale images.

**Root Cause**: 16-bit images (mode `I;16`) have pixel values ranging from 0-65,535. Direct conversion to 8-bit RGB was not properly scaling these values down to the 0-255 range required by JPG format, resulting in blank images.

**Solution**: Added proper bit-depth scaling for 16-bit images:
```python
if img.mode in ('I', 'I;16', 'I;16B', 'I;16L', 'I;16N'):
    # Properly scale 16-bit to 8-bit by dividing by 256
    img = img.point(lambda x: x / 256).convert('L').convert('RGB')
```

This divides pixel values by 256 (65,535 / 256 ≈ 255) before converting to 8-bit grayscale, then to RGB.

**Files Updated**:
- `app.py` (lines ~3032)
- `process_tiffs_for_import.py` (lines ~90)

### Status Message Improvements
**Changes**:
1. Changed "CSVs updated" to "CSV rows updated" for clarity (updating rows in one CSV, not multiple CSVs)
2. Added CSV filename to status message: `"100 CSV rows updated in alma_export_20260216_143052.csv"`
3. Fixed Set ID field being incorrectly interpreted as CSV filename when it contains an Alma set ID number
   - Now only treats Set ID field as CSV path if it contains `.csv`, `/`, or `\` characters
   - Otherwise generates timestamped filename automatically

**Example Status Messages**:
- Before: `"Function 12 complete: 100 TIFFs processed, 100 CSVs updated, 0 failed, 0 no path"`
- After: `"Function 12 complete: 100 TIFFs processed, 100 CSV rows updated in alma_export_20260216_143052.csv, 0 failed, 0 no path"`
