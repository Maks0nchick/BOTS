import requests

def download_zoom_file(download_url: str, save_path: str) -> str:
    """
    При включённой опции 'Allow viewers to download cloud recordings'
    Zoom выдаёт рабочий download_url уже с access_token внутри.
    """
    resp = requests.get(download_url, stream=True)
    resp.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return save_path
