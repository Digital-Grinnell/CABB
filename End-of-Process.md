Processing MMS ID 991011589639004641:
  Copying TIFF: grinnell_35259_OBJ.tiff
    ✓ Copied to For-Import/grinnell_35259_OBJ.tiff
  Creating JPG: grinnell_35259_OBJ.jpg
    ✓ Created JPG at For-Import/grinnell_35259_OBJ.jpg
  Updating alma_export CSV:
    file_name_1: grinnell_35259_OBJ.jpg
    file_name_2: grinnell_35259_OBJ.tiff

Processing MMS ID 991011589639204641:
  Copying TIFF: grinnell_35308_OBJ.tiff
  
Traceback (most recent call last):
  File "/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/lib/python3.13/shutil.py", line 266, in copyfile
    _fastcopy_fcopyfile(fsrc, fdst, posix._COPYFILE_DATA)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/lib/python3.13/shutil.py", line 110, in _fastcopy_fcopyfile
    raise err from None
  File "/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/lib/python3.13/shutil.py", line 103, in _fastcopy_fcopyfile
    posix._fcopyfile(infd, outfd, flags)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
OSError: [Errno 5] Input/output error: '/Volumes/exports/college-life/OBJ/grinnell_35308_OBJ.tiff' -> 'For-Import/grinnell_35308_OBJ.tiff'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/mcfatem/GitHub/CABB/process_tiffs_for_import.py", line 127, in <module>
    process_tiffs()
    ~~~~~~~~~~~~~^^
  File "/Users/mcfatem/GitHub/CABB/process_tiffs_for_import.py", line 73, in process_tiffs
    shutil.copy2(source_tiff, dest_tiff)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/lib/python3.13/shutil.py", line 468, in copy2
    copyfile(src, dst, follow_symlinks=follow_symlinks)
    ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/lib/python3.13/shutil.py", line 260, in copyfile
    with open(src, 'rb') as fsrc:
         ~~~~^^^^^^^^^^^
OSError: [Errno 22] Invalid argument
(.venv) ╭─mcfatem@MAC3Q2TM4WHQ ~/GitHub/CABB ‹main› 
╰─$                                                                                                                              1 ↵