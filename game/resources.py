"""Resource 폴더의 이미지·json 을 경로로 불러오고, 같은 파일은 한 번만 읽는다."""
import json
import os

from pico2d import load_image

from config import RESOURCE_DIR

_images = {}
_jsons = {}


def path(*parts):
    return os.path.join(RESOURCE_DIR, *parts)


def image(*parts):
    p = path(*parts)
    if p not in _images:
        _images[p] = load_image(p)
    return _images[p]


def json_data(*parts):
    p = path(*parts)
    if p not in _jsons:
        with open(p, encoding='utf-8') as f:
            _jsons[p] = json.load(f)
    return _jsons[p]
