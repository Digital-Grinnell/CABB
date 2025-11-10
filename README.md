# Alma-D Bulk Bib Records Editor

A Flet-based single-page UI application designed to perform various Alma-Digital bibliographic record editing functions using the Alma API and the [almapipy](https://github.com/UCDavisLibrary/almapipy) library.

## Features

The application provides five editing functions for Alma-Digital bibliographic records:

1. **Clear dc:relation Collections Fields** - Removes all dc:relation fields having a value that begins with "alma:01GCL_INST/bibs/collections/"
2. **Placeholder Function 2** - Reserved for future Alma-Digital record editing functionality
3. **Placeholder Function 3** - Reserved for future Alma-Digital record editing functionality
4. **Placeholder Function 4** - Reserved for future Alma-Digital record editing functionality
5. **Placeholder Function 5** - Reserved for future Alma-Digital record editing functionality

## Technology Stack

- **Flet** - Modern Python framework for building user interfaces
- **almapipy** - Python wrapper for the Ex Libris Alma API
- **python-dotenv** - Environment variable management
- **Python 3.x** - Programming language

## Project Structure

```
Alma-D-Bulk-Bib-Records-Editor/
├── app.py              # Main Flet application
├── requirements.txt    # Python dependencies
├── run.sh             # Quick launch script
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- An Alma API key with appropriate permissions

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/Digital-Grinnell/Alma-D-Bulk-Bib-Records-Editor.git
   cd Alma-D-Bulk-Bib-Records-Editor
   ```

2. **Configure environment variables**
   
   Copy the example environment file and edit it with your Alma API credentials:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Alma API key:
   ```
   ALMA_API_KEY=your_actual_api_key_here
   ALMA_API_URL=https://api-na.hosted.exlibrisgroup.com
   ```

3. **Run the application**
   
   Use the provided quick launch script:
   ```bash
   ./run.sh
   ```
   
   The script will:
   - Create a virtual environment (`.venv`) if it doesn't exist
   - Install all required dependencies
   - Launch the Flet application

## Manual Installation (Alternative)

If you prefer to set up manually:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

## Usage

1. **Launch the application** using `./run.sh`

2. **Connect to Alma API**
   - Click the "Connect to Alma API" button
   - The status will show if the connection is successful

3. **Enter a record MMS ID**
   - Input the bibliographic record's MMS ID in the text field

4. **Execute editing functions**
   - Click any of the five function buttons to perform operations on the specified record
   - The status area will display the result of each operation

## Development

### Project Development Log

#### Initial Setup (2024)
- Created project structure with virtual environment support
- Implemented Flet-based single-page UI
- Integrated almapipy library for Alma API connectivity
- Created five function placeholders with corresponding UI buttons

#### Function 1: Clear dc:relation Collections
- Implemented placeholder for clearing dc:relation fields
- Pattern matching: `alma:01GCL_INST/bibs/collections/*`
- Uses XML parsing for record manipulation
- Note: Full implementation requires actual XML manipulation logic

#### Architecture Decisions
- **Single-page design**: All functionality on one page for simplicity
- **Class-based architecture**: `AlmaBibEditor` class encapsulates all business logic
- **Environment variables**: API keys stored securely in `.env` file
- **Virtual environment**: Isolated Python environment for dependency management

### Code Structure

#### `app.py`
The main application file containing:
- `AlmaBibEditor` class: Handles Alma API interactions
- `main(page)` function: Builds the Flet UI
- Event handlers for each button
- Status update mechanisms

#### Key Functions

**`initialize_alma_connection()`**
- Establishes connection to Alma API using almapipy
- Validates API key from environment variables
- Returns success status and message

**`clear_dc_relation_collections(mms_id)`**
- Main implementation for Function 1
- Fetches bibliographic record by MMS ID
- Parses XML to find and remove matching dc:relation fields
- Updates the record via Alma API

**Placeholder Functions 2-5**
- Reserved for future functionality
- Follow same pattern: accept MMS ID, return status tuple
- Ready for implementation of additional editing features

### Adding New Functions

To implement additional editing functions:

1. Add a method to the `AlmaBibEditor` class
2. Create an event handler in the `main()` function
3. Add a button to the UI
4. Update the README with the new functionality

Example:
```python
def new_editing_function(self, mms_id: str) -> tuple[bool, str]:
    """Description of new function"""
    # Implementation here
    return True, "Success message"
```

## Dependencies

See `requirements.txt` for complete list:
- `flet>=0.21.0` - UI framework
- `almapipy>=0.4.0` - Alma API wrapper
- `python-dotenv>=1.0.0` - Environment variable management

## API Documentation

- [Alma API Documentation](https://developers.exlibrisgroup.com/alma/apis/)
- [almapipy GitHub Repository](https://github.com/UCDavisLibrary/almapipy)
- [Flet Documentation](https://flet.dev)

## Security Notes

- Never commit your `.env` file or API keys to version control
- The `.env` file is included in `.gitignore` to prevent accidental commits
- Use API keys with minimal required permissions
- Regularly rotate your API keys

## Troubleshooting

### "API Key not configured" error
- Ensure you've created a `.env` file with valid `ALMA_API_KEY`
- Check that the `.env` file is in the project root directory

### "Failed to connect to Alma API" error
- Verify your API key is valid
- Check that the `ALMA_API_URL` matches your institution's region
- Ensure your API key has appropriate permissions

### Virtual environment issues
- Delete the `.venv` folder and run `./run.sh` again
- Ensure Python 3.8+ is installed: `python3 --version`

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Specify license here]

## Contact

For questions or support, please open an issue on GitHub.

## Acknowledgments

- Built with [Flet](https://flet.dev)
- Uses [almapipy](https://github.com/UCDavisLibrary/almapipy) by UC Davis Library
- Developed for Digital Grinnell
