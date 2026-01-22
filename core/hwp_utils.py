import os
import pythoncom
import win32com.client as win32
import tempfile
from pathlib import Path

def convert_hwp_to_pdf_local(input_path, output_path):
    """
    Converts a HWP file to PDF using locally installed Hancom Office via OLE automation.
    """
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
