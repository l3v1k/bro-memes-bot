import os
import httpx
import logging
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parents[3] / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

class CobaltClient:
    """Client for Cobalt API (https://cobalt.tools/)"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("COBALT_API_KEY environment variable is not set")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client"""
        if self._client is None:
            self._client = httpx.AsyncClient(headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Api-Key {self.api_key}'
            })
        return self._client
    
    async def close(self):
        """Close the client session"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def get_media_url(self, url: str, video_quality: str = '1080') -> Optional[Dict[str, str]]:
        """
        Get direct media URL from Cobalt API
        
        Args:
            url: Social media URL to process
            video_quality: Quality of video (144-4320, max). Default 1080
            
        Returns:
            Dict with 'url' and 'filename' if successful, None otherwise
        """
        try:
            client = await self._get_client()
            payload = {
                'url': url,
                # 'videoQuality': video_quality,
                # 'filenameStyle': 'pretty',  # More readable filenames
                'downloadMode': 'auto',     # Download both video and audio
            }
            
            response = await client.post(self.base_url, json=payload)

            logger.info(f"Cobalt API response: {response.text}")
            logger.info(f"Cobalt API response headers: {response.headers}")
            logger.info(response)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'redirect':
                return {
                    'url': data['url'],
                    'filename': data.get('filename', 'video.mp4')
                }
            elif data.get('status') == 'error':
                error = data.get('error', {})
                logger.error(
                    f"Cobalt API error: {error.get('code')} "
                    f"Context: {error.get('context')}"
                )
                return None
            elif data.get('status') == 'picker':
                # For posts with multiple media, take the first video/photo
                for item in data.get('picker', []):
                    if item.get('type') in ('video', 'photo'):
                        return {
                            'url': item['url'],
                            'filename': data.get('filename', 'media.mp4')
                        }
                logger.error("No suitable media found in picker response")
                return None
            else:
                logger.error(f"Unexpected Cobalt API response: {data}")
                return None
                
        except httpx.RequestError as e:
            logger.error(f"Error making request to Cobalt API: {str(e)}")
            return None
        except KeyError as e:
            logger.error(f"Unexpected Cobalt API response format: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while getting media URL: {str(e)}")
            return None