import re

VIDEO_URL_ERROR = (
    "Plataforma no soportada o link inválido. Solo se permite YouTube, Vimeo o Google Drive."
)

_YOUTUBE_PATTERN = re.compile(
    r"^(?:(?:www\.)?youtube\.com/(?:watch\?v=|embed/)|(?:www\.)?youtu\.be/|youtube-nocookie\.com/embed/)"
    r"([\w-]{11})(?:[?&][^\s]*)?$",
    re.IGNORECASE,
)
_VIMEO_PATTERN = re.compile(
    r"^(?:(?:www\.)?vimeo\.com/|player\.vimeo\.com/video/)(\d+)(?:[?&][^\s]*)?$",
    re.IGNORECASE,
)
_GOOGLE_DRIVE_PATTERN = re.compile(
    r"^drive\.google\.com/file/d/([a-zA-Z0-9_-]+)(?:/[^\s?]*)?(?:\?[^\s]*)?$",
    re.IGNORECASE,
)


def parse_video_url(video_url: str | None) -> tuple[str, str] | None:
    if video_url is None:
        return None

    url = video_url.strip()
    if not url:
        return None

    candidate = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    for platform, pattern, embed_url in (
        ("YOUTUBE", _YOUTUBE_PATTERN, "https://www.youtube-nocookie.com/embed/{}"),
        ("VIMEO", _VIMEO_PATTERN, "https://player.vimeo.com/video/{}"),
        ("GOOGLE_DRIVE", _GOOGLE_DRIVE_PATTERN, "https://drive.google.com/file/d/{}/preview"),
    ):
        match = pattern.fullmatch(candidate)
        if match:
            return platform, embed_url.format(match.group(1))

    raise ValueError(VIDEO_URL_ERROR)
