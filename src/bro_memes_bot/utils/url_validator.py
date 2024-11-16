import re
from typing import Optional, Tuple
from enum import Enum

class MediaService(Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    UNKNOWN = "unknown"

class URLValidator:
    """Validates and identifies social media URLs"""
    
    # URL patterns for different platforms
    PATTERNS = {
        MediaService.INSTAGRAM: r'(?:https?:\/\/)?(?:www\.)?instagram\.com(?:\/[^\/]+)?\/(?:p|reel)\/([^\/?#&]+)',
        MediaService.TIKTOK: r'(?:https?:\/\/)?(?:www\.|vm\.|vt\.)?tiktok\.com\/(?:@[\w.-]+\/video\/\d+|[\w.-]+)',
        MediaService.YOUTUBE: r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:shorts\/|watch\?v=)|youtu\.be\/)([a-zA-Z0-9_-]+)',
        MediaService.TWITTER: r'(?:https?:\/\/)?(?:www\.)?(?:twitter\.com|x\.com)\/(?:\w+)\/status\/(\d+)'
    }

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, Optional[MediaService]]:
        """
        Validate URL and identify the service
        Returns: (is_valid: bool, service: Optional[MediaService])
        """
        for service, pattern in cls.PATTERNS.items():
            if re.match(pattern, url):
                return True, service
        return False, None

    @classmethod
    def extract_media_id(cls, url: str, service: MediaService) -> Optional[str]:
        """Extract media ID from URL if possible"""
        pattern = cls.PATTERNS.get(service)
        if not pattern:
            return None
            
        match = re.match(pattern, url)
        return match.group(1) if match else None 