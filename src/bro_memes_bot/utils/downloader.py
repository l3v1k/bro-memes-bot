import os
import tempfile
from pathlib import Path
import yt_dlp
from typing import Optional, Dict
import logging
import httpx
from .cobalt_client import CobaltClient
import re

logger = logging.getLogger(__name__)

class MediaDownloader:
    """Handles media downloads from various platforms using yt-dlp"""
    
    # Constants
    MAX_FILE_SIZE = 50_000_000  # 50MB Telegram limit
    MAX_TITLE_LENGTH = 64
    
    def __init__(self):
        self.base_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': str(Path(tempfile.gettempdir()) / '%(extractor)s_%(id)s.%(ext)s'),
            'max_filesize': self.MAX_FILE_SIZE,
        }
        
        # Combine options to reduce duplication
        self.yt_opts = {
            **self.base_opts,
            'netrc_location': os.getenv('NETRC_LOCATION'),
            'cachedir': os.getenv('CACHE_DIR'),
            'usenetrc': True,
        }
        
        self.cobalt_client = CobaltClient(
            base_url=os.getenv('COBALT_BASE_URL', 'http://localhost:9000/'),
            api_key=os.getenv('COBALT_API_KEY')
        )
    
    def _sanitize_title(self, title: str) -> str:
        """Sanitize and truncate title"""
        # Remove non-word characters except basic punctuation
        clean_title = re.sub(r'[^\w\s,.!?-]', '', title)
        # Replace multiple spaces with single space
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        return clean_title[:self.MAX_TITLE_LENGTH] if clean_title else 'video'
    
    async def _download_with_ytdl(self, url: str, opts: Dict) -> Optional[Dict]:
        """Generic yt-dlp download handler"""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Check file size first
                info = ydl.extract_info(url, download=False)
                if info.get('filesize', 0) > self.MAX_FILE_SIZE:
                    raise ValueError("Video file is too large (>50MB)")
                
                # Download if size check passes
                info = ydl.extract_info(url, download=True)
                
                return {
                    'file_path': ydl.prepare_filename(info),
                    'title': self._sanitize_title(info.get('title', 'video')),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                }
                
        except Exception as e:
            logger.error(f"Error downloading from {url}: {str(e)}")
            return None

    async def download_youtube(self, url: str) -> Optional[Dict]:
        """Download YouTube Shorts"""
        if '/shorts/' not in url:
            logger.info("Not a YouTube Shorts URL, skipping download")
            return None
        return await self._download_with_ytdl(url, self.yt_opts)
            
    async def download_tiktok(self, url: str) -> Optional[Dict]:
        """Download TikTok video"""
        return await self._download_with_ytdl(url, self.base_opts)

    async def download_twitter(self, url: str) -> Optional[Dict]:
        """Download Twitter/X video"""
        result = await self._download_with_ytdl(url, self.base_opts)
        if result:
            # Improve Twitter titles
            title = result['title']
            if not title or title == 'Twitter':
                info = await self._download_with_ytdl(url, {'extract_flat': True})
                uploader = info.get('uploader', 'unknown') if info else 'unknown'
                result['title'] = self._sanitize_title(f"Twitter_video_by_{uploader}")
        return result

    async def download_instagram(self, url: str) -> Optional[Dict]:
        """Download Instagram media using Cobalt API"""
        try:
            media_info = await self.cobalt_client.get_media_url(url)
            if not media_info:
                raise ValueError("Failed to get media URL from Cobalt API")
            
            temp_file = Path(tempfile.gettempdir()) / media_info['filename']
            
            async with httpx.AsyncClient() as client:
                response = await client.get(media_info['url'])
                response.raise_for_status()
                # Use synchronous write since we're writing the entire content at once
                temp_file.write_bytes(response.content)
            
            return {
                'file_path': str(temp_file),
                'title': self._sanitize_title(temp_file.stem),
                'duration': None,
                'thumbnail': None
            }
                
        except Exception as e:
            logger.error(f"Error downloading Instagram media: {str(e)}")
            return None

    def cleanup(self, file_path: str) -> None:
        """Remove downloaded file"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {str(e)}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cobalt_client.close()