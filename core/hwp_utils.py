import os
import tempfile
from pathlib import Path

try:
    import pythoncom
    import win32com.client as win32
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

def convert_hwp_to_pdf_local(input_path, output_path):
    """
    Converts a HWP file to PDF using locally installed Hancom Office via OLE automation.
    """
    if not HAS_WIN32:
        raise ImportError("HWP conversion is only supported on Windows with pywin32 installed.")

    # Initialize COM for the current thread
    pythoncom.CoInitialize()
    hwp = None
    try:
        # Launch HWP application
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        
        # Security: Disable file path check dialog if necessary
        # hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        
        # Hide the window for background processing
        hwp.XHwpWindows.Item(0).Visible = False
        
        # Open the file
        if not hwp.Open(input_path):
            raise Exception(f"Failed to open HWP file: {input_path}")
            
        # Set save parameters for PDF
        hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
        hwp.HParameterSet.HFileOpenSave.filename = output_path
        hwp.HParameterSet.HFileOpenSave.Format = "PDF"
        
        # Execute save
        if not hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet):
            raise Exception("Failed to execute SaveAs PDF")
            
        return True
    except Exception as e:
        print(f"Error during HWP conversion: {e}")
        raise e
    finally:
        if hwp:
            hwp.Clear(1) # Clear document without saving
            hwp.Quit()
        # Uninitialize COM
        pythoncom.CoUninitialize()
