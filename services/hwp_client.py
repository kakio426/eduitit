import requests
from django.conf import settings
from typing import Optional

class HWPClient:
    """
    Client for interacting with the local HWP Conversion Microservice.
    Requires the microservice to be running (default: http://localhost:8000).
    """
    
    def __init__(self, service_url: str = "http://localhost:8000"):
        # Allow overriding via settings if needed in the future
        self.base_url = getattr(settings, "HWP_SERVICE_URL", service_url)

    def convert_to_pdf(self, file_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Sends an HWP/HWPX file to the microservice and downloads the converted PDF.
        
        Args:
            file_path: Absolute path to the source .hwp/.hwpx file.
            output_path: Optional path to save the PDF. If None, saves alongside source.
            
        Returns:
            str: Path to the saved PDF file, or None if failed.
        """
        url = f"{self.base_url}/api/convert/sync"  # Assuming a synchronous endpoint for simplicity or we can poll
        
        # Note: The current microservice implementation in 'hwp-pdf' mainly supports 
        # async job polling via /api/upload -> job_id -> /api/status -> /api/download.
        # For server-to-server integration, implementing a polling logic here is better.
        
        return self._convert_with_polling(file_path, output_path)

    def _convert_with_polling(self, file_path: str, output_path: Optional[str]) -> Optional[str]:
        import time
        import os
        
        filename = os.path.basename(file_path)
        
        # 1. Upload
        upload_url = f"{self.base_url}/api/upload"
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'application/octet-stream')}
            try:
                resp = requests.post(upload_url, files=files)
                resp.raise_for_status()
                data = resp.json()
                job_id = data['job_id']
            except Exception as e:
                print(f"[HWPClient] Upload failed: {e}")
                return None

        # 2. Poll Status
        status_url = f"{self.base_url}/api/status/{job_id}"
        max_retries = 30  # 30 seconds timeout approximation
        
        for _ in range(max_retries):
            try:
                resp = requests.get(status_url)
                resp.raise_for_status()
                status_data = resp.json()
                
                state = status_data.get('status')
                if state == 'completed':
                    break
                elif state == 'failed':
                    print(f"[HWPClient] Conversion failed on server: {status_data.get('error')}")
                    return None
                    
                time.sleep(1)
            except Exception as e:
                print(f"[HWPClient] Polling error: {e}")
                return None
        else:
            print("[HWPClient] Timeout waiting for conversion.")
            return None

        # 3. Download
        download_url = f"{self.base_url}/api/download/{job_id}"
        try:
            resp = requests.get(download_url)
            resp.raise_for_status()
            
            if not output_path:
                output_path = os.path.splitext(file_path)[0] + ".pdf"
                
            with open(output_path, 'wb') as f:
                f.write(resp.content)
                
            return output_path
        except Exception as e:
            print(f"[HWPClient] Download failed: {e}")
            return None
