import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from social_media_handler import is_instagram_url


class TestInstagramURL:
    """Tests para la función is_instagram_url()"""

    def test_instagram_reel_url(self):
        """Test URL de reel estándar"""
        assert is_instagram_url("https://www.instagram.com/reels/DQJwCjPDn9h/") is True

    def test_instagram_reel_short(self):
        """Test URL de reel sin trailing slash"""
        assert is_instagram_url("https://www.instagram.com/reel/DQJwCjPDn9h") is True

    def test_instagram_reels_plural(self):
        """Test URL con 'reels' plural"""
        assert is_instagram_url("https://www.instagram.com/reels/ABC123456/") is True

    def test_instagram_post_url(self):
        """Test URL de post"""
        assert is_instagram_url("https://www.instagram.com/p/ABC123456/") is True

    def test_instagram_tv_url(self):
        """Test URL de IGTV"""
        assert is_instagram_url("https://www.instagram.com/tv/ABC123456/") is True

    def test_instagram_no_www(self):
        """Test URL sin www"""
        assert is_instagram_url("https://instagram.com/reel/ABC123/") is True

    def test_instagram_http(self):
        """Test URL con http"""
        assert is_instagram_url("http://www.instagram.com/reel/ABC123/") is True

    def test_instagram_case_insensitive(self):
        """Test que es case insensitive"""
        assert is_instagram_url("HTTPS://WWW.INSTAGRAM.COM/REEL/ABC123/") is True

    def test_not_instagram(self):
        """Test que NO es Instagram"""
        assert is_instagram_url("https://www.youtube.com/watch?v=abc") is False
        assert is_instagram_url("https://www.google.com") is False
        assert is_instagram_url("https://twitter.com/user/status/123") is False
        assert is_instagram_url("https://tiktok.com/@user/video/123") is False

    def test_empty_string(self):
        """Test string vacío"""
        assert is_instagram_url("") is False

    def test_none_input(self):
        """Test con None"""
        assert is_instagram_url(None) is False

    def test_random_text(self):
        """Test con texto aleatorio"""
        assert is_instagram_url("hola mundo") is False
        assert is_instagram_url("instagram.com") is False


class TestInstagramDownload:
    """Tests para la descarga de videos de Instagram"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        os.getenv("SKIP_INTEGRATION_TESTS") == "1",
        reason="Integration tests disabled"
    )
    def test_download_instagram_video_selenium(self):
        """Test de descarga real con Selenium"""
        from social_media_handler import download_instagram_video
        import tempfile

        test_url = "https://www.instagram.com/reels/DQJwCjPDn9h/"

        with tempfile.TemporaryDirectory() as tmpdir:
            original_download_dir = social_media_handler.DOWNLOAD_DIR
            social_media_handler.DOWNLOAD_DIR = tmpdir

            try:
                result = download_instagram_video(test_url)
                assert result is not None
                assert os.path.exists(result)
                assert result.endswith('.mp4')
                assert os.path.getsize(result) > 0
            finally:
                social_media_handler.DOWNLOAD_DIR = original_download_dir

    def test_extract_shortcode(self):
        """Test de extracción de shortcode"""
        from social_media_handler import _extract_instagram_shortcode

        assert _extract_instagram_shortcode("https://www.instagram.com/reels/DQJwCjPDn9h/") == "DQJwCjPDn9h"
        assert _extract_instagram_shortcode("https://www.instagram.com/reel/ABC123/") == "ABC123"
        assert _extract_instagram_shortcode("https://instagram.com/p/xyz789/") == "xyz789"
        assert _extract_instagram_shortcode("not_a_url") is None


import social_media_handler
