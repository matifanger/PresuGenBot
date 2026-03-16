import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youtube_handler import is_youtube_url


class TestYouTubeURL:
    """Tests para la función is_youtube_url()"""

    def test_youtube_watch_url(self):
        """Test URL estándar de YouTube watch"""
        assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_youtube_short_url(self):
        """Test URL corta youtu.be"""
        assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ") is True

    def test_youtube_embed_url(self):
        """Test URL de embed"""
        assert is_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ") is True

    def test_youtube_shorts_url(self):
        """Test URL de shorts"""
        assert is_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") is True

    def test_youtube_no_cookie_url(self):
        """Test URL youtube-nocookie"""
        assert is_youtube_url("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ") is True

    def test_youtube_no_www(self):
        """Test URL sin www"""
        assert is_youtube_url("https://youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_youtube_http(self):
        """Test URL con http"""
        assert is_youtube_url("http://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_not_youtube(self):
        """Test que NO es YouTube"""
        assert is_youtube_url("https://www.instagram.com/reel/ABC123/") is False
        assert is_youtube_url("https://www.google.com") is False
        assert is_youtube_url("https://vimeo.com/123456789") is False

    def test_empty_string(self):
        """Test string vacío"""
        assert is_youtube_url("") is False

    def test_none_input(self):
        """Test con None"""
        assert is_youtube_url(None) is False

    def test_random_text(self):
        """Test con texto aleatorio"""
        assert is_youtube_url("hola mundo") is False
