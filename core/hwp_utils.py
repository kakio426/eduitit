import os
import tempfile
from pathlib import Path

import sys
import os

# Manual fix for pywin32 DLLs if post-install script wasn't run
try:
    import site
    possible_paths = [site.getusersitepackages()] + sys.path
    for p in possible_paths:
        system32_path = os.path.join(p, "pywin32_system32")
        if os.path.exists(system32_path):
            os.environ['PATH'] = system32_path + os.pathsep + os.environ['PATH']
            print(f"DEBUG: Added {system32_path} to PATH", file=sys.stderr)
            break
except Exception:
    pass

try:
    if sys.platform == "win32":
        import pythoncom
        import win32com.client as win32
        HAS_WIN32 = True
    else:
        HAS_WIN32 = False
except Exception as e:
    import sys
    print(f"DEBUG: pywin32 import failed: {e}", file=sys.stderr)
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
