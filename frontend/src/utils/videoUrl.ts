export function getVideoEmbedUrl(value: string): string | null {
  const url = value.trim();
  if (!url) return null;

  const candidate = url.replace(/^https?:\/\//i, '');
  const youtubeMatch = candidate.match(
    /^(?:(?:www\.)?youtube\.com\/(?:watch\?v=|embed\/)|(?:www\.)?youtu\.be\/|youtube-nocookie\.com\/embed\/)([\w-]{11})(?:[?&][^\s]*)?$/i,
  );
  if (youtubeMatch) return `https://www.youtube-nocookie.com/embed/${youtubeMatch[1]}`;

  const vimeoMatch = candidate.match(
    /^(?:(?:www\.)?vimeo\.com\/|player\.vimeo\.com\/video\/)(\d+)(?:[?&][^\s]*)?$/i,
  );
  if (vimeoMatch) return `https://player.vimeo.com/video/${vimeoMatch[1]}`;

  const driveMatch = candidate.match(
    /^drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)(?:\/[^\s?]*)?(?:\?[^\s]*)?$/i,
  );
  if (driveMatch) return `https://drive.google.com/file/d/${driveMatch[1]}/preview`;

  return null;
}
