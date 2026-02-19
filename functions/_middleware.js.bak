export async function onRequest(context) {
  const url = new URL(context.request.url);
  const path = url.pathname;

  // 1. 쿼리 파라미터 정리 (category, page, ref_src)
  if (url.searchParams.has('category') || url.searchParams.has('page') || url.searchParams.has('ref_src')) {
    url.search = '';
    return Response.redirect(url.toString(), 301);
  }

  // 2. 경로에 인코딩된 category 파라미터가 섞인 경우
  if (path.includes('category%3D') || path.includes('category=')) {
    const cleanPath = path.split('?')[0].replace(/[?&]?category(%3D|=)[^/&]*/gi, '');
    return Response.redirect(url.origin + cleanPath, 301);
  }

  // 3. /m/ 모바일 경로
  if (path.startsWith('/m/')) {
    let newPath = path.replace(/^\/m/, '');
    newPath = newPath.replace(/\/comments\/?$/, '/');
    return Response.redirect(url.origin + newPath, 301);
  }

  // 4. /comments 경로 제거
  if (path.endsWith('/comments') || path.endsWith('/comments/')) {
    const cleanPath = path.replace(/\/comments\/?$/, '/');
    return Response.redirect(url.origin + cleanPath, 301);
  }

  // 5. /entry/xxx -> /posts/xxx/ (핵심!)
  if (path.startsWith('/entry/')) {
    const slug = path.replace(/^\/entry\//, '').replace(/\/$/, '');
    if (slug) {
      return Response.redirect(url.origin + '/posts/' + slug + '/', 301);
    }
    return Response.redirect(url.origin + '/', 301);
  }

  // 6. 숫자 ID URL -> 홈
  if (/^\/\d+\/?$/.test(path)) {
    return Response.redirect(url.origin + '/', 301);
  }

  // 7. /tag/ (단수, 티스토리) -> /tags/
  if (path.startsWith('/tag/')) {
    return Response.redirect(url.origin + '/tags/', 301);
  }

  // 8. /category (단수, 티스토리) -> /categories/
  if (path.startsWith('/category')) {
    return Response.redirect(url.origin + '/categories/', 301);
  }

  // 9. /guestbook
  if (path === '/guestbook' || path === '/guestbook/') {
    return Response.redirect(url.origin + '/', 301);
  }

  // 10. /file/
  if (path.startsWith('/file/')) {
    return Response.redirect(url.origin + '/', 301);
  }

  // 11. /posts/날짜-제목/ -> /posts/제목/ (날짜 접두사 제거)
  const datePostMatch = path.match(/^\/posts\/(\d{4}-\d{2}-\d{2}-)(.+)$/);
  if (datePostMatch) {
    const slugPart = datePostMatch[2];
    return Response.redirect(url.origin + '/posts/' + slugPart, 301);
  }

  return context.next();
}
