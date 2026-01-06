// Parse cookie string to extract url, weeCookie, heroSession
export function parseCookie(cookie) {
  let url = "", weeCookie = "", heroSession = "";
  if (cookie) {
    const urlMatch = cookie.match(/svr=([^;]+)/);
    const weeMatch = cookie.match(/weeCookie=([^;]+)/);
    const heroMatch = cookie.match(/50hero_session=([^;]+)/);
    url = urlMatch ? urlMatch[1] : "";
    weeCookie = weeMatch ? weeMatch[1] : "";
    heroSession = heroMatch ? heroMatch[1] : "";
  }
  return { url, weeCookie, heroSession };
}

// Compose cookie string from components
export function composeCookie(url, weeCookie, heroSession) {
  return `svr=${url};weeCookie=${weeCookie};50hero_session=${heroSession}`;
}

// Clean cookie values (remove prefixes if present)
export function cleanCookieValue(value, prefix) {
  return value.startsWith(prefix) ? value.split('=')[1] : value;
} 