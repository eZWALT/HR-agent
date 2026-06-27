import os
import json
import tempfile
import pathlib
import pytest
from unittest.mock import patch


class TestServiceAreas:
    def test_fallback_when_no_file(self):
        from src.hr_agent.prompts import _service_areas
        with patch("src.hr_agent.prompts._load_core_info", return_value={}):
            areas = _service_areas()
        assert "madrid" in areas
        assert "bilbao" in areas
        assert "cdmx" in areas

    def test_from_core_info(self):
        from src.hr_agent.prompts import _service_areas
        mock_info = {"service_cities": ["Madrid", "Barcelona", "CDMX"]}
        with patch("src.hr_agent.prompts._load_core_info", return_value=mock_info):
            areas = _service_areas()
        assert "madrid" in areas
        assert "barcelona" in areas
        assert "cdmx" in areas

    def test_all_lowercase(self):
        from src.hr_agent.prompts import _service_areas
        mock_info = {"service_cities": ["Madrid", "Paris"]}
        with patch("src.hr_agent.prompts._load_core_info", return_value=mock_info):
            areas = _service_areas()
        for a in areas:
            assert a == a.lower()
        for a in areas:
            assert a == a.lower()

    def test_strips_whitespace(self):
        from src.hr_agent.prompts import _service_areas
        mock_info = {"service_cities": ["  Madrid  ", " Bilbao"]}
        with patch("src.hr_agent.prompts._load_core_info", return_value=mock_info):
            areas = _service_areas()
        assert "madrid" in areas
        assert "bilbao" in areas
        assert "  madrid  " not in areas

    def test_real_data_loads_43_cities(self):
        from src.hr_agent.prompts import _service_areas
        real_file = pathlib.Path("data/grupo-sazon/core-info.json")
        if not real_file.exists():
            pytest.skip("core-info.json not available (expected on atlas)")
        with patch.dict(os.environ, {"CLIENT_SLUG": "grupo-sazon"}):
            mock_info = json.loads(real_file.read_text())
        with patch("src.hr_agent.prompts._load_core_info", return_value=mock_info):
            areas = _service_areas()
        assert len(areas) >= 40
        assert "madrid" in areas
        assert "chihuahua" in areas


class TestLanguageLabel:
    def test_en(self):
        from src.hr_agent.prompts import language_label
        assert language_label("EN") == "English"
        assert language_label("en") == "English"

    def test_es(self):
        from src.hr_agent.prompts import language_label
        assert language_label("ES") == "Spanish"
        assert language_label("es") == "Spanish"

    def test_none_defaults_to_english(self):
        from src.hr_agent.prompts import language_label
        assert language_label(None) == "English"
        assert language_label("") == "English"

    def test_unknown_defaults_to_english(self):
        from src.hr_agent.prompts import language_label
        assert language_label("FR") == "English"

    def test_strips_whitespace(self):
        from src.hr_agent.prompts import language_label
        assert language_label("  ES  ") == "Spanish"
